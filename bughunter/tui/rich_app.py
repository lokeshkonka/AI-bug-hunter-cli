from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.spinner import Spinner
from typing import List, Dict
import asyncio
from bughunter.models.event import BugHunterEvent, EventType
from bughunter.core.events.bus import AsyncEventBus

class RichTui:
    """A Rich-based streaming terminal UI for Phase 1."""
    def __init__(self, event_bus: AsyncEventBus):
        self.event_bus = event_bus
        self.console = Console()
        self.events: List[BugHunterEvent] = []
        self.status = "Scanning"
        self.current_phase = "Initialization"
        self.findings_count: Dict[str, int] = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0
        }
        self.report_path = ""
        self.event_bus.subscribe_all(self._handle_event)
        self.refresh_task = None
        self._stop_event = asyncio.Event()

    async def _handle_event(self, event: BugHunterEvent):
        self.events.append(event)
        if len(self.events) > 20:
            self.events.pop(0)

        if event.type == EventType.phase_started:
            self.current_phase = event.message
        elif event.type == EventType.finding_confirmed:
            severity = event.metadata.get("severity", "LOW").upper()
            if severity in self.findings_count:
                self.findings_count[severity] += 1
        elif event.type == EventType.report_written:
            self.report_path = event.metadata.get("path", "")
            self.status = "Completed"
            self._stop_event.set()
        elif event.type == EventType.error:
            # We log it, but we don't stop the TUI. The orchestrator decides when to stop.
            pass

    def _generate_layout(self) -> Panel:
        table = Table.grid(expand=True)
        table.add_column()
        
        import time
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()
            
        elapsed = time.time() - self.start_time
        if elapsed < 60:
            elapsed_str = f"{int(elapsed)}s"
        else:
            elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
            
        # Header
        header_text = f"Status: {self.status} | Phase: {self.current_phase} | Elapsed: {elapsed_str}"
        if self.status == "Scanning":
            header = Spinner("dots", text=header_text)
        else:
            header = Text(header_text, style="bold")
        table.add_row(header)
        table.add_row("")

        # Findings
        findings_text = Text(f"Findings - CRITICAL: {self.findings_count['CRITICAL']} | HIGH: {self.findings_count['HIGH']} | MEDIUM: {self.findings_count['MEDIUM']} | LOW: {self.findings_count['LOW']}")
        table.add_row(findings_text)
        table.add_row("")

        # Report Path
        if self.report_path:
            table.add_row(Text(f"Report written to: {self.report_path}", style="bold green"))
            table.add_row("")

        # Logs
        log_table = Table(show_header=False, expand=True, box=None)
        for evt in self.events:
            time_str = evt.timestamp.split("T")[1][:8] if "T" in evt.timestamp else evt.timestamp
            color = "cyan"
            if evt.type == EventType.error:
                color = "red"
            elif evt.type == EventType.finding_confirmed:
                color = "magenta"
            elif evt.type == EventType.policy_violation:
                color = "yellow"
            
            log_table.add_row(
                Text(f"[{time_str}]", style="dim"),
                Text(f"[{evt.agent}]", style="blue"),
                Text(evt.message, style=color)
            )
        
        table.add_row(Panel(log_table, title="Recent Events", border_style="dim"))

        return Panel(table, title="Bug Hunter CLI", border_style="blue")

    async def run(self):
        with Live(self._generate_layout(), refresh_per_second=4, console=self.console) as live:
            # Wait for stop event or maximum timeout
            try:
                while not self._stop_event.is_set():
                    live.update(self._generate_layout())
                    # Check every 250ms
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=0.25)
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                pass
            finally:
                # Final update
                live.update(self._generate_layout())
