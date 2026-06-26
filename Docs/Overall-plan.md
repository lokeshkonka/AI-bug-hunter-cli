# Bug Hunter CLI — Overall Plan

## Product Vision

Bug Hunter CLI is an autonomous, authorized white-hat security CLI for developers, bug bounty hunters, and security engineers. It is purpose-built for security: scoped authorization, codebase understanding, deterministic evidence, safe validation, test planning, retesting, and professional reporting.

The tool behaves like a disciplined security engineer:

1. Confirm scope and authorization.
2. Understand the codebase — build a compact security index.
3. Plan tests from that index.
4. Execute only safe, scoped tests using deterministic tools (Semgrep primary).
5. Score every finding using a composite VulnScore (CVSS + AI confidence + evidence weight + exploitability).
6. Store evidence for every claim.
7. Display live scoring in a Textual-based TUI with probability bars.
8. Produce a clear bug report with fixes, scores, and retest steps.

---

## What Makes It Best-In-Class

- **Index-first auditing**: `index.md` is built before testing so agents navigate the codebase like a book index — no whole-repo sends to LLM.
- **Semgrep-powered scanning**: Semgrep is the primary deterministic scanner with 1000+ security rules across all major languages and frameworks. AI evaluates bounded evidence, not raw files.
- **Composite VulnScore**: Every finding gets a 0–100 score from `VulnScoringAgent` combining CVSS, AI confidence probability, evidence weight, exploitability, and remediation complexity. Live probability bars in TUI.
- **Strict white-hat boundary**: Every action is gated by `bughunter-scope.yml` and `SafetyPolicyEngine`.
- **PromptGuardAgent**: Dedicated prompt injection defense layer. All untrusted repository content is wrapped as evidence blocks before reaching the LLM. Injection attempts are logged as security events.
- **ContextManagerAgent**: Token budget enforcement, snippet selection, caching, and cost tracking. Prevents runaway API costs on large repos.
- **12-agent architecture on LangGraph**: Each agent has a single responsibility. The graph is observable, resumable, and auditable.
- **Textual TUI**: Full reactive multi-panel terminal UI with live scoring display, phase tracker, agent feed, approval gate modals, and keyboard controls.
- **Traceable artifacts**: `index.md → testing/testN.md → test-results.md → bug-report.md`. Every artifact in this chain is generated from the previous one, not from model memory.
- **Professional reports**: `bug-report.md` cites exact evidence IDs, index entry IDs, test plan IDs, and score components. Suitable for GitHub issues, security audit handoffs, and bug bounty submissions.
- **SARIF + JSON export**: Machine-readable output for CI/CD pipeline integration.
- **Low token cost**: Index entries, targeted snippets, and the caching layer keep model calls small. Budget controls prevent surprises.

---

## MVP Scope

The MVP audits:

- Local repositories (passive and static audit)
- Local development servers
- Explicitly authorized URLs and hosts

Supported scan modes:

- `passive`: static code, config, dependency, and secret review only.
- `safe-active`: scoped, non-destructive HTTP checks and safe canary payloads.
- `lab-validation`: controlled validation for local or explicitly lab-marked targets.

Default mode: `safe-active`, only after scope validation and user approval for network activity.

Blocked by default (all modes):

- Denial-of-service
- Credential attacks and password spraying
- Persistence and malware behavior
- Real ZIP bombs and real data exfiltration
- Destructive payloads
- Unbounded fuzzing
- Unauthorized internet scanning

---

## CLI Commands

Primary interactive command:

```bash
bughunter
```

Scriptable commands:

```bash
bughunter config
bughunter init-scope
bughunter index --scope bughunter-scope.yml
bughunter plan-tests --run <run_id>
bughunter scan --scope bughunter-scope.yml
bughunter scan --resume <run_id>
bughunter report --run <run_id>
bughunter retest --run <run_id>
bughunter retest --run <run_id> --finding <id> [--tier high critical]
bughunter runs
bughunter show --run <run_id>
bughunter export --run <run_id> --format sarif
bughunter export --run <run_id> --format json
```

