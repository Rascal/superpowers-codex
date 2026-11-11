# CLI contract

Use `python /path/to/skill/scripts/review_gate.py --workspace /path/to/project`.
Here `gate` abbreviates that full command. Python 3.9+ is required. `python3` can
also launch the CLI. On Windows use normal Windows paths; quote paths with spaces.

The CLI emits JSON on stdout; rejected operations emit JSON on stderr and exit 1.
Argument errors exit 2. State lives only in the project's `.review-gate/state.json`.
The plugin's installation directory is never used as a task store.

## Plan before creating execution tasks

New work uses [the planning lifecycle](planning.md): brainstorming, spec review,
plan writing and plan review, then atomic task import. Direct create/adopt below
is only for an explicit execution-only choice. Existing legacy task records remain
usable without manufactured planning approvals.

## Create a fixed contract

Save a contract in `.review-gate/task.json`, or supply JSON on stdin with `-`:

```json
{
  "objective": "Reject negative input prices",
  "plan": "price-validation",
  "kind": "implementation",
  "depends_on": [],
  "constraints": ["Keep the existing API signature"],
  "user_decisions": ["Reject invalid input with ValueError"],
  "criteria": [
    {"id": "C1", "description": "Negative prices raise ValueError", "checks": ["price-tests"]}
  ],
  "checks": [
    {
      "id": "price-tests",
      "argv": ["{python}", "-B", "-m", "unittest", "tests.test_prices", "-v"],
      "timeout": 60,
      "assertions": [{"stream": "stderr", "contains": "\nOK\n"}]
    }
  ]
}
```

All top-level fields are required; arrays for constraints, decisions, and
prerequisites may be empty. IDs use letters, digits, `_`, `-`, and `.`, starting
with a letter or digit. Each criterion references one or more check IDs and every
check must be referenced. A check has exact argv, a timeout greater than zero and
at most 300 seconds, and one or more nonempty literal output assertions.
`{python}` in argv[0] uses the interpreter running the CLI. Other arguments are
literal; no shell interpolation is performed.

Choose assertions that prove the intended runner actually executed, preferably a
stable test count or explicit structured-result marker as well as its success
marker. A command that prints a misleading marker can still fool an assertion;
the independent reviewer must assess the check itself. Put numerical comparisons
and other domain-specific pass conditions in a versioned verification script that
exits nonzero on failure. For multiple targets, use separate checks with explicit
target arguments; for one-then-all ordering, use dependent tasks.

Contracts are copied and hashed at creation. Editing the source JSON afterward
changes nothing. Direct creation needs a nonempty execution-only reason and cannot target a managed
planning record. There is no verify-time command or timeout override and no
contract-edit command. Create a new task/plan for changed requirements.

```sh
gate create prices --contract .review-gate/task.json --execution-only "User supplied external execution contracts"
gate claim prices --owner actual-agent-id
gate verify prices --owner actual-agent-id
gate request-review prices --owner actual-agent-id
gate packet prices
gate review prices --round ROUND_FROM_PACKET --reviewer actual-reviewer-id --report .review-gate/review.json
gate complete prices --owner actual-agent-id
gate show prices
gate list
```

Store generated reports under `.review-gate/` so writing them does not invalidate
source evidence. `--report -` also accepts stdin. All required checks execute; each
criterion receives its own check references and pass/fail result. Exit zero alone
is insufficient. Each output stream retains its last 32 KiB, with a truncation
flag. Assertions inspect that retained output, with CRLF normalized to LF; emit
summary markers at the end of long runs. Timeout cleanup terminates the process
group on POSIX and the process tree with Windows `taskkill`. Commands must not
detach processes or leave background services running.

## Findings and re-review

```json
{
  "verdict": "changes_requested",
  "spec_review": "C1 is missing for values below zero.",
  "quality_review": "Existing tests cover only positive values.",
  "findings": [
    {"id": "F1", "severity": "blocking", "detail": "Negative values are accepted.", "evidence": "prices.py:12; reproduced with -1"}
  ],
  "resolutions": []
}
```

An approval uses `"verdict": "approved"`. New findings use unique IDs and severity
`blocking` or `advisory`; advisory findings remain visible without blocking task
completion. Each round accepts one report. Reviewers must differ from every
recorded implementer, including prior owners after recovery.

