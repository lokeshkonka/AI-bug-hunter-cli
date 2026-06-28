import uuid
from urllib.parse import urlparse
from bughunter.models.scope import Scope
from bughunter.models.policy import PolicyDecision, PolicyDecisionEnum, PolicyAction, PolicyViolation

class SafetyPolicyEngine:
    def __init__(self, scope: Scope):
        self.scope = scope

    def check(self, run_id: str, action: PolicyAction, target: str) -> PolicyDecision:
        if action == PolicyAction.network_request:
            return self._check_network_request(run_id, target)
        elif action == PolicyAction.file_read:
            return self._check_file_read(run_id, target)
        elif action == PolicyAction.tool_execution:
            return self._check_tool_execution(run_id, target)
        
        return PolicyDecision(
            id=str(uuid.uuid4()),
            run_id=run_id,
            action=action,
            target=target,
            decision=PolicyDecisionEnum.block,
            reason="Unknown action type"
        )

    def _check_network_request(self, run_id: str, target: str) -> PolicyDecision:
        # Check if URL is in scope
        parsed_target = urlparse(target)
        
        # We consider it in scope if the base URL matches any of the scope.targets.urls
        # or if the host matches scope.targets.hosts
        in_scope = False
        
        for allowed_url in self.scope.targets.urls:
            parsed_allowed = urlparse(allowed_url)
            if parsed_target.scheme == parsed_allowed.scheme and parsed_target.netloc == parsed_allowed.netloc:
                in_scope = True
                break
                
        if not in_scope and parsed_target.hostname in self.scope.targets.hosts:
            in_scope = True

        if not in_scope:
            return PolicyDecision(
                id=str(uuid.uuid4()),
                run_id=run_id,
                action=PolicyAction.network_request,
                target=target,
                decision=PolicyDecisionEnum.block,
                reason="Target URL or host is not in scope"
            )
            
        return PolicyDecision(
            id=str(uuid.uuid4()),
            run_id=run_id,
            action=PolicyAction.network_request,
            target=target,
            decision=PolicyDecisionEnum.allow,
            reason="Target is in scope"
        )

    def _check_file_read(self, run_id: str, target: str) -> PolicyDecision:
        # Default allow for now, can implement path traversal checks later
        return PolicyDecision(
            id=str(uuid.uuid4()),
            run_id=run_id,
            action=PolicyAction.file_read,
            target=target,
            decision=PolicyDecisionEnum.allow,
            reason="Local file read allowed"
        )

    def _check_tool_execution(self, run_id: str, target: str) -> PolicyDecision:
        return PolicyDecision(
            id=str(uuid.uuid4()),
            run_id=run_id,
            action=PolicyAction.tool_execution,
            target=target,
            decision=PolicyDecisionEnum.allow,
            reason="Tool execution allowed"
        )

    def block(self, run_id: str, action: PolicyAction, target: str, reason: str) -> PolicyViolation:
        return PolicyViolation(
            id=str(uuid.uuid4()),
            run_id=run_id,
            action=action,
            target=target,
            reason=reason
        )