Command behavior:

- `config`: configure provider, model, local settings, token budget, redaction preferences.
- `init-scope`: generate a starter `bughunter-scope.yml`.
- `index`: build only the codebase security index.
- `plan-tests`: create test plans from an existing index.
- `scan`: run the full workflow.
- `scan --resume`: resume an interrupted run from last checkpoint.
- `report`: regenerate `bug-report.md` from stored artifacts.
- `retest`: rerun selected tests and update finding status.
- `runs`: list prior runs with summary (findings count, score distribution, cost).
- `show`: inspect artifacts and findings from a run.
- `export`: export findings as SARIF or JSON for CI/CD integration.

---

## End-to-End Workflow

Every full scan follows this strict order:

1. Load and validate `bughunter-scope.yml`.
2. Validate safety policy via `SafetyPolicyEngine`.
3. Create a run directory and SQLite run record.
4. `PlannerAgent` creates the scan plan.
5. `ReconAgent` builds repository manifest.
6. `ContextManagerAgent` applies file relevance scoring and filtering.
7. `ReconAgent` generates `.bughunter/runs/<run_id>/index.md`.
8. Index entries stored in SQLite.
9. `PlannerAgent` selects tests from the test library using the index.
10. `PlannerAgent` generates `.bughunter/runs/<run_id>/testing/testN.md`.
11. **Approval gate**: user approves safe-active network tests if applicable.
12. `StaticAuditAgent` runs Semgrep and deterministic scanners against indexed files.
13. `DynamicTestAgent` runs scoped HTTP checks against authorized targets.
14. `EvidenceAgent` normalizes, redacts, and deduplicates evidence.
15. `VulnScoringAgent` scores every finding (VulnScore 0–100, risk tier, probability bars in TUI).
16. Every test result appended to `.bughunter/runs/<run_id>/test-results.md`.
17. `FixAgent` proposes concrete remediation guidance per finding.
18. `ReportAgent` generates `.bughunter/runs/<run_id>/bug-report.md`.
19. User offered retest actions for fix validation.

Runtime artifact layout:

```text
.bughunter/runs/<run_id>/
  index.md
  testing/
    test1.md
    test2.md
    test3.md
    ...
  test-results.md
  bug-report.md
  bug-report.sarif        (if exported)
  bug-report.json         (if exported)
```

---

## Scope and Authorization

Network testing requires `bughunter-scope.yml`.

```yaml
project:
  name: example-app
  repo_path: .

targets:
  urls:
    - http://localhost:3000
  hosts: []

scan:
  mode: safe-active
  max_requests_per_minute: 60
  max_depth: 2
  max_concurrency: 5

safety:
  allow_lab_validation: false
  prompt_injection_sensitivity: medium
  notes: "Authorized local development target"

cost:
  max_tokens_per_run: 200000
  max_tokens_per_test: 15000
  max_cost_usd: 1.00
  warn_at_percent: 80
```

Rules:

- No wildcard internet scanning in MVP.
- Out-of-scope requests are blocked before sending.
- Lab validation requires `allow_lab_validation: true`.
- Passive local repo scans can run without network targets.
- The CLI must never auto-upgrade from passive to active testing.
- Token and cost budgets are enforced by `ContextManagerAgent`.

---

## Agent Architecture (12 Agents)

Bug Hunter CLI uses LangGraph as the orchestration layer.

### Core Pipeline Agents

