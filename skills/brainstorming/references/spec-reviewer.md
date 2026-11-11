# Independent spec reviewer

The dispatching agent must apply the
[same-model/same-effort policy](../../review-gated-development/references/subagents.md).

Give a fresh subagent the following request plus the actual packet and repository
context. Do not supply the author's self-assessment or a preferred verdict.

Review this design before implementation planning. Compare it with the original
request and relevant user clarifications. Assess whether requirements are complete,
observable, consistent and within scope; whether the approach is feasible; and
whether unresolved decisions or risks would cause someone to build the wrong thing.
Read relevant source when necessary. Match review depth to the recorded path.

Report material defects with evidence and a stable finding ID. Keep optional
improvements advisory. Preserve real user constraints; identify contradictions
instead of resolving them through unsupported assumptions. Approve only if no
blocking findings or material open questions remain. On re-review, resolve each
open blocking finding and check the changed spec's consequences.

Do not edit the spec, plan, application, task state, or review records. Do not
delegate. Return the exact [planning report schema](../../review-gated-development/references/planning.md#review-reports).
Use `spec_review` for alignment with the original intent and `quality_review` for
clarity, consistency, feasibility and risks. Your report is advice to the author;
the author owns fixes and records your actual verdict against this revision.
