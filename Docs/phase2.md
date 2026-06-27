# Phase 2: Recon, Index, and Full Static Audit Pipeline

## Goal

Build the codebase-aware audit pipeline. Phase 2 makes Bug Hunter CLI useful for deep local repository auditing by mapping the project, creating a reusable `index.md`, selecting relevant files with `ContextManagerAgent`, running full Semgrep with all language packs, and using AI only on compact evidence bundles filtered through `PromptGuardAgent`.

---

## Deliverables

- `ReconAgent` implementation with full repository manifest builder.
- `ContextManagerAgent` — snippet selection, token budgets, caching, cost tracking.
- `PromptGuardAgent` — injection detection and content wrapping.
- `index.md` generator with all required sections.
- Index entry SQLite storage and tag-based retrieval.
- Full Semgrep integration with all language and security rule packs.
- File relevance scoring.
- `StaticAuditAgent` — bounded snippet evaluation with AI.
- `EvidenceAgent` — deduplication, normalization, evidence weight computation.
- Evidence-backed static findings with Semgrep rule IDs cited.
- Tests against the vulnerable Flask fixture app.

---

## ReconAgent

`ReconAgent` is the first agent to run after scope validation. Its output — the repository manifest and `index.md` — is the foundation for every subsequent step.

### Repository Manifest

Before any LLM call, build a manifest containing:

- Project root path
- Detected languages (by file extension and framework indicators)
- Detected frameworks (presence of `requirements.txt`, `package.json`, `pom.xml`, `Gemfile`, `go.mod`, etc.)
- Dependency manifests with paths
- Route files (framework-specific detection)
- Middleware files
- Config files (`.env`, `settings.py`, `config.yml`, etc.)
- Auth-related files (login, auth, session, token in filename or content)
- Database access files (ORM models, raw SQL, connection strings)
- File upload or file-processing paths
- Background job files (celery, sidekiq, cron)
- Test files
- Excluded files with reasons

**Default excluded paths**:

```
.git/          .venv/         venv/          __pycache__/
node_modules/  dist/          build/         .next/
.cache/        .tox/          coverage/      htmlcov/
*.pyc          *.min.js       *.map          *.lock (unless dep scanning)
*.jpg *.png *.gif *.mp4 *.woff *.ttf *.eot
```

### File Relevance Scoring

Each file is assigned a relevance score (0.0–1.0) before inclusion in the index. Files below the threshold (default 0.3) are excluded from LLM calls but still scanned by Semgrep.

**Scoring factors**:

| Factor | Points |
|---|---|
| File name contains: login, auth, session, token, user, admin | +0.30 |
| File name contains: route, view, controller, handler, endpoint | +0.25 |
| File name contains: config, settings, env, secret, key | +0.25 |
| File name contains: payment, billing, order, checkout | +0.20 |
| File is a known framework entry point | +0.20 |
| File contains SQL query patterns (detected by grep) | +0.15 |
| File contains file upload logic | +0.15 |
| File is in `tests/` directory | -0.10 |
| File is auto-generated | -0.30 |

---

### Codebase Index (`index.md`) & Vector DB Ingestion

After the manifest is built, `ReconAgent` performs two indexing steps:
1. **Lexical Indexing (SQLite & Markdown)**: Creates `.bughunter/runs/<run_id>/index.md` for deterministic snippet selection and Semgrep evidence linking.
2. **Semantic Vector Indexing (ChromaDB)**: Ingests the codebase into a local ChromaDB collection (`.bughunter/vector_store/`) specifically to power the interactive REPL's RAG features, allowing users to ask questions like "How is authentication handled?".

`index.md` is a compact security navigation document. It lets later agents identify exact files, routes, symbols, and line ranges without rereading the entire repository.

### Required Sections