| Agent | Phase | Responsibility |
|---|---|---|
| `PlannerAgent` | Plan | Validates intent, creates scan plan, selects tests from library, generates testN.md |
| `ReconAgent` | Recon | Builds repository manifest, generates index.md, detects languages/frameworks |
| `StaticAuditAgent` | Audit | Runs Semgrep + deterministic scanners, sends bounded snippets to LLM for review |
| `DynamicTestAgent` | Test | Runs scoped HTTP checks, safe canary payloads, rate-limited probes |
| `EvidenceAgent` | Evidence | Normalizes evidence, redacts secrets, deduplicates findings, computes evidence weight |
| `VulnScoringAgent` | Score | Scores every finding with composite VulnScore, detects score inflation, ranks findings |
| `FixAgent` | Fix | Proposes concrete remediation guidance, patch-style suggestions, assesses remed complexity |
| `ReportAgent` | Report | Generates bug-report.md from all artifacts + evidence, exports SARIF/JSON |

### Supporting Agents

| Agent | Role |
|---|---|
| `RetestAgent` | Dedicated retest workflow — re-runs selected tests, compares evidence, updates finding status |
| `ContextManagerAgent` | Token budget enforcement, snippet selection, caching, cost tracking |
| `PromptGuardAgent` | Prompt injection defense — wraps all untrusted content before LLM calls, logs injection attempts |
| `CliUiAgent` | Textual TUI — streams progress, scoring bars, approval gate modals, agent feed |

### Supporting Components

- `SafetyPolicyEngine` — gates every command, HTTP request, payload, and test
- `ScopedHttpClient` — enforces scope on all outbound HTTP requests
- `DeterministicToolRunner` — runs Semgrep, pip-audit, npm audit, trufflehog with policy checks
- `SecretRedactor` — masks secrets before storage, display, or LLM calls
- `IndexStore` — stores and queries index entries by tag, file, route, category
- `TestRegistry` — reusable test definitions from `Docs/test-library.md`
- `ArtifactWriter` — writes and updates run artifact files
- `RunStore` — SQLite run history management
- `ProviderAdapter` — unified LLM interface for OpenAI and Gemini

---

## Semgrep Integration

Semgrep is the primary deterministic static scanner. It replaces ad-hoc regex patterns for static analysis.

**Why Semgrep**:
- 1000+ maintained security rules across all major languages
- Structural matching (understands code AST, not just regex)
- False-positive rate significantly lower than regex
- SARIF output natively supported
- Can be pinned to specific rule versions for reproducibility

**Rule packs used by default**:

| Pack | Languages / Use Case |
|---|---|
| `p/security-audit` | General security patterns |
| `p/owasp-top-ten` | OWASP Top 10 patterns |
| `p/secrets` | Secrets and API keys |
| `p/supply-chain` | Dependency and supply-chain risks |
| `p/python` | Python-specific security |
| `p/javascript` | JavaScript security |
| `p/typescript` | TypeScript security |
| `p/java` | Java security |
| `p/ruby` | Ruby security |
| `p/go` | Go security |
| `p/php` | PHP security |
| `p/django` | Django framework |
| `p/flask` | Flask framework |
| `p/express` | Express.js framework |
| `p/react` | React-specific issues |

**Semgrep workflow**:
1. `DeterministicToolRunner` runs Semgrep against repository manifest files.
2. Output parsed as structured JSON (never as shell text).
3. Each match becomes an evidence record with file path, line range, rule ID, and rule message.
4. AI (`StaticAuditAgent`) reviews matches for false-positive reduction and impact assessment.
5. Semgrep matches are the primary evidence source for static findings.

**Safety rules**:
- Semgrep only runs against files in the repository manifest (excluded dirs are never touched).
- Per-file timeout: 30 seconds (configurable).
- Rule sets are pinned versions.
- Semgrep output is parsed, not executed.

---

## Composite VulnScore System

Every finding receives a VulnScore (0–100) computed by `VulnScoringAgent`.

**Components**:

| Component | Weight | Description |
|---|---|---|
| CVSS Base Score | 35% | Technical severity (0–10) |
| AI Confidence Probability | 25% | Calibrated LLM confidence (0.0–1.0) |
| Evidence Weight | 20% | Quality and count of evidence (0–5) |
| Exploitability Factor | 12% | OWASP/PoC/auth context (0.0–1.0) |
| Remediation Penalty | 8% | Complex fixes lower urgency (-0.15–0) |

