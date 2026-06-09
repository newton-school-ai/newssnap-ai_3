#!/bin/bash
# NewsSnap AI - Complete GitHub Setup Script
# Run each step in order. Do NOT skip steps.
#
# Prerequisites:
#   brew install gh
#   gh auth login  (pick GitHub.com > SSH > Login with web browser)
#
# Usage: Run each section one at a time (copy-paste blocks into terminal)

REPO="newton-school-ai/newssnap-ai"

echo "============================================"
echo "  NewsSnap AI - GitHub Setup"
echo "  Repo: $REPO"
echo "============================================"

# ======================================================
# STEP 1: Create repo on GitHub (skip if already exists)
# ======================================================
# Do this on github.com:
#   github.com/organizations/newton-school-ai/repositories/new
#   Name: newssnap-ai
#   Public, no README (we push our own)

# ======================================================
# STEP 2: Push scaffold to main
# ======================================================
# cd /Users/bipulkumar/Documents/aiprojects/newssnap-ai
# git init
# git add -A
# git commit -m "feat: initial project scaffold"
# git remote add origin git@github.com:newton-school-ai/newssnap-ai.git
# git push -u origin main --force

# ======================================================
# STEP 3: Create dev branch
# ======================================================
# git checkout -b dev
# git push -u origin dev
# git checkout main

# ======================================================
# STEP 4: Delete default GitHub labels
# ======================================================
echo ""
echo "--- Step 4: Deleting default labels ---"
gh label list --repo "$REPO" --json name --jq '.[].name' | while read name; do
  gh label delete "$name" --repo "$REPO" --yes 2>/dev/null
done
echo "Default labels deleted."

# ======================================================
# STEP 5: Create project labels
# ======================================================
echo ""
echo "--- Step 5: Creating project labels ---"

# Milestone labels (blue)
for i in 1 2 3 4 5 6 7 8; do
  gh label create "m$i" --repo "$REPO" --color "0075ca" --description "Milestone $i" --force
done

# Domain labels
gh label create "agent"          --repo "$REPO" --color "e4e669" --description "Agentic AI components" --force
gh label create "scraper"        --repo "$REPO" --color "d93f0b" --description "News scraping pipeline" --force
gh label create "recommendation" --repo "$REPO" --color "e4e669" --description "Recommendation engine" --force
gh label create "search"         --repo "$REPO" --color "e4e669" --description "Search system" --force
gh label create "snaps"          --repo "$REPO" --color "d93f0b" --description "Snap generation" --force
gh label create "frontend"       --repo "$REPO" --color "bfd4f2" --description "React Native / UI" --force
gh label create "infra"          --repo "$REPO" --color "c2e0c6" --description "Infrastructure, CI, Docker, DB" --force

# Status labels
gh label create "milestone"        --repo "$REPO" --color "0e8a16" --description "Milestone tracking" --force
gh label create "good first issue" --repo "$REPO" --color "0e8a16" --description "Easy entry point" --force
gh label create "needs-review"     --repo "$REPO" --color "fbca04" --description "PR ready for review" --force
gh label create "bug"              --repo "$REPO" --color "d73a4a" --description "Something is broken" --force
gh label create "enhancement"      --repo "$REPO" --color "a2eeef" --description "New feature request" --force

echo "Labels created. Verify:"
gh label list --repo "$REPO"

# ======================================================
# STEP 6: Create milestones
# ======================================================
echo ""
echo "--- Step 6: Creating milestones ---"

gh api repos/$REPO/milestones -f title="M1: Project Scaffold, DB, and Auth" \
  -f description="Week 1 - DB schema, Google OAuth + JWT, news source config, CI/Docker" \
  -f state="open"

gh api repos/$REPO/milestones -f title="M2: News Scraping Pipeline" \
  -f description="Week 2 - Playwright scraper, RSS scraper, article parser, 10-min scheduler" \
  -f state="open"

gh api repos/$REPO/milestones -f title="M3: AI Content Pipeline" \
  -f description="Week 3 - Dedup agent, story clustering, LLM summarizer, quality filter" \
  -f state="open"

gh api repos/$REPO/milestones -f title="M4: Translation and Snap Generation" \
  -f description="Week 4 - 5-language translator, snap image composer, image pipeline, templates" \
  -f state="open"

