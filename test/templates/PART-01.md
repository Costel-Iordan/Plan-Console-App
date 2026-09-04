PART 01 — PROJECT CONTEXT: <plan-slug>
Owner-maintained. Freeze as "PART-01 v1.0" before Session 1; edits require
a version bump + owner approval. Sections A–F mandatory; G recommended.

A. MISSION & SCOPE
   Mission: <one paragraph>
   Session budget: <N> sessions.
   Session map (gates column: use stable ids — "g1: pytest green, g2: parity vs RECON §4"):
     # | one-line scope | gates | deploy?
     1 | ...            | ...   | no
     ... (last = deploy session, owner-supervised)
   Legacy inventory: <existing assets that stay frozen — paths, URLs, names>
   Out of scope: <explicit non-goals>

B. VERIFIED INFRASTRUCTURE FACTS   (every line: fact — verified YYYY-MM-DD)
   Hosts, versions, endpoints, auth schemes, env vars, hardware limits,
   capability constraints (e.g. "model X has no vision — date").

C. TARGET STRUCTURE
   Final file/function tree, paths only, one line each.

D. ROUTING / CONFIG TABLE   (the ONLY place task→provider→model lives)
   task | primary provider | model | fallback provider | model | cost
   Exact model IDs may live in a §F reference doc (e.g. PROVIDERS.md);
   never duplicated inline anywhere else.

E. BUSINESS RULES   (state only DELTAS from PART-00 defaults)
   Metering: <cost per task; refund semantics>
   Timeouts: <per provider class, e.g. local 90s / cloud 45s>
   Streaming: <which tasks; frame format; ping cadence>
   Runtime model policy: <allow/deny lists for configured VALUES>
   Error-code deltas: <if any>

F. ARTIFACTS MAP
   Source of truth: <path, e.g. RECON.md>
   Agent-appended: PROGRESS.md, BLOCKED.md
   Console-appended (agent never edits): HEALTH.md (Plan-health audit trail)
   Reference docs: <paths>
   Owner-only (agent never touches): <paths, e.g. BUDGET.md>

G. KNOWN QUIRKS & EXCEPTIONS
   Version-specific provider quirks (e.g. JSON-mode string form),
   response-shape exceptions, verbatim-header rules, anything that
   contradicts §C/§D expectations.