**Risk tiers**:

| Tier | Score | Color |
|---|---|---|
| CRITICAL | 85–100 | 🔴 Red |
| HIGH | 65–84 | 🟠 Orange |
| MEDIUM | 40–64 | 🟡 Yellow |
| LOW | 15–39 | 🔵 Blue |
| INFORMATIONAL | 0–14 | ⚪ Gray |

See `Docs/scoring-system.md` for the full formula, worked examples, anti-gaming rules, and SQLite schema.

---

## Textual TUI

The terminal UI is built with Python Textual for full reactive panel layout.

**Panels**:
- **Header**: Tool name, run ID, elapsed time, active model
- **Phase Tracker** (left): 8-phase pipeline with status icons
- **Agent Feed** (left): Live log of agent actions (no chain-of-thought)
- **Live Findings** (main): Finding cards with VulnScore bars and AI confidence probability bars
- **Score Summary** (right): Risk tier counts, top/mean score, token usage, cost
- **Footer**: Current operation, rate-limit state, keyboard shortcuts

**Key features**:
- Probability bars animate as VulnScoringAgent processes each finding
- Findings re-rank in real time as new scores arrive
- Approval gate modals block the pipeline for user confirmation
- `[s]` shows full score breakdown (CVSS + AI prob + evidence items)
- Heartbeat events prevent UI from appearing frozen during long waits
- Non-TTY fallback to Rich structured logging for CI

See `Docs/tui-design.md` for full layout wireframes and widget specifications.

---

## Codebase Index

`index.md` is the core token-saving and reasoning layer. It is built before any test planning.

**Required sections**:

- Project summary and detected stack
- Entry points
- Route and API map
- Auth and authorization map
- Data flow map
- Database and storage access
- File upload and parsing surfaces
- External network calls
- Background jobs
- Config and secret surfaces
- Dependency risk surfaces
- Admin and privileged features
- Security-sensitive files with reasons
- Suggested test areas

**Each index entry includes**:

- File path
- Symbol, function, class, route, or config key
- Line range
- Security relevance
- Retrieval tags (`auth`, `sql`, `xss`, `upload`, `ssrf`, `secrets`, `admin`, `cors`, etc.)
- Related OWASP or test category
- Semgrep rule IDs that match this file (pre-computed)

---

## Security Coverage

**Static (passive)**:

- Secret detection (Semgrep `p/secrets` + trufflehog patterns)
- Dependency vulnerabilities (pip-audit, npm audit, safety)
- Debug flag detection
- Hardcoded credentials
- Insecure CORS configuration
- Dangerous deserialization patterns
- SQL query construction patterns
- File upload handling patterns
- Path traversal risks
- SSRF sink patterns
- Command injection patterns
- Language/framework-specific checks (Flask, Django, Express, Spring, Laravel, Rails, etc.)

**Dynamic (safe-active)**:

- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- CORS policy checks
- TLS metadata
- Cookie flag checks (Secure, HttpOnly, SameSite)
- Redirect behavior
- Auth/session consistency (with test accounts)
- Safe SQL injection canaries
- Safe XSS reflection canaries
- Path traversal canaries
- Rate-limit observation

**AI-assisted**:

- IDOR/BOLA (route mapping + access control review)
- Business logic flaws
- Mass assignment risks
- JWT weakness assessment
- Missing role checks
- Privilege escalation patterns

---

## Provider Strategy

Support OpenAI and Gemini behind one model interface.

Required provider abstraction:

- `generate_structured(prompt, output_schema)` — typed structured output
- `summarize(content, max_tokens)` — bounded summarization
- `rank_findings(findings)` — relative risk ranking
- `propose_fixes(finding, evidence)` — remediation guidance
- `estimate_cost(prompt_tokens, completion_tokens)` — cost tracking

