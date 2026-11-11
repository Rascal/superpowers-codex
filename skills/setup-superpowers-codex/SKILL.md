---
name: setup-superpowers-codex
description: Check the runtime and explain activation of the Superpowers Codex plugin when a user installs it or asks to configure its review-gated workflow.
---

# Set up Superpowers Codex

Locate the installed plugin relative to this file. Never assume a personal home
directory or a particular cache version. Read the plugin's README for the supported
installation and update flow.

Check that `python` resolves to Python 3.9 or newer. The CLI can also be invoked
with `python3`, but bundled hook commands use `python` for the same command across
macOS, Linux and Windows. If only `python3` is available, explain the requirement
and offer the hook configuration described in the README. Do not install Python,
change PATH, or edit user configuration without the user's authorization.

Run the installed review-gate CLI with `--help` to verify imports and runtime.
Explain that task data stays in each target workspace's `.review-gate/`, outside
the installed plugin. Updating the plugin must preserve that directory.

Hooks require the host's trust review. They are inactive for a chat until its real
session ID is explicitly bound to a plan with `bind`. Read the workflow skill to
create and bind a plan if the user asks to adopt it; setup alone does not authorize
starting implementation or binding unrelated chats. No API key or MCP service is
required. Do not claim that a CLI smoke check proves hooks are loaded by the host.
