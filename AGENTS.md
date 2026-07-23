# ANTIGRAVITY WORKSPACE - PYDANTIC AI LOCAL STACK

## CORE STACK - NON-NEGOTIABLE

1. LLM: unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL via Unsloth local server. Host http://127.0.0.1:8888/v1. No cloud APIs.
2. Framework: Pydantic AI ONLY. All agents via `pydantic_ai.Agent`.
3. Observability: Langfuse ONLY. Host http://localhost:3000. Every agent run must be traced.

You MUST NOT use `openai:gpt-4`, `anthropic:claude`, `gemini` models directly. You MUST NOT use Langfuse Cloud.