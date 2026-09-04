PART 00 — SESSION PROTOCOL (universal; loaded every session)
Version 1.1 — Owner-only edits, version bump required. PROGRESS.md records
the version executed. This file contains PROCESS rules only. All project
facts live in the plan's frozen PART-01 file (e.g. "PART-01 v1.0.md").

SESSION MECHANICS
- One session = one numbered unit of work, executed to completion.
- Only session(s) named in PART-01 §A may deploy or touch production.
- Never modify/rename/delete assets in PART-01 §A "legacy inventory"
  unless this session is explicitly scoped to do so.
- End every session: append ONE line to PROGRESS.md, canonical form:
  SESSION <n> | <YYYY-MM-DD> | gates: <passed gN ids, comma-separated> |
  status: PASS|PARTIAL|FAIL|BLOCKED[ — one-line reason] | P00 v<version>
- A failed verification gets ONE fix attempt. Second failure →
  BLOCKED.md (exact repro + what you tried) and STOP.
- Never resolve ambiguity by guessing. BLOCKED.md is a correct outcome.
- Missing credential/access for a step? Do NOT stall: write the exact
  command/SQL for the owner into BLOCKED.md and continue with everything
  that IS possible.

SOURCE-OF-TRUTH HIERARCHY
1. CODE — request/response shapes verbatim (snake_case stays snake_case).
2. The doc named "source of truth" in PART-01 §F.
3. Other §F artifacts.
Exceptions only where PART-01 §G explicitly overrides.

DEFAULT CONTRACTS (apply unless PART-01 §E overrides)
- Status codes: 400 unknown task/bad input/missing config row; 401 auth;
  402 metering; 500 unexpected; 502 provider exhausted (refund); 503 disabled.
- Metering: cost per invocation from §E. Consume BEFORE external calls;
  402 on insufficient balance; REFUND when the paid operation provably
  failed after consumption.
- Failover: on network error / timeout / 429 / 404 / 5xx → fallback
  provider. Both providers fail → 502 + refund. NO failover after first
  byte of a stream. Timeouts per §E.
- Streaming (only tasks listed in §E): normalized frames on the wire,
  ping comment frames at §E cadence, metering consumed before the stream
  opens.
- Runtime model policy in §E governs configured provider/model VALUES,
  not which coding agent executes sessions.
- Provider quirks (JSON-mode syntax, auth-header handling, capability
  limits) come from §G — never assume them.

PART-01 COMPLETENESS (hard gate)
The frozen PART-01 file ("PART-01 v1.0.md" — or a legacy PART-01.md with
a freeze header) must define sections A–F (G optional if empty). If a
section missing, stale-dated, or contradictory affects this session →
BLOCKED.md citing the section. The agent NEVER invents project facts.

ECONOMY RULES
- Be terse. Artifacts and verification output only. No prose about what
you're about to do, no concluding essays.
- Targeted reads: grep to locate, then read only needed line ranges.
  Never re-read content already extracted into plan artifacts.
- Never echo PART-00, PART-01, or large files — reference by path/section.
- One pass: do the work, run the gates, stop. No unsolicited review or
  refactoring outside session scope.
