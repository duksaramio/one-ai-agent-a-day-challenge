# one-ai-agent-a-day-challenge

I am embarking on a journey to build one AI agent a day.

## Constraints

- Local LLM
- Observability is a must
- Do One Thing and One thing well

## Stack & Tools

- **Framework**: Pydantic AI
- **LLM**: Ollama (`qwen3.6:27b` run locally)
- **Observability**: Langfuse (run locally on port 3000)
- **Environment**: Ubuntu 24.04 LTS, Nvidia RTX 4090, Docker

## Completed Agents

### Day 1: Obsidian Reader Agent (`obsidian_reader/`)
An AI agent capable of exploring, reading, and searching files inside the Obsidian vault (`/home/d3lee/obsidian`) with path traversal safety and local Langfuse tracing.

#### Setup & Usage:
1. Initialize the environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy credentials template and set keys:
   ```bash
   cp .env.example .env
   ```
3. Run the CLI tool:
   - **Interactive Chat Loop**:
     ```bash
     .venv/bin/python3 -m obsidian_reader.cli
     ```
   - **Single-Query Mode**:
     ```bash
     .venv/bin/python3 -m obsidian_reader.cli "Search my notes for saram"
     ```

---

## AI Agents to Build (Upcoming)

- bsky social network poster for saram.io
- doomscrolling poster for doomscroll.saram.io
- end of day report agent
- personal blogger
- email assistant
- file directory organizer
