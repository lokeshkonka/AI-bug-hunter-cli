from mcp.server.fastmcp import FastMCP
from typing import List, Optional
import os
import asyncio
from pathlib import Path

mcp = FastMCP("BugHunter")

@mcp.tool()
def create_scope_file(project_name: str, repo_path: str, target_urls: List[str] = []) -> str:
    """Create a bughunter-scope.yml file for a new scan."""
    scope_content = f"""project:
  name: {project_name}
  repo_path: {repo_path}
targets:
  urls: {target_urls}
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
    scope_path = Path("bughunter-scope.yml")
    scope_path.write_text(scope_content)
    return f"Successfully created {scope_path.absolute()}"

@mcp.tool()
def start_scan(scope_path: str = "bughunter-scope.yml") -> str:
    """Start a Bug Hunter CLI scan using the specified scope file. Runs in CI mode."""
    from bughunter.cli import run_scan_async
    try:
        ret = asyncio.run(run_scan_async(scope_path, True, False, True))
        return f"Scan completed with exit code {ret}."
    except Exception as e:
        return f"Scan failed: {str(e)}"

@mcp.tool()
def list_findings(run_id: str) -> str:
    """List all findings for a specific run ID."""
    from bughunter.storage.finding_store import FindingStore
    import json
    
    db_path = ".bughunter/bughunter.db"
    if not os.path.exists(db_path):
        return "No database found. Run a scan first."
        
    store = FindingStore(db_path)
    
    async def get_f():
        return await store.get_run_findings(run_id)
        
    findings = asyncio.run(get_f())
    if not findings:
        return f"No findings found for run {run_id}"
        
    result = []
    for f in findings:
        result.append({
            "id": f.id,
            "title": f.title,
            "severity": f.severity.value,
            "confidence": f.confidence.value,
            "category": f.category,
            "component": f.affected_component
        })
    return json.dumps(result, indent=2)

@mcp.tool()
def get_report_content(run_id: str) -> str:
    """Get the full markdown content of the generated report for a run."""
    reports_dir = Path(".bughunter/reports")
    if not reports_dir.exists():
        return "No reports directory found."
        
    for report_file in reports_dir.glob(f"bug-report-{run_id[:8]}*.md"):
        return report_file.read_text()
        
    return f"Report for run {run_id} not found."

if __name__ == "__main__":
    mcp.run()
