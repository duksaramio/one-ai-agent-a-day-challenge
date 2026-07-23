import os
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from functools import wraps
from inspect import signature
from typing import Any, AsyncIterator
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Set default Ollama base URL if not already defined
if not os.environ.get("OLLAMA_BASE_URL"):
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

from pydantic_ai import Agent
from pydantic_ai.models import Model, StreamedResponse
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.messages import ModelResponse
from langfuse.decorators import langfuse_context, observe

# --- Custom Langfuse Wrapper for Pydantic AI ---
def _wrap_model_request(model: Model) -> Model:
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


def _wrap_model_request_stream(model: Model) -> Model:
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
    model = _wrap_model_request(model)
    model = _wrap_model_request_stream(model)
    return model


def observed_agent(agent: Agent) -> Agent:
    if not agent.model:
        return agent
    agent.model = observed_model(agent.model)
    return agent


# --- Structured Output Schema ---
class BlogSummary(BaseModel):
    title: str = Field(description="The main title of the blog post")
    author: str | None = Field(default=None, description="The author of the blog post, if identified")
    publish_date: str | None = Field(default=None, description="The publish date of the blog post, if identified")
    summary: str = Field(description="A concise summary (1-2 sentences) of the overall blog post")
    key_points: list[str] = Field(description="A list of the main points, arguments, or insights from the post")
    key_takeaway: str = Field(description="The primary action item, lesson, or takeaway from the post")


from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# --- Initialize Unsloth OpenAI-compatible Model ---
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


# --- Define Pydantic AI Agent ---
agent = Agent(
    model=model,
    name="blog_summarizer_agent",
    output_type=BlogSummary,
    model_settings={
        'extra_body': {
            'enable_tools': True,
            'enabled_tools': ['web_search', 'python', 'terminal']
        }
    },
    system_prompt=(
        "You are an expert content summarizer. Your task is to read the content of a blog post "
        "and generate a structured summary. Do not output internal reasoning or <think> tags. "
        "Use the tools provided to fetch or read the blog post "
        "if a URL or a file path/name is provided in the user request. If raw text content is "
        "provided directly, summarize it directly. Extract the details and return them strictly "
        "conforming to the BlogSummary output schema."
    )
)



# --- Agent Tools ---
@agent.tool_plain
def fetch_blog_post(url: str) -> str:
    """
    Fetch the content of a blog post from a URL.
    
    Args:
        url: The HTTP/HTTPS URL of the blog post.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
    except Exception as e:
        return f"Error fetching URL {url}: {e}"
        
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove non-content elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form']):
            element.decompose()
            
        # Try to find common article containers
        article = None
        for selector in ['article', 'main', '[role="main"]', '.post', '.article', '.entry-content', '#content', '#main']:
            found = soup.select_one(selector)
            if found:
                text = found.get_text(separator='\n').strip()
                if len(text) > 200:
                    article = found
                    break
        
        if article is None:
            article = soup.body if soup.body else soup
            
        # Get clean text with nice spacing
        lines = (line.strip() for line in article.get_text(separator='\n').splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit content length to avoid exceeding context limit
        if len(text) > 30000:
            text = text[:30000] + "\n\n[Content truncated due to length...]"
            
        return text
    except Exception as e:
        return f"Error parsing HTML from {url}: {e}"


@agent.tool_plain
def read_local_file(file_path: str) -> str:
    """
    Read the contents of a local blog post file.
    
    Args:
        file_path: The file path or file name of the local text, markdown, or HTML file.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            blogs_dir_env = os.environ.get("BLOGS_DIR")
            if blogs_dir_env:
                repo_root = Path(__file__).resolve().parent.parent
                blogs_dir = (repo_root / blogs_dir_env).resolve()
                if not blogs_dir.exists():
                    blogs_dir = Path(blogs_dir_env).resolve()
                
                alternative_path = (blogs_dir / file_path).resolve()
                if alternative_path.exists():
                    path = alternative_path
                    
        path = path.resolve()
        if not path.exists():
            return f"Error: Local file '{file_path}' does not exist."
        if not path.is_file():
            return f"Error: '{file_path}' is not a file."
            
        if path.suffix.lower() not in ['.md', '.txt', '.html', '.htm']:
            return f"Error: Unsupported file format '{path.suffix}'. Use .txt, .md, or .html."
            
        content = path.read_text(encoding="utf-8")
        if path.suffix.lower() in ['.html', '.htm']:
            soup = BeautifulSoup(content, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form']):
                element.decompose()
            content = soup.get_text(separator='\n')
            
        if len(content) > 30000:
            content = content[:30000] + "\n\n[Content truncated due to length...]"
        return content
    except Exception as e:
        return f"Error reading local file '{file_path}': {e}"


# Wrap the agent with Langfuse observability
wrapped_agent = observed_agent(agent)
