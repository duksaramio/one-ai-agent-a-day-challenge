import sys
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from blog_summarizer.agent import wrapped_agent, BlogSummary, fetch_blog_post, read_local_file

console = Console()

def resolve_file_path(input_path: str) -> str | None:
    """Check if the input exists as a file directly or inside BLOGS_DIR."""
    path = Path(input_path)
    if path.exists() and path.is_file():
        return str(path.resolve())
    
    # Check inside BLOGS_DIR
    blogs_dir_env = os.environ.get("BLOGS_DIR")
    if blogs_dir_env:
        repo_root = Path(__file__).resolve().parent.parent
        blogs_dir = (repo_root / blogs_dir_env).resolve()
        if not blogs_dir.exists():
            blogs_dir = Path(blogs_dir_env).resolve()
        
        alternative_path = (blogs_dir / input_path).resolve()
        if alternative_path.exists() and alternative_path.is_file():
            return str(alternative_path)
            
    return None

def display_summary(summary: BlogSummary):
    """Render the structured summary beautifully in the terminal."""
    console.print("\n[bold green]=== Generated Blog Summary ===[/bold green]\n")
    
    # Metadata Table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[bold cyan]Title:[/bold cyan]", f"[bold white]{summary.title}[/bold white]")
    if summary.author:
        table.add_row("[bold cyan]Author:[/bold cyan]", summary.author)
    if summary.publish_date:
        table.add_row("[bold cyan]Date:[/bold cyan]", summary.publish_date)
    console.print(table)
    console.print()
    
    # Summary Paragraph
    console.print(Panel(summary.summary, title="[bold yellow]Overview[/bold yellow]", border_style="yellow"))
    console.print()
    
    # Key Points
    console.print("[bold cyan]Key Points & Insights:[/bold cyan]")
    for point in summary.key_points:
        console.print(f" • {point}")
    console.print()
    
    # Key Takeaway
    console.print(Panel(
        f"[bold white]{summary.key_takeaway}[/bold white]",
        title="[bold green]Key Takeaway[/bold green]",
        border_style="green"
    ))
    console.print()

def get_multiline_input() -> str:
    """Collect multiline text from standard input."""
    console.print("[cyan]Paste or type the blog text below. Press Ctrl+D (or type 'EOF' on a new line) to finish:[/cyan]")
    lines = []
    while True:
        try:
            line = input()
            if line == "EOF":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)

def load_blog_content(source_input: str, is_raw_text: bool) -> tuple[str, str]:
    """Pre-fetch or pre-read blog content to optimize performance."""
    if is_raw_text or (len(source_input.split()) > 10 and not source_input.startswith("http")):
        return source_input, "pasted content"
    
    if source_input.startswith("http://") or source_input.startswith("https://"):
        console.print(f"[dim]Fetching URL: {source_input}...[/dim]")
        content = fetch_blog_post(source_input)
        return content, f"URL ({source_input})"
    
    resolved_path = resolve_file_path(source_input)
    if resolved_path:
        console.print(f"[dim]Reading local file: {resolved_path}...[/dim]")
        content = read_local_file(resolved_path)
        return content, f"File ({resolved_path})"
        
    return "", ""

def run_agent_query(source_input: str, is_raw_text: bool = False):
    """Run the summarizer agent against the pre-loaded content for 1-turn fast execution."""
    content, source_desc = load_blog_content(source_input, is_raw_text)
    
    if not content or content.startswith("Error"):
        console.print(f"[bold red]Failed to load content:[/bold red] {content or 'Invalid URL or file path'}")
        return

    # Limit text length to 10,000 chars for fast prefill on local Ollama
    if len(content) > 10000:
        content = content[:10000] + "\n\n[Content truncated for summary performance...]"

    console.print(Panel(f"[bold blue]Summarizing {source_desc}...[/bold blue]", expand=False))
    query = f"Please summarize the following blog post content:\n\n{content}"
        
    with console.status("[bold green]Agent generating summary (fast 1-turn)...", spinner="dots"):
        try:
            # Run the wrapped agent with observability
            result = wrapped_agent.run_sync(query)
            output = result.output
        except Exception as e:
            console.print(f"[bold red]Error running agent:[/bold red] {e}")
            return
            
    if isinstance(output, BlogSummary):
        display_summary(output)
    else:
        console.print("\n[bold yellow]Warning: Received unstructured output from agent:[/bold yellow]")
        console.print(output)

def main():
    # If content is piped or redirected to stdin, read it directly
    if not sys.stdin.isatty():
        piped_text = sys.stdin.read().strip()
        if piped_text:
            run_agent_query(piped_text, is_raw_text=True)
            return

    # Check command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["-t", "--text"] and len(sys.argv) > 2:
            raw_text = " ".join(sys.argv[2:])
            run_agent_query(raw_text, is_raw_text=True)
        else:
            source_input = sys.argv[1]
            run_agent_query(source_input)
    else:
        console.print(Panel.fit(
            "[bold magenta]Welcome to the Pydantic AI Blog Summarizer Agent[/bold magenta]\n"
            "Options:\n"
            "  1. Enter a blog URL (starts with http/https)\n"
            "  2. Enter a file path/name (resolves locally or in BLOGS_DIR)\n"
            "  3. Type [bold yellow]paste[/bold yellow] to paste raw blog text directly\n"
            "  4. Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to leave.",
            title="Blog Summarizer CLI",
            border_style="magenta"
        ))
        while True:
            try:
                source_input = Prompt.ask("[bold cyan]Enter choice, URL, or File Path[/bold cyan]").strip()
                if source_input.lower() in ["exit", "quit"]:
                    console.print("[bold yellow]Goodbye![/bold yellow]")
                    break
                if not source_input:
                    continue
                
                if source_input.lower() == "paste":
                    raw_text = get_multiline_input()
                    if raw_text.strip():
                        run_agent_query(raw_text, is_raw_text=True)
                    else:
                        console.print("[yellow]Empty content. Aborted.[/yellow]")
                else:
                    run_agent_query(source_input)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold yellow]Goodbye![/bold yellow]")
                break

if __name__ == "__main__":
    main()
