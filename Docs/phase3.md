# Phase 3: Dynamic Testing, Textual TUI, and Live Scoring

## Goal

Add test planning, safe active web testing, the full Textual TUI with live scoring display, and a responsive terminal experience. Phase 3 focuses on:

- `DynamicTestAgent` with scoped HTTP client
- `testing/testN.md` plan generation before execution
- `test-results.md` append workflow
- The full Textual-based TUI replacing the Phase 1 Rich-based display
- Live VulnScore probability bars in the TUI
- Approval gate modals for active tests
- Heartbeat events and cancellation support

---

## Deliverables

- `DynamicTestAgent` implementation.
- `ScopedHttpClient` with rate limiting and scope enforcement.
- `testing/testN.md` test plan generator.
- `test-results.md` append workflow.
- Safe active test suite (headers, CORS, cookies, canaries).
- Full Textual TUI (replaces Phase 1 Rich streaming). **Must be the best, most beautiful and responsive TUI possible.**
- Live finding cards with VulnScore and AI confidence probability bars.
- Phase tracker widget.
- Agent feed widget.
- Score summary panel.
- Approval gate modals.
- Heartbeat and interruption handling.
- Cancellation and partial run preservation.
- Integration tests against the vulnerable Express fixture app.

---

## Test Plan Files

Before any test executes, `PlannerAgent` writes:

```
.bughunter/runs/<run_id>/testing/testN.md
```

### Required Fields in Each Test Plan

- **Test ID** (e.g., `T-001`)
- **Title**
- **White-hat authorization statement** (explicit, always present)
- **Test category** (from `Docs/test-library.md` taxonomy)
- **Safety classification**: `passive`, `safe-active`, `lab-validation`, or `blocked`
- **Source index entries** (which index entries triggered this test)
- **Semgrep rule IDs** that motivated the test (if applicable)
- **Target files, routes, or endpoints**
- **Test objective**
- **Test method** (deterministic tools + safe HTTP checks)
- **Deterministic tools to run**
- **AI review task** (if any — what AI is asked to evaluate)
- **Safety limits** (rate limits, concurrency caps, payload restrictions)
- **Expected evidence** (what a positive result looks like)
- **Todo checklist** (enables TUI progress tracking and resume)
- **Result placeholder** (filled in by `DynamicTestAgent`)

### Example Test Plan (excerpt)

```markdown
# Test T-003: SQL Injection — POST /api/login

**White-hat authorization**: This test is designed for authorized white-hat security
validation of the scoped target only. Target: http://localhost:3000 per bughunter-scope.yml.

**Category**: injection / sql  
**Safety class**: safe-active  
**Source index entries**: auth/views.py:138-155 [tags: sql, auth]  
**Semgrep rules**: python.django.security.audit.raw-query  

## Objective
Confirm whether the login endpoint is vulnerable to SQL injection via the user_id parameter.

## Method
1. Send benign baseline request to POST /api/login
2. Send SQL canary: `user_id = "1 AND 1=1--"` (safe, non-destructive)
3. Compare responses for behavioral difference
4. If behavioral difference detected, send a second canary: `user_id = "1 AND 1=2--"`
5. Record request/response evidence

## Safety Limits
- Max 4 requests total for this test
- No union-based or time-based payloads (lab-validation only)
- No data extraction attempts

## Expected Evidence
- Different HTTP response for canary vs baseline
- Error message exposure or behavioral difference in response body

## Todo
- [ ] Send baseline request
- [ ] Send canary 1 and record response
- [ ] Send canary 2 and record response
- [ ] Compare responses
- [ ] Store evidence records

## Result
[To be filled by DynamicTestAgent]
```

---

## Test Results File

After each test, `DynamicTestAgent` appends to:

```
.bughunter/runs/<run_id>/test-results.md
```

### Each Result Entry Must Include

- Test ID and title
- Status: `passed`, `finding_created`, `blocked`, `inconclusive`, or `skipped`
- Tools and HTTP checks executed
- Evidence IDs created
- Observations (behavioral differences, response anomalies)
- Finding IDs created (if any)
- False positives rejected and reason
- Retest guidance

