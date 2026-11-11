---
name: writing-plans
description: Turn an independently approved spec into detailed task contracts and obtain independent plan review before execution in the Superpowers Codex workflow. Use after spec review or when continuing an existing planning record.
---

# Writing plans

Before any subagent dispatch, apply the mandatory
[same-model/same-effort policy](../review-gated-development/references/subagents.md).

Use the CLI and [planning schema](../review-gated-development/references/planning.md)
from the sibling review-gated-development skill. Read planning-status and the
current spec packet. If current spec approval is missing, return to brainstorming;
do not substitute implementation review or a self-check for that approval.

## Write an actionable plan

Read relevant code, interfaces and tests. Preserve the spec's exact constraints and
user decisions. Make tasks coherent and independently verifiable. For each task,
provide a globally unique ID, explicit relative files, actionable steps, acceptance
criteria, concrete verification commands/timeouts/assertions and dependencies.
Name IDs after the plan and behavior to avoid collisions with earlier history.

Include implementation detail that removes ambiguity: API signatures, data shapes,
ordering, error behavior and test cases. Full implementation code is not required
in every step. Mark unresolved decisions explicitly instead of inventing APIs or
verification results. Bounded plans may have one implementation task; architectural
plans need appropriate decomposition, interface consistency and dependency analysis.

Map every spec requirement to implementation-task criterion IDs. Ensure each
implementation task serves a requirement, and all contracts inherit global
constraints and user decisions. End with exactly one integration task depending
on every implementation task and verifying their combined behavior.

## Independently review before handoff

1. Submit the plan against the currently approved spec. The CLI validates structure,
   coverage and dependency ordering, but an independent reviewer must assess meaning.
2. Dispatch a different fresh subagent for this stage, without author conversation,
   using [the plan reviewer brief](references/plan-reviewer.md), the plan packet,
   original request and relevant repository context. The packet includes the exact
   approved spec. Reviewers report findings; they do not fix or rewrite artifacts.
3. Record the real report and reviewer ID. Fix blocking findings as the author,
   resubmit and re-review. If a finding reveals a spec defect, revise and re-review
   the spec first, then submit a plan against that new approved spec revision.
4. For planning-only intent, report the approved artifacts and stop at `ready`.
   Review approval itself is not user authorization to implement.
5. When implementation is already authorized, record its actual basis with
   `planning-authorize` if no execution intent was recorded at creation. Do not
   re-ask for settled authorization. Then run `start-execution`. It atomically
   imports only the reviewed tasks and binds them to exact planning receipts.
   Continue with review-gated-development; do not manually recreate those tasks.

Read stage verdicts and findings when resuming. A rejected revision needs an author
update and a new submission; it cannot receive a second verdict. Submitted content
is immutable. After task import, changing requirements requires superseding the
plan, releasing old ownership as needed, and creating a reviewed replacement.
Carry unresolved findings and relevant decisions into its brief; preserve history.

Use the execution-only escape only for an explicit user choice to run external
contracts without this planning workflow. Record that reason; never choose it to
avoid a difficult review, missing information or a failed gate. In native Plan
mode, honor the host's write restrictions and stop before implementation.
