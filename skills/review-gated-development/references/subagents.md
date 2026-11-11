# Mandatory subagent model policy

Every subagent must use the main chat's current model and reasoning effort. This
applies to implementers, explorers, spec/plan/code reviewers, integration reviewers,
evaluators, and any further descendants. Role, cost, latency, or difficulty is never
a reason to select a different model or effort. Change scope, context or approach
when work stalls; do not upgrade or downgrade an agent independently.

Before each dispatch:

1. Use guaranteed inheritance from the main chat. In a spawn API that inherits
   both settings when omitted, leave model and reasoning-effort overrides unset.
   This is sufficient even when the host does not expose their literal values.
2. If host defaults or a custom role would override inheritance, use a compatible
   role or explicitly pass the main chat's exact settings when the host supports
   that. A role name in a review brief is a task description, not permission to
   choose a model-specific agent profile.
3. If neither guaranteed inheritance nor explicit exact matching is available,
   report the limitation instead of guessing or silently dispatching a different
   configuration. Do not rewrite user-global settings to work around it.
4. Carry this same-model/same-effort requirement into delegated briefs so nested
   agents preserve the main-chat settings too.

For a resumed agent, confirm its settings still match the main chat. If they no
longer match, stop the old agent and use a fresh matching agent with the recorded
ownership handoff; never create concurrent writers for one task.

Fresh review context is a separate requirement. Reviewers receive bounded artifacts
and the original request without the author's conversation, while keeping the same
model and reasoning effort. Fresh context does not authorize different settings.

This is a mandatory dispatch rule for the coordinating agent. The task-state CLI
does not own the host's spawn API and cannot authenticate the effective model or
effort. Do not describe this instruction as a host-enforced model lock or report
runtime parity without supporting host metadata or guaranteed inheritance.
