# Robust Bug Hunter Checklist

## Product Robustness

- [ ] Scope file is mandatory for network testing.
- [ ] Local repo-only passive scans work without network targets.
- [ ] `index.md` is created before test planning.
- [ ] `testing/testN.md` files are created before execution.
- [ ] `test-results.md` is updated after every test.
- [ ] `bug-report.md` is generated from artifacts and evidence only.
- [ ] Interrupted runs can produce partial reports.
- [ ] Retesting reuses the original scope and test plan.

## Safety Robustness

- [ ] Central `SafetyPolicyEngine` gates every command, request, and test.
- [ ] Every test has `passive`, `safe-active`, `lab-validation`, or `blocked` classification.
- [ ] Destructive behavior is blocked by default.
- [ ] Race-condition tests have strict concurrency caps.
- [ ] File upload tests use benign files only.
- [ ] ZIP bomb and malware tests are blocked or lab-only simulations.
- [ ] Payment and business-logic tests require test data and explicit approval.
- [ ] Mobile certificate-pinning work is lab-only for owned apps/devices.

## AI Robustness

- [ ] Source files and HTTP responses are treated as untrusted input.
- [ ] Prompt-injection attempts in scanned content cannot override policy.
- [ ] Raw secrets are never sent to providers.
- [ ] Model calls receive bounded snippets selected from `index.md`.
- [ ] Findings without deterministic evidence are rejected.
- [ ] AI output is parsed as structured data, not blindly trusted.
- [ ] Provider timeouts and retries are bounded.
- [ ] Token usage is tracked per run.

## Security Coverage

- [ ] Core web checks.
- [ ] OWASP Web checks.
- [ ] OWASP API checks.
- [ ] Authentication and session checks.
- [ ] Authorization and IDOR/BOLA checks.
- [ ] Business logic checks.
- [ ] Injection and deserialization checks.
- [ ] File upload checks.
- [ ] Secret detection.
- [ ] Dependency and supply-chain checks.
- [ ] Client-side checks.
- [ ] Network checks.
- [ ] Cloud and infrastructure checks.
- [ ] Race-condition checks.
- [ ] Mobile API checks when scoped.
- [ ] Language/framework-specific checks.
- [ ] White-box checks.
- [ ] Black-box checks.

## Reporting Robustness

- [ ] Findings include severity and confidence.
- [ ] Confirmed findings include deterministic evidence.
- [ ] Reports separate bugs from hardening recommendations.
- [ ] Reports include reproduction steps.
- [ ] Reports include fix guidance.
- [ ] Reports include retest steps.
- [ ] Reports cite test IDs and evidence IDs.
- [ ] Reports include blocked tests and skipped tests where relevant.

