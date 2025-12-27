# Contributing

This project uses PRs + squash merge to keep history readable and to support automated releases.

## Pull requests

1. Create a feature branch.
2. Open a PR to `main`.
3. Keep the PR title in Conventional Commits format (this becomes the squash commit message).

### PR title format

Use one of:

- `feat: <summary>`
- `fix: <summary>`
- `docs: <summary>`
- `refactor: <summary>`
- `perf: <summary>`
- `test: <summary>`
- `build: <summary>`
- `ci: <summary>`
- `chore: <summary>`
- `revert: <summary>`

Scopes are allowed but optional:

- `feat(cli): <summary>`
- `fix(render): <summary>`

## Releases

Releases are automated from `main` using Release Please (Release PR model).

### Bootstrap (first release)

For the initial cut, after the rebuild PR merges to `main`:

1. Create an annotated tag:
   - `git tag -a v0.1.0 -m "v0.1.0"`
2. Push the tag:
   - `git push origin v0.1.0`

After that, Release Please will open PRs like `chore(release): v0.1.1` based on merged PR titles.
