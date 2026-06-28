from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Log, ProgressBar, Label
from bughunter.core.events.bus import AsyncEventBus
from bughunter.models.event import BugHunterEvent, EventType
import asyncio

from .widgets.feed import AgentFeedWidget
from .widgets.tracker import PhaseTrackerWidget
from .widgets.findings import FindingsStreamWidget
from .widgets.summary import ScoreSummaryWidget

class BugHunterHeader(Static):
    def compose(self) -> ComposeResult:
        yield Label("Bug Hunter CLI - Agentic Vulnerability Scanner", id="title")

class BugHunterFooter(Static):
    def compose(self) -> ComposeResult:
        yield Label("Status: Running | Press 'q' to quit", id="footer_status")

class BugHunterApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("s", "toggle_summary", "Toggle Summary"),
    ]

    def __init__(self, event_bus: AsyncEventBus):
        super().__init__()
        self.event_bus = event_bus
        self._quit_count = 0

    def compose(self) -> ComposeResult:
        yield BugHunterHeader()
        with Horizontal():
            with Vertical(id="left_panel"):
                yield PhaseTrackerWidget()
                yield AgentFeedWidget()
            with Vertical(id="main_panel"):
                yield FindingsStreamWidget()
            with Vertical(id="right_panel"):
                yield ScoreSummaryWidget()
        yield BugHunterFooter()

    def on_mount(self) -> None:
        self.event_bus.subscribe_all(self.handle_event)

    async def handle_event(self, event: BugHunterEvent) -> None:
        feed = self.query_one(AgentFeedWidget)
        tracker = self.query_one(PhaseTrackerWidget)
        findings = self.query_one(FindingsStreamWidget)
        summary = self.query_one(ScoreSummaryWidget)

        # Dispatch events to appropriate widgets
        if event.type == EventType.phase_started:
            tracker.update_phase(event.message)
        elif event.type == EventType.finding_confirmed:
            findings.add_finding(event)
            summary.update_stats(event)
        
        feed.add_event(event)

    def action_quit_app(self) -> None:
        self._quit_count += 1
        if self._quit_count >= 2:
            self.exit()
        else:
            try:
                footer = self.query_one("#footer_status", Label)
                footer.update("Status: Running | Press 'q' AGAIN to abort scan")
            except:
                self.exit()
