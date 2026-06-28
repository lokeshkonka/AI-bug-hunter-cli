from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from bughunter.core.events.emitter import AgentEventEmitter
from bughunter.models.event import EventType
import asyncio

class BugHunterState(TypedDict):
    run_id: str
    scope_path: str
    scope: Any
    manifest: Any
    test_plans: List[str]
    findings: List[Any]
    evidence_list: List[Any]
    scored_findings: List[Any]
    fix_guidance: Dict[str, Any]
    report_path: str
    phase: str
    errors: List[str]

class WorkflowGraph:
    def __init__(self, run_id: str, emitter: AgentEventEmitter, db_path: str):
        self.run_id = run_id
        self.emitter = emitter
        self.db_path = db_path
        
    async def load_scope_node(self, state: BugHunterState):
        await self.emitter.emit(self.run_id, EventType.phase_started, "Loading Scope")
        from bughunter.core.safety.scope_validator import ScopeValidator
        try:
            scope = ScopeValidator.load_and_validate(state["scope_path"])
            return {"scope": scope, "phase": "load_scope"}
        except Exception as e:
            return {"errors": [f"Scope error: {e}"]}

    async def recon_node(self, state: BugHunterState):
        from bughunter.agents.recon.recon_agent import ReconAgent
        recon = ReconAgent(self.run_id, self.emitter, self.db_path)
        manifest = await recon.run(state["scope"].project.repo_path)
        return {"manifest": manifest, "phase": "recon"}

    async def static_audit_node(self, state: BugHunterState):
        from bughunter.agents.static_audit.static_audit_agent import StaticAuditAgent
        from bughunter.models.run import Run
        run = Run(
            id=self.run_id,
            scope_path=state["scope_path"],
            token_budget=state["scope"].cost.max_tokens_per_run,
            cost_budget_usd=state["scope"].cost.max_cost_usd
        )
        static_audit = StaticAuditAgent(run, self.db_path, self.emitter, scope=state.get("scope"))
        await static_audit.run_audit(state["scope"].project.repo_path)
        return {"phase": "static_audit"}

    async def sca_audit_node(self, state: BugHunterState):
        from bughunter.agents.dependency_audit.sca_agent import DependencyAuditAgent
        sca_agent = DependencyAuditAgent(self.run_id, self.emitter, self.db_path)
        await sca_agent.run_audit(state["scope"].project.repo_path)
        return {"phase": "sca_audit"}

    async def planner_node(self, state: BugHunterState):
        from bughunter.agents.planner.planner_agent import PlannerAgent
        
        if not state["scope"].targets.urls:
            await self.emitter.emit(self.run_id, EventType.tool_progress, "No target URLs defined. Skipping dynamic test plan generation.")
            return {"test_plans": [], "phase": "planner"}
            
        planner = PlannerAgent(self.run_id, self.emitter, self.db_path)
        test_plans = await planner.generate_test_plans(f".bughunter/runs/{self.run_id}/index.md")
        return {"test_plans": test_plans, "phase": "planner"}

    async def dynamic_test_node(self, state: BugHunterState):
        from bughunter.agents.dynamic_test.dynamic_test_agent import DynamicTestAgent
        from bughunter.core.http.client import ScopedHttpClient
        from bughunter.core.safety.engine import SafetyPolicyEngine
        safety_engine = SafetyPolicyEngine(state["scope"])
        http_client = ScopedHttpClient(safety_engine, self.emitter, self.run_id)
        dynamic_tester = DynamicTestAgent(self.run_id, self.emitter, http_client, self.db_path)
        
        for plan in state.get("test_plans", []):
            await dynamic_tester.execute_test_plan(plan, state["scope"])
            
        await http_client.close()
        return {"phase": "dynamic_test"}

    async def score_findings_node(self, state: BugHunterState):
        from bughunter.agents.vuln_scoring.agent import VulnScoringAgent
        from bughunter.storage.finding_store import FindingStore
        
        finding_store = FindingStore(self.db_path)
        findings = await finding_store.get_run_findings(self.run_id)
        scorer = VulnScoringAgent(self.run_id, self.emitter)
        
        scored = []
        for finding in findings:
            # We would normally look up evidence from EvidenceAgent
            evidence = []
            score = await scorer.score_finding(finding, evidence)
            scored.append({"finding": finding, "score": score})
            
        return {"scored_findings": scored, "findings": findings, "phase": "scoring"}

    async def fix_generate_node(self, state: BugHunterState):
        from bughunter.agents.fix.agent import FixAgent
        fix_agent = FixAgent(self.run_id, self.emitter)
        
        fix_guidance = {}
        for item in state.get("scored_findings", []):
            finding = item["finding"]
            fix = await fix_agent.generate_fix(finding)
            fix_guidance[finding.id] = fix
            
        return {"fix_guidance": fix_guidance, "phase": "fix"}

    async def report_write_node(self, state: BugHunterState):
        await self.emitter.emit(self.run_id, EventType.phase_started, "Report Generation")
        from bughunter.reports.markdown import MarkdownExporter
        from pathlib import Path
        
        report_dir = Path(".bughunter/reports")
        report_path = MarkdownExporter.export(self.run_id, state.get("findings", []), state.get("evidence_list", []), str(report_dir))
        
        await self.emitter.emit(self.run_id, EventType.report_written, "Report generated", {"path": report_path})
        return {"report_path": report_path, "phase": "reporting"}

    def build_graph(self):
        workflow = StateGraph(BugHunterState)
        
        workflow.add_node("load_scope", self.load_scope_node)
        workflow.add_node("recon", self.recon_node)
        workflow.add_node("static_audit", self.static_audit_node)
        workflow.add_node("sca_audit", self.sca_audit_node)
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("dynamic_test", self.dynamic_test_node)
        workflow.add_node("score_findings", self.score_findings_node)
        workflow.add_node("fix_generate", self.fix_generate_node)
        workflow.add_node("report_write", self.report_write_node)
        
        workflow.set_entry_point("load_scope")
        workflow.add_edge("load_scope", "recon")
        workflow.add_edge("recon", "static_audit")
        workflow.add_edge("static_audit", "sca_audit")
        workflow.add_edge("sca_audit", "planner")
        workflow.add_edge("planner", "dynamic_test")
        workflow.add_edge("dynamic_test", "score_findings")
        workflow.add_edge("score_findings", "fix_generate")
        workflow.add_edge("fix_generate", "report_write")
        workflow.add_edge("report_write", END)
        
        return workflow.compile()
