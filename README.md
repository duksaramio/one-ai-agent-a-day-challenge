# one-ai-agent-a-day-challenge

I am embarking on a journey to build one AI agent a day.

## Constraints

- Local LLM
- Observability is a must
- Do One Thing and One thing well

## Stack & Tools

- **Framework**: Pydantic AI
- **LLM**: Unsloth local server (`unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL` at `http://127.0.0.1:8888/v1`)
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

### Day 2: Blog Post Summarizer Agent (`blog_summarizer/`)
An AI agent built with Pydantic AI that reads blog posts from URLs, local file paths, designated folders, or direct copy-pasted text, and generates a structured summary (title, author, date, overview, key points, and key takeaways). Traced locally using Langfuse.

#### Setup & Usage:
1. Configure designated blog post directory in `.env`:
   ```env
   BLOGS_DIR="blogs_folder"
   ```
2. Run the CLI tool:
   - **Interactive Menu / Paste Mode**:
     ```bash
     .venv/bin/python3 -m blog_summarizer.cli
     ```
   - **Summarize a File (Resolves relative to `BLOGS_DIR` or exact path)**:
     ```bash
     .venv/bin/python3 -m blog_summarizer.cli designing_ai_agents.md
     ```
   - **Summarize a URL**:
     ```bash
     .venv/bin/python3 -m blog_summarizer.cli "https://example.com/blog-post"
     ```
   - **Summarize Raw Text via Argument**:
     ```bash
     .venv/bin/python3 -m blog_summarizer.cli -t "Paste your blog content here..."
     ```
   - **Piped Input**:
     ```bash
     cat blog.txt | .venv/bin/python3 -m blog_summarizer.cli
     ```

---

## AI Agents to Build (Upcoming)

- bsky social network poster for saram.io
- doomscrolling poster for doomscroll.saram.io
- end of day report agent
- personal blogger
- email assistant
- file directory organizer

