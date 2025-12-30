#!/bin/bash
# Script to remove .env files from git history
# WARNING: This rewrites git history. Make sure you have a backup!

echo "⚠️  WARNING: This will rewrite git history!"
echo "This will remove .env and .env.production from ALL commits."
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Removing .env files from git history..."

# Remove files from all commits
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env .env.production" \
  --prune-empty --tag-name-filter cat -- --all

# Clean up
git for-each-ref --format="delete %(refname)" refs/original | git update-ref --stdin
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo ""
echo "✅ .env files removed from git history"
echo ""
echo "⚠️  IMPORTANT: You need to force push to update GitHub:"
echo "   git push origin --force --all"
echo ""
echo "⚠️  WARNING: Force pushing rewrites history. Make sure all team members"
echo "   are aware and will need to re-clone or reset their local repos."
