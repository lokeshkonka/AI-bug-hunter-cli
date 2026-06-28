from typing import Optional, List, Dict, Any
from bughunter.storage.base import BaseStore
import json
from bughunter.models.finding import Finding, Severity, Confidence
import uuid
from datetime import datetime, timezone

class FindingStore(BaseStore):
    async def insert_finding(self, finding: Finding):
        async with self.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO findings (
                    id, run_id, title, severity, confidence, category, 
                    affected_component, evidence_ids, impact, reproduction_steps, 
                    recommendation, retest_steps, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding.id, finding.run_id, finding.title, finding.severity.value,
                    finding.confidence.value, finding.category, finding.affected_component,
                    json.dumps(finding.evidence_ids), finding.impact, finding.reproduction_steps,
                    finding.recommendation, finding.retest_steps, "open", finding.created_at
                )
            )

    async def get_run_findings(self, run_id: str) -> List[Finding]:
        findings = []
        async with self.get_connection() as conn:
            async with conn.execute("SELECT * FROM findings WHERE run_id = ?", (run_id,)) as cursor:
                async for row in cursor:
                    findings.append(Finding(
                        id=row["id"],
                        run_id=row["run_id"],
                        title=row["title"],
                        severity=Severity(row["severity"]),
                        confidence=Confidence(row["confidence"]),
                        category=row["category"],
                        affected_component=row["affected_component"],
                        evidence_ids=json.loads(row["evidence_ids"]) if row["evidence_ids"] else [],
                        impact=row["impact"],
                        reproduction_steps=row["reproduction_steps"],
                        recommendation=row["recommendation"],
                        retest_steps=row["retest_steps"],
                        created_at=row["created_at"]
                    ))
        return findings