For re-review, explicitly address each existing open blocking finding:

```json
{
  "verdict": "approved",
  "spec_review": "C1 is satisfied by the new validation.",
  "quality_review": "The fix and regression cover the boundary.",
  "findings": [],
  "resolutions": [
    {"id": "F1", "status": "addressed", "evidence": "prices.py:12 and test_prices.py:28"}
  ]
}
```

Resolution status is `addressed`, `not_addressed`, or `false_positive`, each with
nonempty evidence. Open blocking findings cannot disappear by omission, severity
change, or a fresh approval. A false positive requires a reviewer explanation.
There is no automatic retry-count waiver.

Packets contain requirements, verification evidence, open and resolved findings,
the full current manifest, and changed paths since the previous reviewed snapshot.
They do not retain original source contents; the reviewer reads current source
and an available Git diff. A fix packet scopes re-review without prohibiting
necessary investigation outside those files.

## Ownership, dependencies, and integration

```sh
gate block prices --owner actual-agent-id --reason "Required fixture is unavailable"
gate release prices --owner actual-agent-id --reason "Pause while the fixture is repaired"
gate claim prices --owner actual-agent-id
gate recover prices --owner old-agent-id --new-owner new-agent-id --reason "Host confirmed the previous agent is unavailable"
gate reopen prices --owner actual-agent-id --reason "A new regression requires changes"
```

Only one unfinished task can own a workspace. Completed task owners are retained
as provenance. Claim by the same current owner is idempotent. Recovery records an
explicit transfer; it does not guess agent liveness. Release, recovery, and reopen
invalidate current evidence while preserving attempts and findings.

Dependencies must already exist in the same plan, so creation order forms an
acyclic graph. They must be completed before claim and verification. Receipts bind
dependents to each prerequisite's generation and reviewed attempt. Reopening or
reverifying a prerequisite makes old dependent receipts invalid.

Create exactly one task with `"kind": "integration"` and `depends_on` naming every
implementation task in the plan. Its contract should verify the combined result.
Creating it seals that plan against new tasks. Its reviewer gets the accumulated
findings and assesses the whole change. Only a completed, current integration
review permits `plan-status` to report `complete: true`:

```sh
gate plan-status price-validation
```

Earlier completed tasks are historical checkpoints; later implementation changes
naturally alter the workspace. Final integration checks the combined current
snapshot. Reopened prerequisites still invalidate dependent checkpoints.

## Optional Codex hooks

```sh
gate bind --session REAL_HOST_SESSION_ID --plan price-validation
gate unbind --session REAL_HOST_SESSION_ID
```

Trust the bundled hooks in Codex before relying on them. Binding is explicit and
per chat. SessionStart returns recovery context; Stop consults plan status and
requests a continuation for unfinished work. A recorded blocker or an already
active continuation emits a visible warning instead of another continuation.
Interrupt is never blocked. Unknown/unbound chats are unaffected. Hook errors
are visible and never count as approval. The adapter does not parse transcripts,
intercept Git commands, or authenticate caller-supplied agent IDs.

## Persistence and compatibility

Snapshots include file contents, paths, directories (including the root and empty
directories), permission modes, and untracked/Git-ignored files. Only root `.git`,
root `.review-gate`, and actual `__pycache__` directories are excluded. Symlinks and
special files are unsupported. Keep dependencies and generated reports outside
the source snapshot. External services, environment variables, executable versions,
and platform-specific ACLs are not fingerprinted. Workspaces must stay quiescent
through verification and review; fingerprints are not atomic filesystem snapshots.

State replacement is atomic and lock acquisition has a five-second timeout. All
CLI mutations use the lock. A process interruption may leave verification marked
`running`; rerun it before review. Windows uses byte-range locks, POSIX uses flock.

Version-1 task records remain readable but cannot be completed under the new
rules. `adopt ID --contract FILE --execution-only REASON` preserves their original objective, criteria,
baseline, and full legacy record while clearing eligibility for completion. Fresh
ownership, verification, and review are required. Existing completed history is
never silently promoted to stronger verification guarantees.

Planning-managed stores use format 3 so older runtimes fail closed. See the
[planning compatibility rules](planning.md#spikes-and-recovery).
