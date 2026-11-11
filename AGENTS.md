# Repository conventions

The Jira task-ID prefix requirement does not apply to branches or commits in this
personal repository. Use concise, descriptive branch names and commit messages.

Every subagent must use the main chat's model and reasoning effort. Use guaranteed
inheritance or explicitly match both settings; never change them for role, cost,
latency, or difficulty. Apply this rule to all descendants and keep fresh review
context separate from model selection.

Keep `.review-gate/` state and local caches out of commits and release archives.
Run `python -B -m unittest discover -s tests -v` before publishing changes.
Use an independent reviewer for implementation changes. Create pull requests only
when explicitly requested.
