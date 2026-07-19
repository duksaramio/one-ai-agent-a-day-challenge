import sys
import asyncio
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from obsidian_reader.agent import wrapped_agent

console = Console()

def run_agent_query(query: str):
    """Run a single query against the agent and print the result."""
    console.print(Panel(f"[bold blue]Running Agent Query:[/bold blue] {query}", expand=False))
    
    with console.status("[bold green]Agent thinking and reading Obsidian vault...", spinner="dots"):
        try:
            # Run the wrapped agent with observability
            result = wrapped_agent.run_sync(query)
            output = result.output
        except Exception as e:
            console.print(f"[bold red]Error running agent:[/bold red] {e}")
            return
            
    console.print("\n[bold green]=== Agent Response ===[/bold green]")
    # Render response as Markdown for beautiful display
    console.print(Markdown(str(output)))
    console.print("[bold green]======================[/bold green]\n")

def interactive_loop():
    """Start an interactive chat session with the Obsidian Reader Agent."""
    console.print(Panel.fit(
        "[bold magenta]Welcome to the Obsidian Reader Agent CLI[/bold magenta]\n"
        "Ask questions about your notes, search files, or summarize folders.\n"
        "Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to leave.",
        title="Obsidian Reader",
        border_style="magenta"
    ))
    
    while True:
        try:
            query = Prompt.ask("[bold cyan]You[/bold cyan]")
            if query.strip().lower() in ["exit", "quit"]:
                console.print("[bold yellow]Goodbye![/bold yellow]")
                break
            if not query.strip():
                continue
                
            run_agent_query(query)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Goodbye![/bold yellow]")
            break

def main():
    # Check if a query was passed as command line arguments
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        run_agent_query(query)
    else:
        interactive_loop()

if __name__ == "__main__":
    main()
