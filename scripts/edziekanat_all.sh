#!/usr/bin/env bash
#
# Refresh EVERY WCY group's calendar from the e-Dziekanat, logged in as
# one student, and push the .ics files to GitHub. Meant for cron on a
# machine that can reach s1.wcy.wat.edu.pl (a home Raspberry Pi; not the
# WAT campus network, which cannot reach it).
#
# Credentials come from the environment and are never written to disk by
# this script:
#   WATCAL_ME_USER   e-Dziekanat identifier ("Imie Nazwisko")
#   WATCAL_ME_PASS   e-Dziekanat password
# Put them in ~/.watcal-me.env (chmod 600); this script sources it.
#
# Other environment:
#   WATCAL_REPO          clone to work in (default: this script's repo)
#   WATCAL_DEPLOY_KEY    SSH key to push with (GitHub deploy key, write)
#   WATCAL_BRANCH        branch to sync and push (default: main)
#   WATCAL_ME_DELAY      seconds between groups (default 5)
#
# Runs in a DEDICATED clone (e.g. ~/watcal-remote): every run does
# `git reset --hard origin/main`, discarding local changes, which keeps
# it conflict-free with the Actions bot's commits.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${WATCAL_REPO:-$SCRIPT_DIR/..}"
cd "$REPO"

[ -f "$HOME/.watcal-me.env" ] && . "$HOME/.watcal-me.env"
: "${WATCAL_ME_USER:?set WATCAL_ME_USER (in ~/.watcal-me.env)}"
: "${WATCAL_ME_PASS:?set WATCAL_ME_PASS (in ~/.watcal-me.env)}"
export WATCAL_ME_USER WATCAL_ME_PASS

BRANCH="${WATCAL_BRANCH:-main}"
DELAY="${WATCAL_ME_DELAY:-5}"
PYTHON="${WATCAL_PYTHON:-python3}"
log(){ echo "[$(date -u +'%F %T')] $*"; }

# One run at a time.
exec 9>"$(git rev-parse --git-dir)/edziekanat.lock"
flock -n 9 || { log "another run is in progress, exiting"; exit 0; }

if [ -n "${WATCAL_DEPLOY_KEY:-}" ]; then
    export GIT_SSH_COMMAND="ssh -i $WATCAL_DEPLOY_KEY -o IdentitiesOnly=yes"
fi

log "Syncing with origin/$BRANCH"
git fetch --quiet origin "$BRANCH"
git reset --hard --quiet "origin/$BRANCH"

# venv; reinstall only when pyproject.toml changes
if [ ! -d .venv ]; then
    log "Creating .venv"; "$PYTHON" -m venv .venv
fi
HASH_FILE=".venv/.pyproject.sha"
NEW_HASH="$(sha1sum pyproject.toml | cut -d' ' -f1)"
if [ "$(cat "$HASH_FILE" 2>/dev/null)" != "$NEW_HASH" ]; then
    log "Installing project"; .venv/bin/pip install -q -e . && echo "$NEW_HASH" > "$HASH_FILE"
fi

mkdir -p logs
find logs -name 'edziekanat_*.txt' -mtime +14 -delete 2>/dev/null || true
LOG="logs/edziekanat_$(date +'%Y-%m-%d_%H-%M').txt"

log "Scraping all WCY groups from the e-Dziekanat (delay ${DELAY}s)"
set +e
.venv/bin/watcal-me --all-groups --delay "$DELAY" --verbose --log-file "$LOG"
CODE=$?
set -e

log "Rebuilding index.json"
.venv/bin/watcal index || log "index rebuild failed"

git config user.name  "e-Dziekanat (pi)"
git config user.email "actions@github.com"
git add db/calendars/wcy_calendars db/calendars/index.json
if git diff --cached --quiet; then
    log "No calendar changes - nothing to commit."; exit "$CODE"
fi
git commit --quiet -m "e-Dziekanat: all WCY groups ($(date -u +'%Y-%m-%d'))"
for attempt in 1 2 3; do
    if git pull --rebase -X theirs --quiet origin "$BRANCH" && git push --quiet; then
        log "Pushed."; exit "$CODE"
    fi
    log "push attempt $attempt failed, retrying"; sleep 8
done
log "could not push"; exit 1
