# Repository conventions

The Jira task-ID prefix requirement does not apply to branches or commits in this
personal repository. Use concise, descriptive branch names and commit messages.

Keep `.review-gate/` state and local caches out of commits and release archives.
Run `python -B -m unittest discover -s tests -v` before publishing changes.
Use an independent reviewer for implementation changes. Create pull requests only
when explicitly requested.
