# Contributing

## Commit messages (Conventional Commits)
Use the form: `type(scope): short description`

Common types:
- **feat**: user-visible feature
- **fix**: bug fix
- **docs**: docs only
- **chore**: tooling/build/infra
- **refactor**, **perf**, **test**

Rules:
- Use imperative mood (“add”, not “added”).
- Keep subject ≤ 72 chars; body wraps at 72.
- **BREAKING CHANGE:** details in footer when applicable.
- Reference issues with `Refs #123` or `Fixes #123`.

Examples
- `feat(hdr): expose libplacebo mobius params`
- `fix(sdr): correct limited-range overlay washout`
- `chore(ci): run pyright/ruff/pytest on PRs`

Further reading: Conventional Commits 1.0.0.  (Verified 2025-11-09.)  
https://www.conventionalcommits.org/en/1.0.0/  
