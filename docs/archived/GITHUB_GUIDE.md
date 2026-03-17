````markdown
# GitHub Guide (archived)

This guide explains common Git/GitHub workflows used historically in the project.

---

## Branching Strategy

- `main` - stable release branch
- `develop` - integration branch (if used)
- `feature/*` - individual feature branches
- `hotfix/*` - urgent fixes

## Pull Request Workflow

1. Create a feature branch
2. Push changes to your fork
3. Open a PR against `main`
4. Add description, link to issues, and testing notes
5. Get reviews and address requested changes

---

## Release Notes

- Tag releases on `main` with semantic versioning
- Include changelog entries in PR descriptions

---

## CI / Tests

This project historically used a lightweight test harness in `financial-normalizer/run_tests.py`.

---

## Permissions & Maintainers

Maintainers with write access review and merge PRs.

---

## Archive Notice
This is an archived copy retained for reference. See `README.md` for the canonical workflow.

````
