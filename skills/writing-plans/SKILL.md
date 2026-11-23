---
name: writing-plans
description: Turn an independently approved spec into a detailed plan, obtain independent review, and present the reviewed revision to the user before implementation. Use after spec review or when continuing an existing Superpowers Codex planning record.
---

# Writing plans

Before any subagent dispatch, apply the mandatory
[subagent model and effort policy](../review-gated-development/references/subagents.md).

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

## Present the plan for human review

Read the independently approved `plan-packet`. In chat, show what will change,
the simplest viable approach using existing code, and how the outcome will be
checked. For each significant addition, name the requirement it serves today and
what it would take to deploy or maintain. A bounded plan can fit in a few
sentences. Whenever the chat gives a summary, link a readable copy of the full
reviewed plan with its steps, affected components and checks. Label the inline
plan or linked copy with the packet's revision ID and keep that ID with the question.

For planning-only work, deliver the reviewed plan and finish at `ready`. For
implementation, ask whether to **proceed with this revision, simplify it, or
hold**. Wait for the user's reply, even when the original brief requested
implementation. Leave an ambiguous response pending. On resume, use the decision
on the revision actually shown. If that connection is unclear, show the plan again.

- **Proceed.** A clear go-ahead on the shown revision suffices once. If execution
  intent is still missing, record it with `planning-authorize` using that same
  reply. Pass the ID you showed and the actual reply to `start-execution` using
  `--revision` and `--user-approval`. Then continue with review-gated-development.
- **Simplify or change.** Record the feedback, revise the plan, obtain fresh
  independent review, and show the new revision and what changed. If the feedback
  changes the spec's approach, constraints or scope, revise and re-review the spec
  first, even if the user-visible goal stays the same.
- **Hold.** Record the user's reason with `planning-block` and wait. When the
  user returns, use `planning-resume` to continue the requested discussion or
  handoff. Starting work still requires their go-ahead on the shown revision.

Read stage verdicts and findings when resuming. A rejected revision needs an author
update and a new submission; it cannot receive a second verdict. Submitted content
is immutable. After task import, changing requirements requires superseding the
plan, releasing old ownership as needed, and creating a reviewed replacement.
Carry unresolved findings and relevant decisions into its brief; preserve history.

Use the execution-only escape only for an explicit user choice to run external
contracts without this planning workflow. Record that reason; never choose it to
avoid a difficult review, missing information or a failed gate. In native Plan
mode, honor the host's write restrictions and stop before implementation.
