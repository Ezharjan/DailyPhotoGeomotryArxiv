#!/usr/bin/env bash
# Commit the generated site/data (docs/) and push it, rebasing and retrying if
# the branch moved while the job was running.
# Usage: commit-and-push.sh "commit message"
set -euo pipefail

message="${1:?commit message required}"
branch="${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD)}"

git config user.name "${COMMIT_USER_NAME:-github-actions[bot]}"
git config user.email "${COMMIT_USER_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"

git add -A docs
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git commit -m "${message} ($(date -u +%Y-%m-%d))"

for attempt in 1 2 3 4 5; do
  if git push origin "HEAD:${branch}"; then
    echo "Pushed to ${branch}."
    exit 0
  fi
  echo "Push rejected (attempt ${attempt}); rebasing onto the latest ${branch}..."
  sleep $((attempt * 5))
  git pull --rebase origin "${branch}"
done

echo "::error::Could not push the update after 5 attempts."
exit 1
