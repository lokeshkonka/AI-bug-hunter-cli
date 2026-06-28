from textual.widgets import Static, Label, ProgressBar
from textual.containers import VerticalScroll, Vertical
from bughunter.models.event import BugHunterEvent

class FindingCard(Vertical):
    def __init__(self, title: str, severity: str, score: float):
        super().__init__()
        self.title = title
        self.severity = severity
        self.score = score
        self.add_class(f"finding-{severity.lower()}")

    def compose(self):
        yield Label(f"[{self.severity}] {self.title}", classes="finding_title")
        yield Label(f"VulnScore: {self.score}")
        yield ProgressBar(total=100, progress=self.score, show_eta=False)

class FindingsStreamWidget(VerticalScroll):
    def compose(self):
        yield Label("Findings", classes="panel_title")

    def add_finding(self, event: BugHunterEvent):
        meta = event.metadata or {}
        severity = meta.get("severity", "INFO")
        score = meta.get("score", 50.0)
        card = FindingCard(event.message, severity, score)
        self.mount(card)