1. **Project Summary** — name, detected language/framework stack, repo size, excluded file count
2. **Entry Points** — main application files, server entry, WSGI/ASGI handlers
3. **API and Route Map** — every route detected with HTTP method, path, handler function, file:line
4. **Authentication and Authorization Map** — login routes, session management, JWT handling, role checks, decorator/middleware patterns
5. **Data Storage and Database Map** — ORM models, raw SQL, connection strings, database names
6. **File Upload and Parsing Surfaces** — upload endpoints, file type checks (or lack thereof), storage destinations
7. **External Network Call Surfaces** — HTTP client usage, fetch calls, requests library, API integrations
8. **Config and Secret Surfaces** — environment variable access, config file reads, secret management patterns
9. **Admin and Privileged Functionality** — admin panels, privileged routes, management commands
10. **Dependency and Package Risk Surfaces** — detected manifests, lock files, any packages with known CVEs (from Phase 1 dep check)
11. **Security-Sensitive File Index** — files ranked by security relevance with reasons
12. **Pre-computed Semgrep Matches** — list of files where Semgrep found matches, with rule IDs (populated after Semgrep run)
13. **Suggested Test Areas** — ordered list of recommended test categories based on the above

### Each Index Entry Includes

- File path
- Symbol, function, class, route, or config key
- Line range (start:end)
- Security relevance (brief explanation)
- Retrieval tags (from tag taxonomy)
- Related test category
- Semgrep rule IDs that matched in this file (pre-filled)

### Tag Taxonomy

`auth`, `authorization`, `idor`, `session`, `jwt`, `sql`, `nosql`, `ssrf`, `xss`, `ssti`, `xxe`, `upload`, `path-traversal`, `cors`, `secrets`, `admin`, `dependency`, `network`, `cloud`, `business-logic`, `race-condition`, `deserialization`, `command-injection`

---

## ContextManagerAgent (Full Implementation)

Phase 2 delivers the full `ContextManagerAgent`. See `Docs/agents/context_manager_agent.md`.

**Phase 2 deliverables**:
- File relevance scoring and pre-filtering
- Snippet selection algorithm (tag-based, relevance-ranked, token-budgeted)
- Audit packet construction (snippet + index entry + Semgrep matches)
- Token budget enforcement per run and per test
- In-memory + SQLite caching for index summaries and file summaries
- Cost tracking in `provider_usage` table
- Budget warning events emitted to TUI

---

## PromptGuardAgent (Full Implementation)

Phase 2 delivers the full `PromptGuardAgent`. See `Docs/agents/prompt_guard_agent.md`.

**Integration**:
- `ProviderAdapter.send_with_guard()` wraps all LLM calls.
- `SecretRedactor` runs first (mask secrets), then `PromptGuardAgent` (wrap injections), then `ProviderAdapter` sends.
- All injection detections logged as `security_events`.

---

## Full Semgrep Integration

Phase 2 enables all language and security rule packs.

### Rule Packs Enabled

```
p/security-audit      p/owasp-top-ten       p/secrets
p/supply-chain        p/python              p/javascript
p/typescript          p/java                p/ruby
p/go                  p/php                 p/django
p/flask               p/express             p/react
```

### Semgrep Workflow

1. `DeterministicToolRunner` runs Semgrep against all files in the manifest (excluding filtered paths).
2. Run with `--json` and `--timeout 30` per file.
3. Parse output as `SemgrepResult` Pydantic model.
4. Each match creates an `Evidence` record: `source_tool=semgrep`, `rule_id`, `file_path`, `line_start`, `line_end`, `message`.
5. Matches are stored in SQLite and linked to the corresponding `index_entry` for the file.
6. Index entries are updated with `semgrep_rule_ids` field.

### Additional Deterministic Scanners (Phase 2)

Beyond Semgrep:

- **`pip-audit`** / **`safety`**: Python dependency vulnerability check.
- **`npm audit`**: Node.js dependency vulnerability check.
- **Trufflehog patterns**: Supplementary secret detection (high-entropy strings, private key PEM headers).
- **CORS header analysis**: Static detection of `CORS_ALLOW_ALL`, `origins: *` patterns.
- **Insecure deserialization**: Detection of `pickle.loads`, `yaml.load()` without `Loader`, `ObjectInputStream`, `Marshal.load`.

---

## StaticAuditAgent

`StaticAuditAgent` is the AI-powered layer on top of deterministic scanning.

### Audit Packet Format

Each model call receives a structured audit packet (not raw file content):

