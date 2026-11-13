---
name: review-gated-development
description: Execute independently reviewed plans with fixed verification contracts, durable ownership, and independent task reviews. Use when implementing an approved Superpowers Codex plan or resuming its execution workflow.
---

# Review-gated development

Before any subagent dispatch, apply the mandatory
[subagent model and effort policy](references/subagents.md).

Require independent review for every coherent implementation task in this workflow.
Scale planning to uncertainty and impact. Honor existing user authorization; do not
ask again for settled decisions or automatically commit, push, or open a PR.

Locate `scripts/review_gate.py` relative to this skill. Use Python 3.9+ and pass the
complete project root with `--workspace`. Keep reports and contract drafts inside
that root's `.review-gate/` or outside the project, so they do not change snapshots.
Read [the CLI contract](references/cli.md) for schemas and commands.

## Before implementation

- For new work, use brainstorming followed by writing-plans. They obtain separate
  independent spec and plan reviews. `start-execution` imports their approved
  contracts; do not recreate or alter imported tasks manually. Planning-only intent
  stops after plan review. See [planning lifecycle](references/planning.md).
- For existing tasks, inspect execution_mode. Legacy records remain executable
  under their original guarantees. New direct create/adopt requires an explicit
  user choice and `--execution-only REASON`; it cannot bypass a managed plan.
- Record the objective, constraints, user decisions, criterion IDs, dependencies,
  and exact verification commands in the contract. Each criterion must map to
  checks; each check needs a timeout and positive output assertions. Include target
  identifiers in command arguments when verifying multiple instances. Preserve
  user-specified proof mechanisms. An exit code alone is insufficient evidence.
- Infer routine verification choices from the repository. Ask only when missing
  information materially affects correctness, scope, or authorization. Do not
  replace an expensive required check with a cheaper one.
- Imported task sets already contain ordered dependencies and final integration.
  For an explicitly chosen execution-only workflow, create tasks in dependency
  order and end with one integration task depending on every implementation task.
  Changed requirements need a superseding/new plan; do not weaken stored contracts.
- Claim each task using the actual implementing agent ID before editing. Only one
  task can own a workspace at a time. Use separate worktrees for parallel work.
  A pending dependency blocks claim. Resume existing owners; do not duplicate them.

## Implement, verify, and review

1. Implement the task. The coordinator may implement small tasks directly;
   substantial independent tasks can use a fresh implementer subagent. Give the
   implementer its contract and relevant context without the entire conversation.
2. Invoke `verify`; it runs only the stored commands. Inspect every criterion's
   captured evidence, including output assertions. Incomplete or interrupted runs
   require fresh verification. Never describe absent evidence as a pass.
3. Invoke `request-review` and keep the workspace still. Spawn a fresh reviewer
   without forking the conversation. Supply the original request, current packet,
   relevant repository instructions, and access to source and diff. Do not supply
   the implementer's reasoning or a desired verdict.
4. The reviewer checks specification compliance and quality independently and
   returns the structured report. Review is read-only. Targeted tests and reading
   surrounding code are allowed when needed to establish a finding. Findings need
   stable IDs, severity, concrete detail, and evidence. Record the actual report
   with the actual reviewer ID; no implementer may approve their own work.
5. Fix blocking findings as the implementer, verify again, and request re-review.
   The packet identifies prior findings and files changed since review. Focus on
   those findings and the consequences of the fix; expand review if interfaces or
   earlier assumptions changed. Every prior blocking finding needs an explicit
   resolution with evidence. Record valid disagreement as `false_positive` with
   evidence. An iteration limit never makes a real blocking defect acceptable.
6. Invoke `complete` only after approval. Advisory findings remain visible. After
   all implementation tasks, execute and independently review the integration
   task against the entire change and accumulated findings. Check `plan-status`
   before claiming the plan is complete.

## Recovery and optional hooks

Read `list`, `show`, and `plan-status` after context loss. Preserve user decisions
and history. If the recorded agent is unavailable, confirm that through the host
before `recover`; record the old owner, new owner, and reason. Release or reopen
invalidates current evidence. Reopening a prerequisite invalidates dependent
receipts even when its source later returns to the same bytes.

Use `block` with a concrete reason when no defensible next step remains; tell the
user what is needed. Release a blocked workspace explicitly if independent work
can proceed. Do not infer agent death from a missing notification.

Bundled hooks require host trust and an explicit session-to-plan `bind`. Bind only
when the user adopts this workflow for that chat, using the real host session ID.
The SessionStart hook can expose that ID. Stop requests one continuation for
unfinished work; blocked work or a repeated continuation produces a visible
warning instead. User interruption takes priority. The adapter reads structured
state and never interprets success phrases as proof.

This is a cooperative local gate, not authenticated identity or a security boundary
against an agent with filesystem access. Output assertions check the declared
observable, not semantic correctness. Hooks do not prevent bypassing the CLI, and
read-only reviewer instructions do not create a separate filesystem sandbox.