gh api repos/$REPO/milestones -f title="M5: Feed API, Search, and Interactions" \
  -f description="Week 5 - Personalized feed, Meilisearch, like/comment/share, trending" \
  -f state="open"

gh api repos/$REPO/milestones -f title="M6: Recommendation Engine" \
  -f description="Week 6 - Content-based + collaborative filtering, hybrid scorer, diversity" \
  -f state="open"

gh api repos/$REPO/milestones -f title="M7: Mobile App" \
  -f description="Week 7 - React Native swipe feed, search/explore, social features, profile" \
  -f state="open"

gh api repos/$REPO/milestones -f title="M8: Production Readiness" \
  -f description="Week 8 - Push notifications, 2-week cleanup, admin dashboard, E2E, deployment" \
  -f state="open"

echo "Milestones created. Verify:"
gh api repos/$REPO/milestones --jq '.[] | "\(.number): \(.title)"'

# ======================================================
# STEP 7: Configure branch rulesets
# ======================================================
# This must be done MANUALLY on GitHub:
#
# Go to: github.com/newton-school-ai/newssnap-ai/settings/rules
#
# --- Ruleset 1: Protect main ---
# Click "New ruleset" > "New branch ruleset"
#   Name: Protect main
#   Enforcement: Active
#   Bypass list: Add Faculty (org admin) ONLY
#   Target branches: Add target > Include by pattern > "main"
#   Rules to enable:
#     [x] Restrict deletions
#     [x] Require a pull request before merging
#         - Required approvals: 1
#         - Dismiss stale reviews: yes
#     [x] Require conversation resolution
#     [x] Block force pushes
#     [x] Restrict creations
#     [x] Restrict updates
#   NOTE: Skip "Require status checks" until CI runs once (Issue 1)
#
# --- Ruleset 2: Protect dev ---
# Click "New ruleset" > "New branch ruleset"
#   Name: Protect dev
#   Enforcement: Active
#   Bypass list: Add Faculty + Maintainer (student leader)
#   Target branches: Add target > Include by pattern > "dev"
#   Rules to enable:
#     [x] Restrict deletions
#     [x] Require a pull request before merging
#         - Required approvals: 2
#         - Dismiss stale reviews: yes
#     [x] Block force pushes
#   NOTE: Less restrictive than main (no restrict creations/updates)

echo ""
echo "--- Step 7: Branch rulesets ---"
echo "MANUAL STEP: Configure rulesets at:"
echo "  https://github.com/$REPO/settings/rules"
echo "  See instructions above for main and dev rulesets."

# ======================================================
# STEP 8: Create all 33 issues
# ======================================================
echo ""
echo "--- Step 8: Creating issues ---"
echo "Run: bash scripts/create_github_issues.sh"
echo "(This creates all 33 issues with labels and milestones)"

# ======================================================
# STEP 9: Create project board
# ======================================================
# MANUAL STEP on GitHub:
#   1. Go to: github.com/orgs/newton-school-ai/projects > New project
#   2. Select: Table view
#   3. Name: "NewsSnap Sprint Tracker"
#   4. Add all 33 issues to the board
#   5. Add Status field with values: Todo, In Progress, In Review, Done
#   6. Set all issues to "Todo"

echo ""
echo "--- Step 9: Project board ---"
echo "MANUAL STEP: Create project board at:"
echo "  https://github.com/orgs/newton-school-ai/projects"
echo "  Name: NewsSnap Sprint Tracker"
echo "  Columns: Todo | In Progress | In Review | Done"

# ======================================================
# STEP 10: Add pod members
# ======================================================
# 1. Invite to org: github.com/orgs/newton-school-ai/people
# 2. Set permissions at: github.com/newton-school-ai/newssnap-ai/settings/access
#    - Maintainer: "Maintain" role
#    - Contributors (4): "Write" role
# 3. Add Maintainer to dev ruleset bypass list
# 4. Add all to project board
# 5. Update names in POD_GUIDE.md

echo ""
echo "--- Step 10: Add pod members ---"
echo "MANUAL STEP: Invite members at:"
echo "  https://github.com/orgs/newton-school-ai/people"
echo "  Permissions at: https://github.com/$REPO/settings/access"

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  Verify: gh issue list --repo $REPO --limit 40"
echo "============================================"