```
AUDIT GOAL: Check for SQL injection risk

SCOPE: safe-active scan of example-app (localhost:3000)

FRAMEWORK: Django 4.2 with PostgreSQL

RELEVANT INDEX ENTRIES:
- auth/views.py:138-155  [tags: auth, sql, injection]
  login() function — constructs SQL query with format string

SEMGREP MATCHES in auth/views.py:
- Rule: python.django.security.audit.raw-query.raw-query (HIGH)
  Line 142: db.execute(f"SELECT * FROM users WHERE id = {user_id}")

FILE SNIPPET (auth/views.py:138-155):
[UNTRUSTED CODE — READ ONLY]
def login(request):
    user_id = request.POST.get('user_id')
    result = db.execute(f"SELECT * FROM users WHERE id = {user_id}")
    ...
[END UNTRUSTED CODE]

WHY SELECTED: Semgrep flagged raw SQL query with user input at line 142. Index tag: sql.

TASK: Evaluate this snippet for SQL injection risk. Propose CVSS vector. Assess false-positive likelihood. Provide reproduction steps if confirmed. Respond as structured JSON.
```

### AI Role

AI is used for:
- Reducing false positives (Semgrep sometimes matches safe patterns)
- Proposing CVSS vector based on code context
- Generating human-readable impact and reproduction steps
- Suggesting concrete fixes
- Grouping duplicate findings across files

AI is NOT used for:
- Claiming a file is vulnerable without a Semgrep or deterministic match
- Reading files not in the audit packet
- Running commands or making HTTP requests
- Inventing evidence

---

## EvidenceAgent (Phase 2 Foundation)

`EvidenceAgent` receives all evidence from Semgrep, other deterministic scanners, and AI reviews.

**Phase 2 responsibilities**:
- Normalize evidence records into canonical format.
- Apply `SecretRedactor` to all evidence text.
- Deduplicate: same rule ID + same file + overlapping line range → merge.
- Compute initial evidence weight per finding (from evidence scoring table in `Docs/scoring-system.md`).
- Reject finding candidates with zero evidence weight.
- Pass normalized findings to `VulnScoringAgent` (Phase 4 — stub in Phase 2, just stores in SQLite).

---

## Context Window Strategy

The audit pipeline never sends the entire repository to the model.

Required flow:

1. `ReconAgent` builds repository manifest + relevance scores.
2. `ReconAgent` writes `index.md` and stores index entries.
3. Semgrep and deterministic scanners produce candidate evidence.
4. `ContextManagerAgent` selects relevant snippets using tag-based ranking.
5. Snippets are grouped into audit packets (max tokens per call enforced).
6. `StaticAuditAgent` sends each audit packet to the LLM.
7. Findings are stored only when linked to Semgrep or deterministic evidence.

---

## Todo List

- [ ] Implement `ReconAgent` with manifest builder.
- [ ] Implement file relevance scoring.
- [ ] Implement language and framework detection.
- [ ] Implement `index.md` writer with all required sections.
- [ ] Implement index entry SQLite storage and tag-based retrieval.
- [ ] Implement ignore rules for excluded paths.
- [ ] Implement full `ContextManagerAgent` (snippet selection, budget, caching, cost tracking).
- [ ] Implement `PromptGuardAgent` (injection detection, content wrapping, security events).
- [ ] Integrate full Semgrep rule packs.
- [ ] Integrate `pip-audit` and `npm audit`.
- [ ] Implement `StaticAuditAgent` with audit packet format and structured output.
- [ ] Implement `EvidenceAgent` deduplication and normalization.
- [ ] Add test: `index.md` is created before any test execution.
- [ ] Add test: Semgrep matches are stored as evidence with rule IDs.
- [ ] Add test: PromptGuardAgent quarantines injection in scanned content.
- [ ] Add test: `ContextManagerAgent` rejects over-budget audit packets.
- [ ] Add integration test: full scan against vulnerable Flask fixture app.
- [ ] Validate that expected findings are produced for known vulnerabilities.

---

## Acceptance Criteria

Phase 2 is complete when:

- `.bughunter/runs/<run_id>/index.md` is created before any test execution.
- Later audit steps retrieve targeted snippets from index entries (not whole files).
- Semgrep runs all language packs against manifest files and stores evidence with rule IDs.
- `StaticAuditAgent` only receives bounded audit packets (enforced by `ContextManagerAgent`).
- `PromptGuardAgent` quarantines injection patterns in all tested scenarios.
- Static findings include exact Semgrep rule IDs, file paths, line ranges, and AI-assessed CVSS vectors.
- Integration test against vulnerable Flask fixture produces expected findings.
- Token usage and cost are tracked in `provider_usage` table.
