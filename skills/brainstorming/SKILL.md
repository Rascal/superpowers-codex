---
name: brainstorming
description: Clarify software ideas and choose spike, bounded, or architectural planning, with independent design/spec review before implementation in the Superpowers Codex workflow. Use for brainstorming, design, or a new coding request that needs this workflow.
---

# Brainstorming

Explore the repository and original request before choosing the depth of planning.
Native Plan mode is useful when active; do not invent mode-switch tools or bypass
its write restrictions. If writes are unavailable, discuss and review artifacts in
chat, then persist the exact artifacts and confirm their reviews when writes are
authorized. A planning-only request never authorizes implementation.

## Choose and explain the path

- **Spike:** the requested outcome is a feasibility answer or recommendation.
  Investigate cheaply, capture actual evidence and limitations, and keep any probe
  disposable. Production work needs implementation authorization and the spec/plan gates.
- **Bounded:** a clear change to an existing flow with limited impact and cheap
  reversal. Keep the spec and plan concise; both independent reviews still apply.
- **Architectural:** a new project/subsystem, cross-component interface, substantial
  uncertainty, or costly decision. Explore alternatives, contracts, failure modes,
  migration/recovery needs and verification in more depth.

Classify the requested outcome, not phrases such as “can you.” Explain the choice
briefly so the user can correct it. Reassess if scope or risk changes; supersede
the old planning record and create a replacement when its classification changes.

Ask only questions that materially change the outcome. Inspect available evidence
first, retain settled user decisions, and do not repeatedly request approval for
already-authorized work. Challenge assumptions and compare viable alternatives.

## Register and develop the spec

Use `../review-gated-development/scripts/review_gate.py` relative to this skill.
Read [planning commands and schemas](../review-gated-development/references/planning.md).
The CLI path is inside the installed plugin; `--workspace` names the user's project.
Store drafts/reports under that project's `.review-gate/` or an agreed document
location. Submitted snapshots, not subsequently edited draft files, are authoritative.

1. Save the original request and relevant verbatim user clarifications as the brief.
   Register `planning-create` with the selected path, rationale and actual author ID.
   Records default to planning-only. Use `--execution-intent REASON` only when the
   user has already requested implementation, recording that actual intent.
   If using trusted hooks, explicitly bind the current real session ID to this plan.
   A previous binding must be deliberately unbound before adopting a new plan.
2. For a spike, perform the investigation and use `spike-finish` to record findings,
   actual evidence, recommendation and limitations. For a spike-only request, stop after reporting the answer.
   Authorized production follow-up needs a separate bounded/architectural planning
   record; preserve any implementation authorization already given by the user.
3. For bounded/architectural work, write the spec: goal, non-goals, observable
   requirement IDs, constraints, existing user decisions, approach, alternatives,
   risks and open questions. Scale depth to the path. Resolve material uncertainty
   before approval; block the planning record while waiting for necessary input.
4. Submit the spec. Dispatch a fresh reviewer without the author's conversation,
   using [the spec reviewer brief](references/spec-reviewer.md), the packet and
   relevant repository context. The reviewer reports findings and never edits.
5. Record the actual report using the actual reviewer ID. The author fixes blocking
   findings, submits a new revision and obtains re-review. Every revision needs its
   own approval; no automatic waiver after repeated failures. If progress stalls,
   record the blocker or obtain the missing decision.
6. Only after current spec approval, continue with `writing-plans`. Do not start
   detailed implementation planning or application changes before that gate.

User clarifications belong in the spec's user_decisions as faithful statements;
give reviewers the relevant original excerpts too. A reviewer may challenge a
spec assumption but cannot silently override a binding user decision. Planning
review is a separate stage from later checking whether implemented code matches it.
