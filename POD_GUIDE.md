# Pod Guide - NewsSnap AI

## Pod Members

| Role | Name | GitHub Username |
|------|------|----------------|
| Faculty (Admin) | TBD | TBD |
| Maintainer (Student Leader) | TBD | TBD |
| Contributor 1 | TBD | TBD |
| Contributor 2 | TBD | TBD |
| Contributor 3 | TBD | TBD |
| Contributor 4 | TBD | TBD |

## Responsibilities

### Faculty
- Product Manager role
- Reviews milestones (M1-M8)
- Only person who merges dev into main
- Conducts Q&A sessions every 2-3 days per milestone
- Does NOT review individual PRs

### Maintainer (Student Leader)
- Reviews all PRs from contributors
- Merges approved PRs into dev (after 2+ approvals)
- Resolves merge conflicts on dev
- Tracks sprint progress on project board
- Does NOT write code or raise PRs

### Contributors (4)
- Work on all issues (not assigned to specific issues)
- Raise PRs targeting dev
- Review each other's PRs (provide 2 of 2 required approvals)
- Participate in Q&A sessions -- must be able to explain ANY code

## Collaboration Model

All 4 contributors work on all issues. Per issue, the team picks one approach:

### Option A: Competitive PRs

Best for straightforward issues where individual practice matters.

1. Each contributor implements independently on their own branch
2. Branch naming: `feature/issue-N-name-yourname`
3. Each raises a separate PR targeting dev
4. All contributors review all competing PRs
5. Minimum 2 approvals required
6. Maintainer merges the best implementation

### Option B: Collaborative PR

Best for complex issues where discussion adds more value.

1. Team discusses approach, agrees on design, splits work
2. One branch: `feature/issue-N-name`
3. One PR with all contributors as co-authors in commit message
4. Minimum 2 approvals from contributors
5. Maintainer reviews and merges

## Sprint Timeline (8 Weeks)

| Week | Milestone | Issues |
|------|-----------|--------|
| 1 | M1: Scaffold, DB, Auth | #1-4 |
| 2 | M2: Scraping Pipeline | #5-8 |
| 3 | M3: AI Content Pipeline | #9-12 |
| 4 | M4: Translation + Snaps | #13-16 |
| 5 | M5: Feed, Search, Interactions | #17-20 |
| 6 | M6: Recommendation Engine | #21-24 |
| 7 | M7: Mobile App | #25-29 |
| 8 | M8: Production Readiness | #30-33 |

## Q&A Sessions

- Frequency: every 2-3 days per milestone
- Format: Faculty asks any contributor to explain any code
- Scope: not just the code you wrote -- you must understand ALL code in the repo
- Purpose: ensure learning, prevent copy-paste, build defense skills

## Daily Standup (Async)

Post in team chat daily:
1. What I worked on yesterday
2. What I am working on today
3. Any blockers

## PR Review Checklist

Before approving a PR, verify:
- [ ] Code works (pull branch, run locally)
- [ ] Tests pass (`pytest tests/ -v`)
- [ ] Lint passes (`ruff check src/`)
- [ ] No hardcoded secrets or API keys
- [ ] Follows coding standards (type hints, docstrings)
- [ ] PR description links the issue and describes changes
- [ ] Acceptance criteria from issue are met

## Project Board

**Name:** NewsSnap Sprint Tracker
**Columns:** Todo | In Progress | In Review | Done

Move issues as you work:
- Pick up issue -> move to "In Progress"
- Raise PR -> move to "In Review"
- PR merged -> move to "Done"
