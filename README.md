# Superpowers Codex

A distributable Codex plugin for review-gated development. Version 0.2.0 adds fixed
verification contracts, durable task ownership and dependencies, independent
finding-aware reviews, final integration review, and optional lifecycle hooks.

The runtime uses Python 3.9+ and its standard library. It targets macOS, Linux,
and Windows. Local development checks run on macOS; the included GitHub Actions
matrix covers all three platforms when this project is pushed to GitHub. A matrix
configuration is not evidence those remote jobs have already passed.

## Install from GitHub

Register this repository as a marketplace, then install the plugin:

```sh
codex plugin marketplace add Rascal/superpowers-codex
codex plugin add superpowers-codex@superpowers-codex
```

Start a new chat and run the **setup-superpowers-codex** skill. You can also install
through the desktop Plugins Directory after adding the marketplace: select the
**Superpowers Codex** source and install its plugin.

Review and trust the bundled hooks if you want them. Hooks consult only plans
explicitly bound to the current chat; installing the plugin does not bind chats.
Codex installs its own cached copy, so development edits in a checkout do not
silently modify a friend's installation.

The catalog at `.agents/plugins/marketplace.json` points to the plugin at the
repository root. No separate marketplace repository or server is needed.
Codex supports this [Git-backed marketplace workflow](https://developers.openai.com/plugins/build/plugins).
Bundled hooks require trust and manual desktop installation; hook-containing
plugins are not eligible for the universal public plugin directory.

## Install from a ZIP

For an offline transfer, build with `python3 scripts/build_plugin.py` (Windows:
`python`). The ZIP and SHA-256 file appear in `.review-gate/releases/`. Copy the ZIP
to the other computer, extract it to a permanent directory, and add that root:

```sh
codex plugin marketplace add /absolute/path/to/superpowers-codex-0.2.0
codex plugin add superpowers-codex@superpowers-codex
```

On Windows, quote the path, for example
`codex plugin marketplace add "C:\Tools\superpowers-codex-0.2.0"`.
Choose either the GitHub source or the extracted source for this marketplace.
The ZIP contains the same marketplace name and plugin; it is an alternative source,
not an additional installation.

## Python and hooks

Use Python 3.9 or newer. The CLI may be launched with `python3` or `python`.
Bundled hook commands use `python`, which must resolve to Python 3.9+ on PATH.
On a macOS/Linux machine that only provides `python3`, before registering the
extracted marketplace, edit the two commands in
`plugins/superpowers-codex/hooks/hooks.json` to use `python3` instead. Then install
and trust that hook definition. No shell alias or machine-specific path is baked
into the archive. Windows installations should enable Python on PATH.

## Use

Invoke the **review-gated-development** skill for a task or project. It records the
objective, constraints, prior decisions, acceptance criteria, check commands,
timeouts, and required output assertions before implementation. The CLI executes
that stored contract; an exit-zero command without the required output fails.

Every task needs independent review. Blocking findings must be resolved explicitly
by a reviewer. Completed implementation tasks feed a final integration task, whose
review covers the combined workspace before the plan can be called complete.

See [the workflow skill](skills/review-gated-development/SKILL.md) and
[CLI schemas and examples](skills/review-gated-development/references/cli.md).

Task records remain in each project’s `.review-gate/`, separate from the installed
plugin. Keep the workspace still during review. Work is serialized per workspace;
use separate worktrees for parallel development.

## Update and remove

For the GitHub source, refresh the marketplace and install the updated plugin:

```sh
codex plugin marketplace upgrade superpowers-codex
codex plugin add superpowers-codex@superpowers-codex
```

Start a new chat after updating. Re-review hook trust when the definition changes.
Release versions belong in `plugin.json`; Git tags can be selected with the
marketplace command's `--ref` option when you want a fixed release.

For ZIP installs, replace the extracted marketplace at its registered path with
the new release and refresh/reinstall through Codex. Task state remains in each
project's `.review-gate/`; never remove that directory during a plugin update.

Disable/uninstall the plugin in the app to stop loading its skills and hooks.
`codex plugin marketplace remove superpowers-codex` removes the source. Unbind a
chat with the CLI when it should stop following a plan. Neither operation deletes
task history. Earlier prototype ZIPs used the name `superpowers-codex-local`;
remove that old marketplace after switching to the GitHub source.

## Development checks

```sh
python3 -B -m unittest discover -s tests -v
python3 scripts/build_plugin.py
```

Tests cover failed and vacuous verification, stale code/rounds/dependencies,
ownership recovery, finding resolution, final integration, hook decisions, and
running the extracted plugin from a path containing spaces. Platform-specific
permission tests are skipped on Windows; process cleanup and locking tests run on
all platforms. The archive intentionally excludes task state, caches, tests, and
personal paths.

## Enforcement boundary

This is a cooperative local workflow. The CLI enforces its state transitions;
reviewer identities and local files remain trusted inputs. Output assertions do
not establish semantic correctness by themselves. Hooks ask Codex to continue or
surface incomplete work; they do not prevent bypassing the CLI or replace host
permissions. No API key, external service, or MCP server is required.

The hook adapter is tested using documented JSON inputs and outputs. Real host
installation/trust and Linux/Windows execution must be validated on those hosts
before claiming they passed; neither is implied by local unit tests.
