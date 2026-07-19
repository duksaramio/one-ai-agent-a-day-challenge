# Pydantic AI + Ollama + Langfuse Rules

## 1. Pydantic AI Agent Definition - MANDATORY

ALWAYS use this factory. Never instantiate Agent with a cloud model string.

```python
# src/agents/factory.py - THE ONLY WAY TO CREATE AGENTS
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai import Agent
from pydantic import BaseModel

OLLAMA_MODEL_NAME = "qwen3.6:27b"
OLLAMA_BASE_URL = "http://localhost:11434/v1"

def get_local_agent(output_type=None, system_prompt: str = "", **kwargs):
    ollama_provider = OllamaProvider(base_url="http://localhost:11434")
    ollama_model = OllamaModel(
        model_name=OLLAMA_MODEL_NAME,
        provider=ollama_provider,
    )
    return Agent(
        model=ollama_model,
        output_type=output_type,
        system_prompt=system_prompt,
        **kwargs
    )

# Alternative that also works (OpenAI-compatible):
# from pydantic_ai.models.openai import OpenAIModel
# from pydantic_ai.providers.openai import OpenAIProvider
# def get_local_agent(...):
# model = OpenAIModel(
# model_name="qwen3.6:27b",
# provider=OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama")
# )
# return Agent(model=model,...)