import os
import re
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from functools import wraps
from inspect import signature
from typing import Any, AsyncIterator, Coroutine

# Load environment variables before importing Pydantic AI/Langfuse to ensure configuration is set
load_dotenv()

# Set default Ollama base URL if not already defined in environment
if not os.environ.get("OLLAMA_BASE_URL"):
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

from pydantic_ai import Agent
from pydantic_ai.models import Model, StreamedResponse
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.messages import ModelResponse
from langfuse.decorators import langfuse_context, observe

# --- Custom Langfuse Wrapper for Pydantic AI v2 ---
# Since the community langfuse-pydantic-ai package has compatibility issues with Pydantic AI v2
# (e.g. missing imports and changed RunUsage attributes), we implement a clean custom wrapper here.

def _warp_model_request(model: Model) -> Model:
    origin_request = model.request
    sig = signature(origin_request)

    @wraps(origin_request)
    @observe(name="model-request", as_type="generation")
    async def _wrapped(*args: Any, **kwargs: Any) -> ModelResponse:
        bound_args = sig.bind(*args, **kwargs)
        bound_kwargs = dict(bound_args.arguments)

        langfuse_context.update_current_observation(
            input=bound_kwargs["messages"],
            model=model.model_name,
            model_parameters=bound_kwargs.get("model_parameters", None),
            metadata=bound_kwargs,
        )

        response = await origin_request(*args, **kwargs)
        usage = response.usage

        # Map new Pydantic AI RunUsage fields to Langfuse structure
        langfuse_context.update_current_observation(
            output=response,
            usage={
                "input": usage.input_tokens if usage else 0,
                "output": usage.output_tokens if usage else 0,
                "total": (usage.input_tokens + usage.output_tokens) if usage else 0,
            },
        )

        return response

    model.request = _wrapped
    return model


def _warp_model_request_stream(model: Model) -> Model:
    origin_request_stream = model.request_stream
    sig = signature(origin_request_stream)

    @wraps(origin_request_stream)
    @asynccontextmanager
    @observe(name="model-request-stream", as_type="generation")
    async def _wrapped(*args: Any, **kwargs: Any) -> AsyncIterator[StreamedResponse]:
        bound_args = sig.bind(*args, **kwargs)
        bound_kwargs = dict(bound_args.arguments)

        langfuse_context.update_current_observation(
            input=bound_kwargs["messages"],
            model=model.model_name,
            model_parameters=bound_kwargs.get("model_parameters", None),
            metadata=bound_kwargs,
        )

        response: StreamedResponse
        async with origin_request_stream(*args, **kwargs) as response:
            yield response
            usage = response.usage()
            langfuse_context.update_current_observation(
                output=response.get(),
                usage={
                    "input": usage.input_tokens if usage else 0,
                    "output": usage.output_tokens if usage else 0,
                    "total": (usage.input_tokens + usage.output_tokens) if usage else 0,
                },
            )

    model.request_stream = _wrapped
    return model


def observed_model(model: Model) -> Model:
    model = _warp_model_request(model)
    model = _warp_model_request_stream(model)
    return model


def observed_agent(agent: Agent) -> Agent:
    if not agent.model:
        return agent
    agent.model = observed_model(agent.model)
    return agent


# --- Agent Implementation ---

VAULT_ROOT = Path("/home/d3lee/obsidian").resolve()

def get_safe_path(relative_path: str) -> Path:
    """Helper to prevent path traversal and return resolved path."""
    joined_path = (VAULT_ROOT / relative_path.strip("/")).resolve()
    if not str(joined_path).startswith(str(VAULT_ROOT)):
        raise ValueError(f"Access denied: path traversal attempt detected for path '{relative_path}'")
    return joined_path

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# Initialize Unsloth OpenAI-compatible Model
unsloth_base_url = os.environ.get("UNSLOTH_BASE_URL", "http://127.0.0.1:8888/v1")
unsloth_api_key = os.environ.get("UNSLOTH_API_KEY", "sk-unsloth-YOUR_KEY")
llm_model_name = os.environ.get("LLM_MODEL", "unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL")

model = OpenAIChatModel(
    model_name=llm_model_name,
    provider=OpenAIProvider(
        base_url=unsloth_base_url,
        api_key=unsloth_api_key,
    )
)


