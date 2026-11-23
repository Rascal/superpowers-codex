# Planning lifecycle and CLI

`gate` below abbreviates `python3 /path/to/review-gated-development/scripts/review_gate.py
--workspace /path/to/project` (Windows: `python`). Keep draft/report files under the
project's `.review-gate/` so they do not change implementation snapshots. The tools
store immutable copies; later edits to input files have no effect until resubmitted.

## Start and classify

```sh
gate planning-create label-validation --path bounded \
  --reason "A small change to the existing label helper" \
  --author ACTUAL_AUTHOR_ID --brief .review-gate/brief.md
gate planning-status label-validation
gate bind --session REAL_HOST_SESSION_ID --plan label-validation
```

The brief is UTF-8 text containing the original request and relevant verbatim user
clarifications. Paths are `spike`, `bounded`, or `architectural`; the agent chooses
based on the requested outcome, uncertainty and impact. A classification change
needs a replacement record; preserve the old findings and decisions.

Records default to **planning-only**. If the user already requested implementation,
add `--execution-intent "Actual basis of the user's implementation request"` at
creation. This records intent, not tool permissions. Never invent authorization.

## Submit a spec

All fields below are required; list fields other than requirements may be empty.
Bounded work can use short text. Architectural work should explain interfaces,
alternatives, failure modes and risks at the depth needed to make sound decisions.

```json
{
  "goal": "Reject blank labels without changing nonblank behavior",
  "non_goals": ["No UI or persistence changes"],
  "requirements": [
    {"id": "R1", "description": "Empty or whitespace-only labels raise ValueError"},
    {"id": "R2", "description": "Nonblank labels retain the existing trimmed result"}
  ],
  "constraints": ["Keep the public function name format_label"],
  "user_decisions": ["Blank means empty or whitespace-only"],
  "approach": "Validate the normalized value in the existing helper",
  "alternatives": [],
  "risks": ["Existing callers may rely on an empty result"],
  "open_questions": []
}
```

```sh
gate spec-submit label-validation --author ACTUAL_AUTHOR_ID --file .review-gate/spec.json
gate spec-packet label-validation
gate spec-review label-validation --revision REVISION_FROM_PACKET \
  --reviewer ACTUAL_REVIEWER_ID --report .review-gate/spec-review.json
```

Submit copies the document and assigns a new revision ID and digest. One revision
accepts one review. A new submission always requires review, even if bytes are
identical. Draft questions can be stored but prevent approval. Packet output
contains the original brief, exact artifact, authors and finding history.

## Write and submit the detailed plan

Plan submission requires the current spec's approval. This complete example uses
one implementation task and one integration task. Adapt paths, steps and checks to
the actual repository; these commands are examples, not claims that its tests exist.

```json
{
  "summary": "Validate blank labels, preserve existing behavior, and verify integration",
  "tasks": [
    {
      "id": "labels-validation",
      "files": ["labels.py", "tests/test_labels.py"],
      "steps": [
        "Add test_rejects_blank and test_keeps_nonblank regression cases",
        "Validate the normalized value in format_label",
        "Run the label tests and inspect the results"
      ],
      "contract": {
        "objective": "Reject blank labels and preserve valid results",
        "plan": "label-validation",
        "kind": "implementation",
        "depends_on": [],
        "constraints": ["Keep the public function name format_label"],
        "user_decisions": ["Blank means empty or whitespace-only"],
        "criteria": [
          {"id": "C1", "description": "Blank input raises ValueError", "checks": ["labels"]},
          {"id": "C2", "description": "Valid input retains its trimmed result", "checks": ["labels"]}
        ],
        "checks": [{
          "id": "labels",
          "argv": ["{python}", "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_labels.py", "-v"],
          "timeout": 60,
          "assertions": [
            {"stream": "stderr", "contains": "test_rejects_blank"},
            {"stream": "stderr", "contains": "test_keeps_nonblank"},
            {"stream": "stderr", "contains": "\nOK\n"}
          ]
        }]
      }
    },
    {
      "id": "labels-integration",
      "files": [],
      "steps": ["Run the full suite and independently review the combined change and findings"],
      "contract": {
        "objective": "Verify the combined label change",
        "plan": "label-validation",
        "kind": "integration",
        "depends_on": ["labels-validation"],
        "constraints": ["Keep the public function name format_label"],
        "user_decisions": ["Blank means empty or whitespace-only"],
        "criteria": [{"id": "I1", "description": "The complete suite passes", "checks": ["suite"]}],
        "checks": [{
          "id": "suite",
          "argv": ["{python}", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
          "timeout": 60,
          "assertions": [{"stream": "stderr", "contains": "\nOK\n"}]
        }]
      }
    }
  ],
  "coverage": [
    {"requirement": "R1", "task": "labels-validation", "criteria": ["C1"]},
    {"requirement": "R2", "task": "labels-validation", "criteria": ["C2"]}
  ],
  "open_questions": []
}
```

IDs are workspace-wide, not per-plan. Every implementation task needs explicit
relative files and actionable steps. Use `/` separators; traversal, control
characters, Windows device names and invalid filename characters are rejected.
Unicode and literal bracketed route names are allowed. Path-length and host ACL
constraints still depend on the target environment.

Contracts must inherit every spec constraint and user decision. All requirements
must map to implementation criteria, and every implementation task must serve a
requirement. Tasks are ordered by dependencies. Exactly one final integration task
must depend on all implementation tasks. Existing contract/check rules still apply.

