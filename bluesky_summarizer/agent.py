import os
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from functools import wraps
from inspect import signature
from typing import Any, AsyncIterator, Optional
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator

# Load environment variables from .env
load_dotenv()

from pydantic_ai import Agent
from pydantic_ai.models import Model, StreamedResponse
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


# --- Pydantic Output Schema ---
class BlueskyPostSummary(BaseModel):
    url: str = Field(description="The original URL of the blog post")
    summary: str = Field(description="A single concise summary string strictly UNDER 200 CHARACTERS.")
    character_count: int = Field(description="The total character count of the summary string")

    @field_validator('summary')
    @classmethod
    def validate_summary_length(cls, v: str) -> str:
        v_clean = v.strip()
        if len(v_clean) > 200:
            # If over 220 chars, instruct the LLM to rewrite shorter
            if len(v_clean) > 220:
                raise ValueError(
                    f"Summary length is {len(v_clean)} characters, which exceeds the 200-character limit! "
                    f"Please rewrite the summary as a shorter single sentence under 200 characters."
                )
            # Otherwise truncate cleanly to 200 characters
            v_clean = v_clean[:197].rstrip() + "..."
        return v_clean


from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# --- Initialize Unsloth OpenAI-compatible Model ---
unsloth_base_url = os.environ.get("UNSLOTH_BASE_URL", "http://127.0.0.1:8888/v1")
unsloth_api_key = os.environ.get("UNSLOTH_API_KEY", "sk-unsloth-d4209d8c37ee566e9145b0fd508419aa")
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
    name="bluesky_blog_summarizer_agent",
    output_type=BlueskyPostSummary,
    retries=3,
    model_settings={
        'extra_body': {
            'enable_tools': True,
            'enabled_tools': ['web_search', 'python', 'terminal']
        }
    },
    system_prompt=(
        "You are an expert micro-blogging assistant and content summarizer. "
        "Your task is to fetch the blog post content from the provided URL using the `fetch_blog_post` tool, "
        "and generate a single-sentence summary of the blog post strictly UNDER 200 CHARACTERS. "
        "CRITICAL RULE: The summary field must NOT exceed 200 characters in total length (aim for ~120-160 characters). "
        "Include the original URL in the output schema. Do not output internal reasoning or <think> tags."
    )
)



@agent.tool_plain
def fetch_blog_post(url: str) -> str:
    """
    Fetch the text content of a blog post from a web URL.

    Args:
        url: The HTTP or HTTPS URL of the blog post.
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

        # Clean non-article tags
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form']):
            element.decompose()

        # Find main article element
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

        lines = (line.strip() for line in article.get_text(separator='\n').splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        if len(text) > 30000:
            text = text[:30000] + "\n\n[Content truncated due to length...]"

        return text
    except Exception as e:
        return f"Error parsing HTML content from {url}: {e}"


# Wrap agent with Langfuse tracing
wrapped_agent = observed_agent(agent)
