# ANTIGRAVITY WORKSPACE - PYDANTIC AI LOCAL STACK

## CORE STACK - NON-NEGOTIABLE

1. LLM: qwen3.6:27b via Ollama locally. Host http://localhost:11434. No cloud APIs.
2. Framework: Pydantic AI ONLY. All agents via `pydantic_ai.Agent`.
3. Observability: Langfuse ONLY. Host http://localhost:3000. Every agent run must be traced.

You MUST NOT use `openai:gpt-4`, `anthropic:claude`, `gemini` models directly. You MUST NOT use Langfuse Cloud.