`test-results.md` is append-only during a run. It is the source of truth for `ReportAgent`.

---

## DynamicTestAgent

`DynamicTestAgent` executes the safe-active HTTP tests planned in `testing/testN.md`.

### Process

1. Read test plan from `testing/testN.md`.
2. Check each action against `SafetyPolicyEngine`.
3. Send requests through `ScopedHttpClient` (enforces scope, rate limits).
4. Collect request + response as evidence records.
5. Apply `PromptGuardAgent` to any HTTP response before AI review.
6. Ask AI to evaluate behavioral differences (structured output).
7. Store evidence and create findings with `EvidenceAgent`.
8. Update the todo checklist in the test plan file.
9. Append result to `test-results.md`.
10. Emit `tool_progress` and `finding_candidate`/`finding_confirmed` events.

---

## ScopedHttpClient

Every outbound HTTP request must pass through `ScopedHttpClient`.

### Scope Guard Checks (in order)

1. URL scheme: only `http` and `https` allowed.
2. Hostname matches `targets.urls` or `targets.hosts` in scope file.
3. Port matches (no unexpected port scanning).
4. Scan mode allows HTTP requests (passive mode blocks all).
5. Rate limit not exceeded (token bucket per hostname).
6. Payload category is allowed for current scan mode.

Requests failing any check are rejected and logged as `policy_violation` events. They are never sent.

### Rate Limiting

- Token bucket per hostname.
- Default: 60 requests/minute (configurable in scope file).
- When bucket is empty, `ScopedHttpClient` emits `rate_limited` event with retry time.
- The TUI shows the countdown in the footer.

### Concurrency

- Default max concurrent requests: 5.
- Race-condition tests may request higher concurrency but must not exceed `max_concurrency` in scope.
- `SafetyPolicyEngine` enforces the cap.

---

## Safe Active Test Suite

Allowed in `safe-active` mode:

### Security Header Checks

- `Content-Security-Policy` — present and not permissive (`unsafe-inline`, `unsafe-eval`)
- `Strict-Transport-Security` — present with `max-age ≥ 31536000`
- `X-Frame-Options` — `DENY` or `SAMEORIGIN`
- `X-Content-Type-Options` — `nosniff`
- `Permissions-Policy` — present
- `Referrer-Policy` — present and restrictive
- `Cache-Control` on sensitive routes — `no-store` or `no-cache`

### CORS Checks

- `Access-Control-Allow-Origin: *` (overly permissive)
- `Access-Control-Allow-Credentials: true` with wildcard origin
- Reflected origin without validation (send arbitrary origin, check if reflected)

### TLS Checks

- TLS version (TLS 1.0/1.1 → finding)
- Weak cipher suites
- Certificate validity

### Cookie Flag Checks

- `Secure` flag on session cookies
- `HttpOnly` flag
- `SameSite` attribute
- Session cookie lifetime

### Safe Canary Payloads

Canary payloads prove reflection or parser behavior **without causing damage**:

- **SQL canary**: `1 AND 1=1--` vs `1 AND 1=2--` — behavioral difference detection
- **XSS canary**: `<script>alert(1)</script>` in query params — check if reflected unencoded
- **Path traversal canary**: `../etc/hostname` — check for path traversal response
- **SSRF indicator**: Request to a controlled callback URL (if configured in scope)

**All canary payloads are**:
- Non-destructive
- Non-data-exfiltrating
- Scope-restricted
- Evidence-documented

### Access Control Checks

- Routes accessible without authentication (against configured test accounts)
- IDOR probes using test account object IDs (requires test accounts in scope file)
- Broken function-level authorization (user role vs admin endpoint)

---

## Full Textual TUI

Phase 3 delivers the full Textual-based TUI, replacing the Phase 1 Rich streaming.

See `Docs/tui-design.md` for the complete specification.

### Phase 3 TUI Milestones