# Define the Pydantic AI agent
agent = Agent(
    model=model,
    name="obsidian_reader_agent",
    model_settings={
        'extra_body': {
            'enable_tools': True,
            'enabled_tools': ['web_search', 'python', 'terminal']
        }
    },
    system_prompt=(
        "You are an assistant with access to the user's Obsidian vault. "
        "Your task is to help the user search, read, and explore files and folders in their vault. "
        "Do not output internal reasoning or <think> tags. "
        "Use the tools provided to discover files, read their content, and search for specific terms. "
        "Always be concise and provide helpful summaries of notes when requested."
    )
)


@agent.tool_plain
def list_obsidian_files(relative_path: str = "") -> str:
    """
    List files and directories in the user's Obsidian vault.
    
    Args:
        relative_path: The directory path relative to the vault root to list. Defaults to the vault root.
        
    Returns:
        A text list of files and subdirectories.
    """
    try:
        target_dir = get_safe_path(relative_path)
        if not target_dir.exists():
            return f"Error: Directory '{relative_path}' does not exist."
        if not target_dir.is_dir():
            return f"Error: '{relative_path}' is a file, not a directory."
            
        contents = list(target_dir.iterdir())
        if not contents:
            return f"Directory '{relative_path}' is empty."
            
        directories = []
        files = []
        
        for item in contents:
            rel_item_path = item.relative_to(VAULT_ROOT)
            if item.is_dir():
                directories.append(f"[DIR]  {rel_item_path}")
            else:
                files.append(f"[FILE] {rel_item_path}")
                
        # Sort directories and files alphabetically
        directories.sort()
        files.sort()
        
        result_lines = [f"Contents of '{relative_path or '/'}':"]
        result_lines.extend(directories)
        result_lines.extend(files)
        return "\n".join(result_lines)
    except Exception as e:
        return f"Error listing directory '{relative_path}': {str(e)}"

@agent.tool_plain
def read_obsidian_file(relative_path: str) -> str:
    """
    Read the contents of a specific file from the Obsidian vault.
    
    Args:
        relative_path: The file path relative to the vault root to read.
        
    Returns:
        The content of the file or an error message.
    """
    try:
        target_file = get_safe_path(relative_path)
        if not target_file.exists():
            return f"Error: File '{relative_path}' does not exist."
        if not target_file.is_file():
            return f"Error: '{relative_path}' is not a file."
            
        # We only want to read text/markdown files
        if target_file.suffix.lower() not in ['.md', '.txt', '.canvas']:
            return f"Skipping non-text file '{relative_path}' (extension: {target_file.suffix})."
            
        content = target_file.read_text(encoding="utf-8")
        return f"--- Content of {relative_path} ---\n{content}\n--- End of File ---"
    except Exception as e:
        return f"Error reading file '{relative_path}': {str(e)}"

@agent.tool_plain
def search_obsidian_notes(query: str) -> str:
    """
    Search for a text query inside all markdown files within the Obsidian vault.
    
    Args:
        query: The text term/substring to search for (case-insensitive).
        
    Returns:
        A list of files containing the term along with matching line snippets.
    """
    try:
        if not query:
            return "Error: Search query cannot be empty."
            
        matches = []
        query_lower = query.lower()
        
        # Traverse vault recursively
        for path in VAULT_ROOT.rglob("*.md"):
            try:
                content = path.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    lines = content.splitlines()
                    file_matches = []
                    for idx, line in enumerate(lines, 1):
                        if query_lower in line.lower():
                            file_matches.append(f"  Line {idx}: {line.strip()}")
                    
                    if file_matches:
                        rel_path = path.relative_to(VAULT_ROOT)
                        matches.append(f"Match in '{rel_path}':\n" + "\n".join(file_matches[:5]))
            except Exception:
                # Ignore individual file read errors (e.g. permission issues or encoding issues)
                continue
                
        if not matches:
            return f"No matches found for query '{query}'."
            
        return "\n\n".join(matches)
    except Exception as e:
        return f"Error searching notes: {str(e)}"

# Wrap the agent with Langfuse observability
wrapped_agent = observed_agent(agent)
