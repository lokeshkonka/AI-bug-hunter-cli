import os
os.environ["TQDM_DISABLE"] = "1"

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.markdown import Markdown
from pathlib import Path
import asyncio
import warnings

# Suppress Langchain/Pydantic V1 warnings for Python 3.14+
warnings.filterwarnings("ignore", message=".*Pydantic V1.*")

console = Console()

def start_interactive_session():
    from rich.align import Align
    from bughunter.config_manager import ConfigManager
    
    logo = r'''

    
██████╗ ██╗   ██╗ ██████╗  ██████╗██╗   ██╗    ██████╗██╗     ██╗
██╔══██╗██║   ██║██╔════╝ ██╔════╝╚██╗ ██╔╝   ██╔════╝██║     ██║
██████╔╝██║   ██║██║  ███╗██║  ███╗╚████╔╝    ██║     ██║     ██║
██╔══██╗██║   ██║██║   ██║██║   ██║ ╚██╔╝     ██║     ██║     ██║
██████╔╝╚██████╔╝╚██████╔╝╚██████╔╝  ██║      ╚██████╗███████╗██║
╚═════╝  ╚═════╝  ╚═════╝  ╚═════╝   ╚═╝       ╚═════╝╚══════╝╚═╝ v1


'''
    console.print(logo.strip("\n"), style="bold cyan")
    
    config = ConfigManager.load()
    active_model = "None"
    if config.active_profile and config.active_profile in config.profiles:
        active_model = config.profiles[config.active_profile].model
        
    console.print()
    console.print(Align.right(f"[italic yellow]Active Model: {active_model}[/italic yellow]"))
    console.print()
    console.print("Hey ! Bug Hunter CLI [green]/commands[/green] to get all info !\n")
    # Initialize VectorStore
    try:
        from bughunter.storage.vector_store import VectorStore
        vs = VectorStore()
    except Exception as e:
        console.print(f"[yellow]VectorStore not available: {e}[/yellow]")
        vs = None

    from bughunter.config_manager import ConfigManager
    if not ConfigManager.get_active_profile():
        console.print("\\n[bold yellow]No API key configured![/bold yellow]")
        console.print("Let's set up your first API key profile.\\n")
        import os
        os.system("bughunter config")
        # Re-check after setup
        if not ConfigManager.get_active_profile():
            console.print("[red]Setup cancelled or failed. Exiting...[/red]")
            return

    # Add folder selection and trust prompt
    import questionary
    from pathlib import Path
    import os
    
    target_folder = questionary.path(
        "Could you clarify which folder the project is present?",
        default=os.getcwd()
    ).ask()
    
    if not target_folder:
        console.print("[red]No folder selected. Exiting...[/red]")
        return
        
    is_trusted = questionary.confirm(
        f"Do you trust the contents of this folder '{target_folder}'?",
        default=False
    ).ask()
    
    if not is_trusted:
        console.print("[red]Security aborted: Folder is not trusted. Exiting...[/red]")
        return
        
    os.chdir(target_folder)
    console.print(f"[green]Working directory set to {target_folder}[/green]\\n")

    while True:
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
            from prompt_toolkit.styles import Style
            from prompt_toolkit.key_binding import KeyBindings
            
            class CommandSuggest(AutoSuggest):
                def __init__(self, commands):
                    self.commands = commands
                    
                def get_suggestion(self, buffer, document):
                    text = document.text
                    if not text:
                        return None
                        
                    if text.startswith("/scan "):
                        prefix = text[6:]
                        import os
                        from pathlib import Path
                        
                        # Default suggestion
                        if not prefix and Path("bughunter-scope.yml").exists():
                            return Suggestion("bughunter-scope.yml")
                            
                        search_dir = Path(prefix).parent if '/' in prefix else Path('.')
                        name_prefix = Path(prefix).name if not prefix.endswith('/') else ""
                        
                        try:
                            if search_dir.exists() and search_dir.is_dir():
                                # Sort to prioritize files over hidden/internal dirs
                                matches = sorted([
                                    p.name + ('/' if p.is_dir() else '') 
                                    for p in search_dir.iterdir() 
                                    if p.name.startswith(name_prefix)
                                ])
                                if matches:
                                    return Suggestion(matches[0][len(name_prefix):])
                        except Exception:
                            pass
                        return None

                    for cmd in self.commands:
                        if cmd.lower().startswith(text.lower()) and len(cmd) > len(text):
                            return Suggestion(cmd[len(text):])
                    return None

            commands = [
                "/scan", "/index", "/config", "/commands", "/help", "/clear", "/exit", "/quit"
            ]
            
            custom_style = Style.from_dict({
                'prompt': 'ansicyan bold',
                'auto-suggestion': 'fg:#666666 bg:default',
            })
            
            bindings = KeyBindings()
            @bindings.add('tab')
            def _(event):
                b = event.app.current_buffer
                if b.suggestion:
                    b.insert_text(b.suggestion.text)
                    
            session = PromptSession(
                "❯ ",
                auto_suggest=CommandSuggest(commands),
                style=custom_style,
                key_bindings=bindings
            )
            
            console.print()
            user_input = session.prompt()
            
            if not user_input or not user_input.strip():
                continue
                
            console.print()
                
            if user_input.strip() == "/exit" or user_input.strip() == "/quit":
                break
            elif user_input.strip() == "/clear":
                console.clear()
            elif user_input.strip().startswith("/scan"):
                console.print("[bold yellow]Starting scan...[/bold yellow]")
                from bughunter.cli import run_scan_async
                scope_path = "bughunter-scope.yml"
                parts = user_input.split()
                if len(parts) > 1:
                    scope_path = parts[1]
                    
                if not Path(scope_path).exists():
                    console.print(f"[yellow]Scope file {scope_path} not found. Creating a default one...[/yellow]")
                    default_scope = f"""project:
  name: interactive-scan
  repo_path: .

targets:
  urls: []
  hosts: []

scan:
  mode: safe-active
  max_requests_per_minute: 60
  max_depth: 2
  max_concurrency: 5

cost:
  max_tokens_per_run: 200000
  max_tokens_per_test: 15000
  max_cost_usd: 1.00
  warn_at_percent: 80

ci:
  fail_on_score: 80
  fail_on_cost_usd: 1.00
  fail_on_tier: "high"
"""
                    Path(scope_path).write_text(default_scope)
                    
                asyncio.run(run_scan_async(scope_path))
            elif user_input.strip() == "/index":
                if vs:
                    console.print("[bold yellow]Indexing codebase into local Vector DB...[/bold yellow]")
                    with console.status("[bold green]Chunking and embedding files..."):
                        chunks_indexed = vs.ingest_directory(".")
                    console.print(f"[bold green]Successfully indexed {chunks_indexed} file chunks![/bold green]")
                else:
                    console.print("[red]VectorStore is not initialized.[/red]")
            elif user_input.strip().startswith("bughunter ") or user_input.strip().startswith("/config"):
                cmd = user_input.strip()
                if cmd.startswith("/config"):
                    cmd = cmd.replace("/config", "bughunter config", 1)
                import os
                os.system(cmd)
            elif user_input.strip() == "/commands" or user_input.strip() == "/help":
                console.print(Markdown("""
**Available Commands:**
- `/scan [scope_file]`: Run a security scan
- `/index`: Ingest current codebase into Vector DB for RAG
- `/config`: Manage API keys and profiles
- `/commands` or `/help`: Show this list of available commands
- `/clear`: Clear the terminal screen
- `/exit` or `/quit`: Exit the interactive session
                """))
            elif user_input.startswith("/"):
                console.print(f"[red]Unknown command: {user_input}[/red]. Type /help for available commands.")
            else:
                handle_question(user_input, vs)
                
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Exiting...[/bold red]")
            break

