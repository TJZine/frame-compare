## Description

<!-- Describe your changes in detail -->

## Related Issue

<!-- Link to the issue this PR addresses, if applicable -->
Closes #

## Type of Change

<!-- Mark the appropriate option with an 'x' -->

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to change)
- [ ] 📚 Documentation update
- [ ] 🔧 Refactoring (no functional changes)
- [ ] 🧪 Test update
- [ ] 🏗️ Build/CI change

## Checklist

<!-- Ensure all items are completed before requesting review -->

### Code Quality

- [ ] My code follows the project's style guidelines (Ruff)
- [ ] Verification matches the changed claims using `.agents/project.md` and the applicable specialist runbook procedure
- [ ] When required, `uv run --no-sync ruff check .` and `uv run --no-sync ruff format --check .` pass
- [ ] When required, `uv run --no-sync pyright --warnings` passes with no new errors
- [ ] My changes generate no new warnings

### Testing

- [ ] I have identified the relevant existing, updated, new, or runtime proof for the changed behavior
- [ ] The reported commands/results apply to the current source state; skipped or unavailable platform proof is named
- [ ] Changed import boundaries have been checked with the canonical import-linter command in `.agents/project.md`

### Documentation

- [ ] I have updated the documentation accordingly

## PR Title Format

<!-- Ensure your PR title follows Conventional Commits format -->
<!-- This becomes the squash commit message -->

Examples:

- `feat(cli): add --json output flag`
- `fix(render): correct overlay positioning`
- `docs: update installation guide`
- `chore: update dependencies`

## Screenshots

<!-- If applicable, add screenshots to demonstrate visual changes -->

## Additional Notes

<!-- Any other information reviewers should know -->
