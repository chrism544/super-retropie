#!/bin/bash
# Weekly check (Windows scheduled task "Super RetroPie repo sync", or cron): bring the repo up to date,
# stage what changed on the box, and write sync-report.txt. Nothing is committed or pushed - review with
# `git diff --cached --stat`, then `git commit && git push`.
cd "$(dirname "$0")/.." || exit 1
{
    echo "Super RetroPie sync - $(date '+%F %T')"
    git pull -q --ff-only || echo "!! could not update from GitHub (local changes?) - syncing anyway"
    bash tools/sync-from-box.sh; rc=$?
    echo
    if [ $rc -ne 0 ]; then echo "Not synced (exit $rc)."
    elif git diff --cached --quiet; then echo "No changes - GitHub matches the box."
    else echo "Staged, not pushed:"; git diff --cached --stat | tail -25
         echo; echo "Review: git diff --cached    Publish: git commit -m \"Sync from box\" && git push"; fi
} > sync-report.txt 2>&1
