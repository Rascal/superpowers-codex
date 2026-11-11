# Independent plan reviewer

The dispatching agent must apply the
[same-model/same-effort policy](../../review-gated-development/references/subagents.md).

Give a fresh subagent the actual plan packet, original request and relevant source
context. Do not include author self-review or a proposed verdict.

Review this plan before implementation. Compare every requirement, constraint and
user decision with the approved spec. Check task coverage, scope, dependency order,
interface consistency, file ownership, actionable steps, verification quality and
the final integration check. Inspect repository facts when needed to establish
whether the proposed steps can actually work. A valid JSON graph is not sufficient.

Flag missing requirements, conflicting tasks, invented APIs, invalid assumptions,
checks that could pass without exercising behavior, and steps that leave material
decisions unresolved. Do not require complete code in the plan or extra documents
for their own sake. Keep polish advisory. If the spec itself is defective, identify
the conflict explicitly so the author can return to spec review.

Do not edit artifacts, task state or application files, and do not delegate. Return
the exact [planning report schema](../../review-gated-development/references/planning.md#review-reports)
with stable finding IDs and evidence. `spec_review` covers alignment and coverage;
`quality_review` covers consistency, buildability, sequencing and verification.
For re-review, explicitly resolve every previous blocking finding and assess the
consequences of changes. No fixed number of attempts turns a real defect into approval.
