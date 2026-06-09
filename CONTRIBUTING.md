# Contributing to NewsSnap AI

## Branch Strategy

```
main  (stable - milestone-complete merges only)
 |
 +-- dev  (all feature branches merge here)
      |
      +-- feature/issue-N-short-name
```

- Never push to main directly
- All PRs target dev
- Maintainer merges to main after milestone review

### Branch Naming

```
feature/issue-5-playwright-scraper
fix/issue-9-dedup-threshold
docs/issue-2-db-schema
```

For competitive PRs, append your name: `feature/issue-5-playwright-scraper-alice`

## PR Workflow

1. Create branch from dev: `git checkout -b feature/issue-N-name dev`
2. Make changes, commit with descriptive messages
3. Push: `git push origin feature/issue-N-name`
4. Open PR targeting dev on GitHub
5. Fill in PR template (link issue, describe changes, testing done)
6. Request 2 reviews from other contributors
7. Address review comments
8. Maintainer merges after 2 approvals

## Commit Messages

Format: `type: short description`

Types: feat, fix, docs, test, refactor, chore

Examples:
- `feat: add playwright scraper for NDTV`
- `fix: handle missing og:image in article parser`
- `test: add dedup agent unit tests`
- `docs: update source config documentation`

## Coding Standards

### Python (Backend)
- Python 3.11+
- Linting: ruff (configured in pyproject.toml)
- Type hints on all function signatures
- Docstrings on all public functions
- Tests in tests/ directory using pytest
- Async where applicable (FastAPI, scrapers)

### TypeScript (Frontend)
- TypeScript strict mode
- ESLint + Prettier
- Functional components with hooks
- Props interfaces for all components

### General
- ASCII-only in all files (no em dashes, arrows, special characters)
- Environment variables in .env (never commit secrets)
- All tests must pass before PR

## Pod Roles

| Role | Permission | Responsibility |
|------|-----------|---------------|
| Faculty | Admin | Reviews milestones, merges dev to main |
| Maintainer | Maintain | Reviews PRs, merges to dev, does NOT write code |
| Contributors (4) | Write | Build features, raise PRs, review each other |

## Collaboration Model

Per issue, team picks one approach:

**Option A: Competitive PRs** -- Each contributor implements independently, best implementation merged.

**Option B: Collaborative PR** -- Team designs together, one PR with co-authors.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_dedup_agent.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Lint
ruff check src/
```

## Verify No Special Characters

```bash
grep -rPn '[^\x00-\x7F]' --include="*.md" --include="*.py" --include="*.sh" . | grep -v '.git/'
```

This should return empty. If it finds matches, replace special characters with ASCII equivalents.
