---
name: setup-superpowers-codex
description: Check the runtime and explain activation of the Superpowers Codex plugin when a user installs it or asks to configure its review-gated workflow.
---

# Set up Superpowers Codex

Locate the installed plugin relative to this file. Never assume a personal home
directory or a particular cache version. Read the plugin's README for the supported
installation and update flow.

Check that `python3` resolves to Python 3.9+ on macOS/Linux, or `python` resolves
to Python 3.9+ on Windows. Bundled hooks select the interpreter through Codex's
`commandWindows` override. If the expected interpreter is unavailable, explain
that prerequisite. Do not install Python or change PATH without authorization.

Run the installed review-gate CLI with `--help` to verify imports and runtime.
Confirm that brainstorming, writing-plans, review-gated-development, and this setup
skill are discoverable. New work starts with brainstorming; existing execution
records can resume through review-gated-development.
Explain that task data stays in each target workspace's `.review-gate/`, outside
the installed plugin. Updating the plugin must preserve that directory.
Managed planning uses store format 3. Older 0.2 runtimes reject it; do not lower
the version field to make an older runtime proceed. The new runtime can read
legacy stores, without claiming their tasks had spec or plan review.

Confirm that SessionStart and Stop are listed in Settings > Hooks (or `/hooks` in
the CLI). An empty list is a discovery failure, not a trust prompt; do not describe
installation as verified until both are visible. This plugin uses the native
`.codex-plugin/plugin.json` entry point.

Hooks require the host's trust review. They are inactive for a chat until its real
session ID is explicitly bound to a plan with `bind`. Read the workflow skill to
create and bind a plan if the user asks to adopt it; setup alone does not authorize
starting implementation or binding unrelated chats. No API key or MCP service is
required. Do not claim that a CLI smoke check proves hooks are loaded by the host.
