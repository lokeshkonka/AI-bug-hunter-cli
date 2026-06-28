import asyncio
import time
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import httpx
from bughunter.core.safety.engine import SafetyPolicyEngine
from bughunter.models.event import EventType

class RateLimitExceeded(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.2f}s")

class TokenBucket:
    def __init__(self, tokens_per_minute: int):
        self.capacity = tokens_per_minute
        self.tokens = float(tokens_per_minute)
        self.fill_rate = tokens_per_minute / 60.0
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
            self.last_update = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def wait_time(self) -> float:
        async with self._lock:
            if self.tokens >= 1:
                return 0.0
            return (1.0 - self.tokens) / self.fill_rate

class ScopedHttpClient:
    """HTTP Client that enforces scope, rate limiting, and safety policies."""
    
    def __init__(self, safety_engine: SafetyPolicyEngine, emitter=None, run_id=None):
        self.safety = safety_engine
        self.emitter = emitter
        self.run_id = run_id
        self.buckets: Dict[str, TokenBucket] = {}
        self.client = httpx.AsyncClient(verify=False) # Often needed for testing lab environments
        self._lock = asyncio.Lock()
        
    def _get_bucket(self, hostname: str) -> TokenBucket:
        if hostname not in self.buckets:
            limit = self.safety.scope.scan.max_requests_per_minute
            self.buckets[hostname] = TokenBucket(limit)
        return self.buckets[hostname]

    async def _check_rate_limit(self, url: str):
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"Invalid URL: {url}")
            
        bucket = self._get_bucket(hostname)
        if not await bucket.consume(1):
            wait_t = await bucket.wait_time()
            if self.emitter and self.run_id:
                await self.emitter.emit(self.run_id, EventType.rate_limited, f"Rate limited on {hostname}", {"retry_after": wait_t})
            raise RateLimitExceeded(wait_t)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        from bughunter.models.policy import PolicyAction, PolicyDecisionEnum
        decision = self.safety.check(self.run_id or "unknown", PolicyAction.network_request, url)
        if decision.decision == PolicyDecisionEnum.block:
            if self.emitter and self.run_id:
                await self.emitter.emit(
                    self.run_id, 
                    EventType.policy_violation, 
                    f"Blocked {method} {url}: {decision.reason}",
                    {"url": url, "method": method, "reason": decision.reason}
                )
            raise ValueError(f"Request blocked by safety policy: {decision.reason}")
            
        await self._check_rate_limit(url)
        
        return await self.client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)
        
    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)
        
    async def close(self):
        await self.client.aclose()