- [ ] `BugHunterApp` Textual application with theme and CSS.
- [ ] `PhaseTrackerWidget` with 8 phases and status icons.
- [ ] `AgentFeedWidget` scrolling log.
- [ ] `FindingsStreamWidget` with `FindingCard` widgets.
- [ ] `VulnScore` progress bar per finding (colored by tier).
- [ ] `AIProbBar` animated probability bar.
- [ ] `ScoreSummaryWidget` with tier counts, top/mean score, token cost.
- [ ] `BugHunterHeader` with elapsed timer.
- [ ] `BugHunterFooter` with current op and rate limit state.
- [ ] `ApprovalModal` for safe-active, lab-validation, race-condition.
- [ ] Heartbeat events: `model_waiting` spinner, `rate_limited` countdown.
- [ ] Keyboard bindings: q, p, r, e, i, f, s, a, ?.
- [ ] Interruption handling: Ctrl+C → save partial results prompt.
- [ ] Non-TTY fallback to Rich structured logging.

---

## Latency Strategy

The TUI must stay active and informative during all long-running operations.

### Heartbeat Events (emitted on schedule)

| Event | When | Interval |
|---|---|---|
| `model_waiting` | LLM call in progress | Every 3s |
| `rate_limited` | Rate limit hit | Once, with countdown |
| `still_running` | No output for extended period | Every 15s |
| `tool_progress` | Semgrep scanning | Every 5s (file count) |

### Progress Rules

- **No fake progress bars** with invented percentages.
- When total work is unknown: show "current file N / ?" or elapsed time.
- When total is known (from Semgrep file list): show "N / total files".
- Rate limit waits show exact countdown (not a generic spinner).

---

## Cancellation and Resume

### Interruption Handling

When user presses `q` or `Ctrl+C`:
1. Modal: *"Save partial results before exiting? [Y/N]"*
2. If Y: Signal LangGraph to stop after current node. Write partial `test-results.md` and `bug-report.md [INCOMPLETE]`.
3. If N: Exit. SQLite preserves committed state.

### Resume

```bash
bughunter scan --resume <run_id>
```

Resumes from the last completed LangGraph checkpoint. Completed nodes are not re-run. In-progress test is re-run from its last completed todo item.

---

## Todo List

- [ ] Implement `ScopedHttpClient` with scope guard and rate limiting.
- [ ] Implement test plan writer (`testing/testN.md`).
- [ ] Implement test results appender (`test-results.md`).
- [ ] Implement `DynamicTestAgent` with policy checks.
- [ ] Implement security header checks.
- [ ] Implement CORS checks.
- [ ] Implement TLS checks.
- [ ] Implement cookie flag checks.
- [ ] Implement safe SQL canary framework.
- [ ] Implement safe XSS canary framework.
- [ ] Implement path traversal canary.
- [ ] Implement access control checks (with test accounts).
- [ ] Implement full Textual TUI (`BugHunterApp` and all widgets).
- [ ] Implement VulnScore and AI probability bars with animation.
- [ ] Implement approval gate modals.
- [ ] Implement heartbeat events.
- [ ] Implement interruption handling and partial save.
- [ ] Implement run resume from checkpoint.
- [ ] Add test: out-of-scope requests are blocked before sending.
- [ ] Add test: rate limiting is enforced.
- [ ] Add test: canary payloads do not exceed safe limits.
- [ ] Add integration test against vulnerable Express fixture app.

---

## Acceptance Criteria

Phase 3 is complete when:

- Test plans are written to `testing/testN.md` before any execution.
- `test-results.md` is updated after each test.
- Safe active checks run only against scoped targets.
- Out-of-scope requests are blocked and logged as policy violations.
- The full Textual TUI shows VulnScore bars and AI probability bars.
- Approval gate modals appear before safe-active network tests.
- Heartbeat events prevent TUI from appearing frozen.
- Partial findings appear in TUI before the full scan completes.
- Interrupted runs preserve enough state for a partial report.
- Resume continues from the last checkpoint without re-running completed tests.