Provider rules:

- API keys from environment variables only. Never stored in config files.
- All content redacted by `SecretRedactor` before provider calls.
- All content wrapped by `PromptGuardAgent` before provider calls.
- Token usage tracked per call in SQLite.
- Timeouts: 60s per call, 3 retries with exponential backoff.
- Structured output parsed as typed Pydantic models. No raw text parsing.
- Graceful degradation when provider is unavailable.

---

## Data Storage

SQLite for local run history.

**Core tables**:

| Table | Purpose |
|---|---|
| `runs` | Run records with scope, status, timing |
| `events` | All events emitted during a run |
| `targets` | Scoped URL and host targets |
| `files` | Repository manifest entries |
| `index_entries` | Security index entries with tags |
| `test_plans` | Generated testN.md records |
| `test_results` | Results per test |
| `policy_decisions` | SafetyPolicyEngine decisions |
| `policy_violations` | Blocked actions |
| `evidence` | Evidence records with source and content |
| `findings` | Finding records with status lifecycle |
| `score_components` | VulnScore component breakdown per finding |
| `reports` | Report artifact records |
| `provider_usage` | Token and cost tracking per call |
| `security_events` | Prompt injection attempts and safety logs |
| `retest_runs` | Retest run records linked to original runs |

---

## Report Requirements

**Runtime artifacts**:

```
index.md               — security index of the codebase
testing/testN.md       — test plan per test (before execution)
test-results.md        — append-only results per test
bug-report.md          — final polished report
bug-report.sarif       — SARIF format (optional export)
bug-report.json        — JSON format (optional export)
```

**`bug-report.md` sections**:

1. Executive summary
2. Scope and authorization
3. Scan mode and safety policy summary
4. Codebase index summary
5. Tests executed / blocked / skipped
6. Policy violations
7. Risk overview (VulnScore distribution table)
8. Findings table (title, tier, score, confidence, category)
9. Detailed findings (with score breakdown, evidence, reproduction, fix)
10. Retest checklist
11. Tool and model metadata (tokens used, cost, Semgrep rules, provider)
12. AI safety events appendix (prompt injection attempts)

**Each finding must cite**:

- VulnScore and risk tier
- Score breakdown (all 5 components with rationale)
- Index entry IDs used
- Test plan that produced the result
- Test result entry
- Evidence IDs
- Semgrep rule IDs (if applicable)
- CVSS vector

---

## Implementation Phases

### Phase 1: Foundation, Safety, and CLI Skeleton

- Python package scaffold using `uv`
- Typer CLI entrypoint
- `bughunter-scope.yml` parser and validator
- SQLite schema and run store
- Event bus (asyncio)
- `SafetyPolicyEngine` with policy decisions
- `SecretRedactor`
- Provider config for OpenAI and Gemini
- Minimal Semgrep runner (basic rule packs)
- Basic deterministic checks (secrets, debug flags, configs)
- Minimal Markdown report renderer
- Basic TUI (Rich-based streaming, upgrade to Textual in Phase 3)

### Phase 2: Recon, Index, and Static Audit Pipeline

- `ReconAgent` with repository manifest builder
- `ContextManagerAgent` (snippet selection, token budget, caching)
- `index.md` generator with all required sections
- Index entry SQLite storage and tag-based retrieval
- Full Semgrep integration with all language rule packs
- `StaticAuditAgent` — Semgrep + AI review of bounded snippets
- `PromptGuardAgent` (content wrapping, injection detection)
- Evidence records and EvidenceAgent deduplication
- Static findings with exact file references and Semgrep rule IDs

### Phase 3: Dynamic Testing and Textual TUI

