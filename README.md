# Superpowers Codex

A distributable Codex plugin for review-gated development. Version 0.3.2 includes adaptive
brainstorming, independent spec review before planning, detailed implementation
plans, and independent plan review before execution. The existing verification,
task reviews, final integration review and optional lifecycle hooks remain.

All subagents must use the main chat's model, including every reviewer and
descendant. Reasoning effort is capped at **Max**: **Ultra → Max**; Max and lower
settings stay unchanged. An Ultra parent must request Max for its subagents unless
the host configuration already guarantees it. Defaults or custom profiles must not
silently change the required settings. Fresh context is independent of model choice.
This is mandatory dispatch guidance, not a host-enforced lock. See the
[subagent policy](skills/review-gated-development/references/subagents.md).

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
repository root. Its native manifest is `.codex-plugin/plugin.json`. No separate marketplace repository or server is needed.
Codex supports this [Git-backed marketplace workflow](https://developers.openai.com/plugins/build/plugins).
Bundled hooks require trust and manual desktop installation; hook-containing
plugins are not eligible for the universal public plugin directory.

## Install from a ZIP

For an offline transfer, build with `python3 scripts/build_plugin.py` (Windows:
`python`). The ZIP and SHA-256 file appear in `.review-gate/releases/`. Copy the ZIP
to the other computer, extract it to a permanent directory, and add that root:

```sh
codex plugin marketplace add /absolute/path/to/superpowers-codex-0.3.2
codex plugin add superpowers-codex@superpowers-codex
```

On Windows, quote the path, for example
`codex plugin marketplace add "C:\Tools\superpowers-codex-0.3.2"`.
Choose either the GitHub source or the extracted source for this marketplace.
The ZIP contains the same marketplace name and plugin; it is an alternative source,
not an additional installation.

## Hook discovery compatibility

Since version 0.2.2, the plugin uses the native `.codex-plugin/plugin.json` manifest. On the tested
Codex build, the portable root manifest loaded skills but silently omitted bundled
hooks; retaining that root manifest also masked the compatibility manifest. The
release therefore has one native entry point and no competing root `plugin.json`.

Both SessionStart and Stop must appear in the native hook list before installation
is considered verified. `scripts/check_native_hooks.py` checks the source manifest
through Codex's read-only metadata API; add `--require-installed` to check the
installed hook listing too. This does not trust hooks, execute them, or bind chats.
The setup skill remains available for explicit invocation.

## Python and hooks

Use Python 3.9 or newer. The CLI and default hooks use `python3` on macOS/Linux.
The documented `commandWindows` override uses `python` on Windows and reads the
installed path from `PLUGIN_ROOT` inside Python, so paths with spaces work without
shell-specific environment-variable syntax. Ensure that platform's interpreter is
on PATH; no `python` alias is needed on macOS/Linux.

After installation, open **Settings > Hooks** (or `/hooks` in the CLI) to review
and trust the two hook definitions. Codex skips untrusted hooks. A plugin update
that changes a hook or its script requires another review.

## Use

Start new work with **brainstorming**. It selects a spike, bounded or architectural
path, clarifies requirements and obtains independent spec review. Then
**writing-plans** creates detailed tasks and gets a separate fresh plan review.
**review-gated-development** executes the approved task graph. The fourth skill,
**setup-superpowers-codex**, checks installation and runtime prerequisites.

The pipeline is: clarify → spec → spec review → plan → plan review → execution.
Bounded work keeps artifacts short; architectural work receives deeper design and
interface analysis. A spike ends with evidence and a recommendation, without
importing implementation tasks.

Planning-only is the default for a new planning record. A reviewed plan can finish
without starting implementation. Record the user's actual implementation intent
when it is given; review approval itself does not grant permission to execute.

Spec/plan approvals bind to immutable revisions. Changed specs invalidate old plan
approval. Task import is atomic, checks requirement coverage and dependencies, and
pins both planning revisions. After import, changed requirements need a superseding
plan. Blocking findings must be explicitly resolved by an independent reviewer.

Every execution task runs its stored verification contract and receives independent
review. Final integration reviews the combined workspace and accumulated findings.
State persists in `.review-gate/`; only one task owns a workspace at a time. Use
separate worktrees for parallel implementation.

See [brainstorming](skills/brainstorming/SKILL.md),
[writing plans](skills/writing-plans/SKILL.md),
[planning schemas](skills/review-gated-development/references/planning.md), and
[execution commands](skills/review-gated-development/references/cli.md).

Managed planning creates store format 3. Upgrade the runtime before using it:
older 0.2 versions reject that format. Legacy stores remain readable, and existing
tasks are not retroactively described as having planning review. Deliberate direct
contract execution requires `--execution-only REASON`; it cannot bypass a managed
plan. Native Plan mode restrictions and planning-only user requests still apply.

## Update and remove

For the GitHub source, refresh the marketplace and install the updated plugin:

```sh
codex plugin marketplace upgrade superpowers-codex
codex plugin add superpowers-codex@superpowers-codex
```

Start a new chat after updating. Re-review hook trust when the definition changes.
Release versions belong in `.codex-plugin/plugin.json`; Git tags can be selected with the
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
python3 scripts/check_native_hooks.py
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

Native discovery is tested when the Codex CLI is installed; CI runners without
Codex skip that check. Tests on those runners still exercise packaging and hook
commands. Discovery and successful script execution do not grant hook trust: the
user reviews hooks in Codex before lifecycle execution is enabled.
