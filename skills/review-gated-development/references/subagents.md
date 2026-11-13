# Mandatory subagent model and effort policy

Every subagent must use the main chat's current model, with reasoning effort capped
at Max. This applies to implementers, explorers, spec/plan/code reviewers,
integration reviewers, evaluators, and every further descendant.

| Main chat effort | Required subagent effort |
| --- | --- |
| Ultra (`ultra`) | Max (`max`) |
| Max or a lower supported effort | Same effort as the main chat |

No subagent may use Ultra. This cap is the only permitted effort adjustment; role,
cost, latency, or difficulty does not authorize other model or effort changes.
Change scope, context or approach when work stalls.

Before each dispatch:

1. Preserve the main chat's model through guaranteed inheritance or an explicit
   exact match. Resolve the required effort using the table above. For an Ultra
   parent, explicitly request `reasoning_effort: "max"` when supported, unless the
   chosen host configuration already guarantees that result. Leaving effort unset
   in an API that inherits Ultra violates the cap.
2. Omit an effort override only when inheritance guarantees the required effort.
   If a full-history fork or another mode only inherits Ultra and cannot override
   effort, use a supported dispatch mode that can request Max. Supply the needed
   task context separately; do not retain Ultra to preserve a fork.
3. If host defaults or a custom role would change either required setting, use a
   compatible role or explicitly supply the required model and effort. A role name
   in a brief does not authorize a model-specific profile. If the settings are
   unknown and no host guarantee establishes the required result, or the host
   cannot apply it, report the limitation instead of guessing. Do not rewrite
   user-global settings to work around it.
4. Carry the main model and resolved effort requirement into delegated briefs.
   Nested agents preserve those settings and the Max ceiling; the cap does not
   itself authorize delegation or impose a nesting-depth limit.

For a resumed agent, confirm its settings still satisfy the required model and
effort. Otherwise, stop the old agent and use a fresh compliant
agent with the recorded ownership handoff; never create concurrent writers for one
task.

Fresh review context is a separate requirement. Reviewers receive bounded artifacts
and the original request without the author's conversation, while keeping the same
model and required capped effort. Fresh context does not authorize other settings.

This is a mandatory dispatch rule for the coordinating agent. The task-state CLI
does not own the host's spawn API and cannot authenticate the effective model or
effort. Do not describe this instruction as a host-enforced lock or report runtime
compliance without supporting host metadata or guaranteed dispatch behavior.