- `DynamicTestAgent` with scoped HTTP client
- Rate limiting and concurrency controls
- `testing/testN.md` test plan generation
- `test-results.md` append workflow
- Safe active test suite (headers, CORS, cookies, canaries)
- Full Textual TUI with all panels
- Live scoring display (VulnScore bars, probability bars)
- Phase tracker and agent feed
- Approval gate modals
- Heartbeat events and interruption handling
- Cancellation and resume support

### Phase 4: Scoring, Orchestration, and Final Reports

- Full LangGraph graph connecting all agents
- `VulnScoringAgent` — composite VulnScore, risk tiers, inflation detection
- `FixAgent` — remediation guidance with remed complexity
- `ReportAgent` — polished `bug-report.md` from all artifacts
- `RetestAgent` — retest workflow, evidence comparison, status lifecycle
- OpenAI and Gemini provider adapters with structured output
- Token and cost tracking (full `provider_usage` table)
- Retest command and retest report
- Score breakdown modal in TUI
- End-to-end integration tests against fixture apps

### Phase 5: CI Integration, Exports, and Robustness

- SARIF export (valid SARIF 2.1.0)
- JSON export for machine consumption
- CI mode (non-TTY Rich logging + JSON events)
- GitHub Actions integration example
- GitHub issue export command
- Plugin-style test packs (custom org-specific rules)
- Fixture app suite (vulnerable Flask + Express apps)
- Prompt injection test suite
- Cost control CI enforcement (fail if CRITICAL findings or cost > threshold)
- Lockfile-pinned Semgrep rule versions

---

## Fixture Apps

For integration and end-to-end testing, Bug Hunter CLI maintains small intentionally vulnerable apps:

```
tests/fixtures/
  vulnerable_flask_app/          # Python Flask with known vulns
    app.py                       # SQLi, IDOR, debug mode, secrets
    requirements.txt
    scope.yml                    # Scope file for testing
  vulnerable_express_app/        # Node.js Express with known vulns
    app.js                       # XSS, CORS, missing headers
    package.json
    scope.yml
  scope_files/                   # Various scope file examples
    passive_only.yml
    safe_active.yml
    lab_validation.yml
```

These apps have documented vulnerabilities at known file paths and line numbers. Each Phase 2+ test run can be verified against expected findings.

---

## Success Criteria

**MVP success** — a user can:

1. Configure OpenAI or Gemini.
2. Create or generate `bughunter-scope.yml`.
3. Run `bughunter scan --scope bughunter-scope.yml`.
4. Watch the Textual TUI with live scoring bars.
5. See `index.md` created before deeper testing.
6. Review generated `testing/testN.md` plans.
7. Approve scoped active tests via TUI modal.
8. Watch findings appear with VulnScore and AI confidence probability bars.
9. Get `test-results.md` and `bug-report.md` with full score breakdowns.
10. Run `bughunter retest --run <id>` after fixing issues.

**Best-in-class success**:

- Findings are evidence-backed, scored, and reproducible.
- Semgrep provides the bulk of static evidence — AI only refines and interprets.
- PromptGuardAgent blocks all tested injection attempts.
- Reports are useful to developers, security engineers, and bug bounty programs.
- The index-first design keeps API costs within budget.
- The TUI feels alive and trustworthy during long AI and scan phases.
- SARIF output is valid and usable in GitHub Code Scanning.
- The same run can be inspected, resumed, reported, and retested.

---

## Related Docs

- `Docs/scoring-system.md` — Full VulnScore formula, components, anti-gaming rules
- `Docs/tui-design.md` — Textual TUI layout, widgets, wireframes
- `Docs/strict-ai-safety.md` — AI safety contract, PromptGuardAgent, SafetyPolicyEngine
- `Docs/test-library.md` — Reusable test definitions with Semgrep rule references
- `Docs/artifact-workflow.md` — Artifact chain and order guarantees
- `Docs/robustness-checklist.md` — Comprehensive robustness checklist
- `Docs/phase1.md` through `Docs/phase5.md` — Phased implementation plans
- `Docs/agents/` — Per-agent specifications