```sh
gate plan-submit label-validation --author ACTUAL_AUTHOR_ID --file .review-gate/plan.json
gate plan-packet label-validation
gate plan-review label-validation --revision REVISION_FROM_PACKET \
  --reviewer ACTUAL_PLAN_REVIEWER_ID --report .review-gate/plan-review.json
```

The plan packet includes the exact approved spec. Plan revisions pin its revision
ID and digest. Resubmitting a spec makes previous plan approval stale. Resubmitting
a plan makes its own approval stale. Preserve findings across revisions; explicitly
resolve each open blocking finding during re-review.

## Review reports

Both planning stages reuse the execution review report shape:

```json
{
  "verdict": "changes_requested",
  "spec_review": "R2 has no planned criterion or test",
  "quality_review": "The task graph is otherwise consistent",
  "findings": [{
    "id": "F1", "severity": "blocking",
    "detail": "Add coverage for preserved nonblank behavior",
    "evidence": "Plan coverage contains only R1"
  }],
  "resolutions": []
}
```

An approval uses `approved`; findings may be advisory, but no blocking finding may
remain open. Both assessment strings are required. Re-review resolutions name an
existing ID, `addressed`, `not_addressed`, or `false_positive`, and concrete evidence.
See [execution report examples](cli.md#findings-and-re-review).

Authors cannot approve their own artifacts. A planning reviewer cannot later
become an author of the same record. Skills request a fresh independent reviewer
for each stage; caller IDs and context independence remain cooperative assertions.
The CLI validates records and structure, not the semantic truth of a review.

## Handoff and scope

A planning-only record reaches `ready` after independent plan approval. Deliver
the reviewed plan. Its `plan-status` has `complete: true` with
`completion_scope: planning`. A record with implementation intent instead reaches
`awaiting_user_review`. SessionStart exposes the pending phase and revision.
Stop yields while the user considers the plan.

Present the independently approved `plan-packet` revision as described in the
[writing-plans handoff](../../writing-plans/SKILL.md#present-the-plan-for-human-review).
Keep the revision you actually showed. To start, pass that ID and the user's
affirmative reply on that plan as literal arguments. If the user requested only
a plan originally and now asks to implement the displayed revision, the same
reply supplies the intent and the go-ahead.

```sh
gate planning-authorize label-validation --author ACTUAL_AUTHOR_ID \
  --reason "ACTUAL_REPLY_TO_THE_SHOWN_PLAN"
gate start-execution label-validation --revision REVISION_SHOWN_TO_USER \
  --user-approval "ACTUAL_REPLY_TO_THE_SHOWN_PLAN"
```

The first command is needed only when intent is missing. An earlier implementation
request or agent verdict leaves the human decision pending. For feedback, revise
the affected spec or plan, repeat its independent review and present the new
revision. For a hold, record the reason with `planning-block`. Spikes, blocked
and superseded records cannot start execution.

On first import, `start-execution` checks the independent approvals, intent,
revision and nonblank reply before creating tasks. A stale ID or task collision
leaves the task list untouched. The resulting execution record stores
`user_approval` alongside `receipt.plan_revision`, `receipt.plan_digest` and
`started_at`. The CLI trusts the coordinator to relay the human's actual reply.
An agent resuming an existing import can call `start-execution PLAN` with no flags
to retrieve the original record. If both flags are supplied again, they must
match that record. Continue with the execution skill's claim/verify/review/complete
loop. Managed plans with execution intent finish after integration review.

For a user deliberately choosing external execution contracts, direct create/adopt
requires `--execution-only "Reason for the explicit exception"`. The reason is
retained, and status labels the mode. This escape is prohibited inside any managed
planning record. Do not use it as an automatic fallback from a failed planning gate.

## Spikes and recovery

A spike accepts no spec, implementation plan, or task import. After investigating,
submit JSON with `findings` and `recommendation` strings, a nonempty `evidence`
list, and a `limitations` list using `spike-finish PLAN --author ID --file FILE`.
Use actual observations/source references. The CLI checks the report structure;
it does not independently reproduce those observations. A completed spike's scope
is `investigation`.

```sh
gate planning-block label-validation --author ACTUAL_AUTHOR_ID --reason "Need the user's failure-policy decision"
gate planning-resume label-validation --author ACTUAL_AUTHOR_ID --reason "Decision received"
gate planning-supersede label-validation --author ACTUAL_AUTHOR_ID --reason "Requirements changed; replace the plan"
```

Block/resume preserves current artifacts and approvals. Supersession permanently
invalidates execution eligibility. After task import, artifact revisions are
rejected: supersede, release old task ownership, and create a reviewed replacement.
Carry unresolved findings and decisions into its brief. Existing release/block/
reopen/recover commands can maintain ownership but cannot revive superseded work.

Use planning-status, stage packets, their review_verdict fields and findings to
resume after interruption. All revisions and reviews remain in history. The runtime
reads store formats 1 through 4. A write to a store containing managed plans uses
format 4, which v0.3.2 and earlier cannot read. Reading status leaves the stored
format alone. Upgrade clients that share the workspace. A pending plan needs a
human decision on first import. An existing import keeps its original receipt,
including when it predates human review. Version-1 tasks still require adoption
into fixed contracts.