def handle_question(question: str, vs=None):
    from bughunter.config_manager import ConfigManager
    profile = ConfigManager.get_active_profile()
    
    if not profile:
        console.print("[yellow]No active API profile found. Use 'bughunter config add' to set one up.[/yellow]")
        return
        
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        
        llm = None
        if profile.provider.lower() == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=profile.model, api_key=profile.api_key)
        elif profile.provider.lower() in ["groq", "grok"]:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=profile.model, 
                api_key=profile.api_key, 
                base_url="https://api.groq.com/openai/v1" if profile.provider.lower() == "groq" else "https://api.x.ai/v1"
            )
        elif profile.provider.lower() == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model=profile.model, google_api_key=profile.api_key)
        else:
            console.print(f"[red]Unsupported provider: {profile.provider}[/red]")
            return
            
        context = "No project context available."
        
        # Inject context from Vector DB if available
        if vs:
            search_results = vs.search(question, n_results=5)
            if search_results:
                context = "Retrieved Codebase Context:\\n\\n" + "\\n".join(search_results)
        
        # Inject scope if available, else inject default template
        if Path("bughunter-scope.yml").exists():
            context += f"\\n\\nScope File Context (Currently exists):\\n{Path('bughunter-scope.yml').read_text()}"
        else:
            default_template = """project:
  name: interactive-scan
  repo_path: .
targets:
  urls: []
  hosts: []
scan:
  mode: safe-active
  max_requests_per_minute: 60
  max_depth: 2
  max_concurrency: 5
cost:
  max_tokens_per_run: 200000
  max_tokens_per_test: 15000
  max_cost_usd: 1.00
  warn_at_percent: 80
ci:
  fail_on_score: 80
  fail_on_cost_usd: 1.00
  fail_on_tier: "high"
"""
            context += f"\\n\\nThe default scope file is named 'bughunter-scope.yml' and uses YAML format. Example template:\\n{default_template}"
            
        # Inject latest scan report
        reports_dir = Path(".bughunter/reports")
        report_context = ""
        if reports_dir.exists():
            reports = list(reports_dir.glob("*.md"))
            if reports:
                latest_report = max(reports, key=os.path.getctime)
                report_content = latest_report.read_text()
                if len(report_content) > 25000:
                    report_content = report_content[:25000] + "\\n... (truncated)"
                report_context = f"\\n\\nLATEST SCAN REPORT ({latest_report.name}):\\n{report_content}"
                
        commands_info = """
AVAILABLE COMMANDS:
- `/scan [scope_file]`: Run a security scan. The user can press 'q' twice to cancel mid-flight.
- `/index`: Ingest current codebase into Vector DB for RAG.
- `/config`: Manage API keys and profiles.
- `/commands` or `/help`: Show this list of available commands.
- `/clear`: Clear the terminal screen.
- `/exit` or `/quit`: Exit the interactive session.
"""

        messages = [
            SystemMessage(content=f"You are the Bug Hunter CLI expert assistant. You have full access to the project context, recent security scan reports, and CLI commands.\\n\\n{commands_info}\\n\\nYour job is to explain how to use the tool, describe recent scans in detail, answer 'what', 'how', and 'why' questions, and guide the user through their security vulnerabilities one by one if asked.\\nIf the user asks you to create a scope file, USE the create_scope_file tool directly to create it for them!\\n\\nCONTEXT:\\n{context}{report_context}"),
            HumanMessage(content=question)
        ]
        
        from langchain_core.tools import tool
        
        @tool
        def create_scope_file(file_content: str, filename: str = "bughunter-scope.yml") -> str:
            """Create a scope file for Bug Hunter CLI with the provided YAML content."""
            try:
                Path(filename).write_text(file_content)
                return f"Successfully created scope file: {filename}"
            except Exception as e:
                return f"Error creating file: {str(e)}"
                
        tools = [create_scope_file]
        
        from rich.rule import Rule
        import time
        from concurrent.futures import ThreadPoolExecutor
        
        def run_agent():
            try:
                from langgraph.prebuilt import create_react_agent
                agent = create_react_agent(llm, tools)
                result = agent.invoke({"messages": messages})
                return result["messages"][-1].content
            except Exception as tool_err:
                # Fallback to basic invoke if model doesn't support tools natively
                return llm.invoke(messages).content

        start_time = time.time()
        with console.status("[bold green]Thinking... 0s") as status:
            with ThreadPoolExecutor() as executor:
                future = executor.submit(run_agent)
                while not future.done():
                    elapsed = time.time() - start_time
                    if elapsed < 60:
                        elapsed_str = f"{int(elapsed)}s"
                    else:
                        elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
                    status.update(f"[bold green]Thinking... {elapsed_str}")
                    time.sleep(0.1)
                response_content = future.result()
            
        console.print(Rule(style="dim cyan"))
        console.print(Markdown(response_content))
        console.print(Rule(style="dim cyan"))
    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
    except Exception as e:
        error_msg = str(e)
        if "Model not found" in error_msg or "invalid-argument" in error_msg or "404" in error_msg:
            console.print(f"\\n[red]API Error: The configured model '{profile.model}' was not found or is invalid for this provider.[/red]")
            console.print("Type [green]/config[/green] or [green]bughunter config[/green] to set up a new profile with a valid model.\\n")
        else:
            console.print(f"[red]Error communicating with AI: {e}[/red]")
