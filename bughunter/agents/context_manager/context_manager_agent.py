from typing import List, Dict, Any, Optional
import tiktoken
from bughunter.storage.recon_store import ReconStore
from bughunter.storage.provider_store import ProviderStore
from bughunter.models.run import Run
from bughunter.core.events.emitter import AgentEventEmitter
from bughunter.models.event import EventType

class ContextManagerAgent:
    def __init__(self, run: Run, db_path: str, emitter: AgentEventEmitter):
        self.run = run
        self.db_path = db_path
        self.recon_store = ReconStore(db_path)
        self.provider_store = ProviderStore(db_path)
        self.emitter = emitter
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.summary_cache = {}
        
    def estimate_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))
        
    async def check_budget(self, agent: str, estimated_tokens: int) -> bool:
        usage = await self.provider_store.get_total_usage(self.run.id)
        current_tokens = usage["total_tokens"]
        current_cost = usage["total_cost"]
        
        if current_tokens + estimated_tokens > self.run.token_budget:
            await self.emitter.emit(self.run.id, EventType.error, f"Budget exhausted: {current_tokens + estimated_tokens} > {self.run.token_budget}")
            return False
            
        if current_cost > self.run.cost_budget_usd:
            await self.emitter.emit(self.run.id, EventType.error, f"Cost budget exhausted: ${current_cost} > ${self.run.cost_budget_usd}")
            return False
            
        return True

    async def select_snippets(self, tags: List[str], max_tokens: int) -> str:
        entries = await self.recon_store.get_index_entries_by_tags(self.run.id, tags)
        # Sort by relevance score
        entries.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        selected_text = ""
        current_tokens = 0
        
        for entry in entries:
            # Read snippet from file
            # In a real impl, we should cache file contents or read exact lines
            # For this MVP, let's format it.
            snippet = f"File: {entry['file_path']} (Lines {entry['line_start']}-{entry['line_end']})\n"
            snippet += f"Tags: {entry['tags']}\n"
            snippet += f"Security relevance: {entry['security_relevance']}\n"
            snippet += "---\n"
            
            try:
                with open(entry['file_path'], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # 1-indexed
                    start = max(0, entry['line_start'] - 1)
                    end = min(len(lines), entry['line_end'])
                    snippet += "".join(lines[start:end])
            except Exception:
                snippet += "[Error reading file snippet]\n"
                
            snippet += "---\n\n"
            
            est = self.estimate_tokens(snippet)
            if current_tokens + est > max_tokens:
                break
                
            selected_text += snippet
            current_tokens += est
            
        return selected_text
