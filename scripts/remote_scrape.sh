#!/usr/bin/env bash
#
# Scrape faculties that Imperva/Incapsula blocks from GitHub Actions, from
# a machine it does not block (the Raspberry Pi on a home connection),
# and push the calendars to GitHub. Meant for cron; see README, section
# "Scraping z Raspberry Pi (WCY)".
#
#   scripts/remote_scrape.sh            # WCY
#   scripts/remote_scrape.sh wcy wim    # selected faculties
#
# Environment:
#   WATCAL_REPO          clone to work in (default: this script's repo)
#   WATCAL_DEPLOY_KEY    SSH key to push with (GitHub deploy key, write access)
#   WATCAL_REMOTE_NAME   machine name in the commit message (default: pi-cloud)
#   WATCAL_BRANCH        branch to sync and push (default: main)
#   WATCAL_PYTHON        interpreter for the venv (default: python3)
#
# WARNING: run this in a clone DEDICATED to it (e.g. ~/watcal-remote), never
# in a working copy you edit. Every run starts with
# `git reset --hard origin/main`, which throws away local changes: that is
# what keeps it free of conflicts with the commits the Actions bot pushes
# every night. Shallow (--depth 1) clones are fine and recommended - the
# full history is over 10 GB.
#
# Exit code: that of `watcal calendars`, so cron mail / monitoring sees
# a blocked or failed faculty. Git failures exit non-zero on their own.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${WATCAL_REPO:-$SCRIPT_DIR/..}"

BRANCH="${WATCAL_BRANCH:-main}"
MACHINE="${WATCAL_REMOTE_NAME:-pi-cloud}"
PYTHON="${WATCAL_PYTHON:-python3}"

if [ "$#" -eq 0 ]; then
    set -- wcy
fi
FACULTIES=()
for code in "$@"; do
    code="$(echo "$code" | tr '[:upper:]' '[:lower:]')"
    if ! [[ "$code" =~ ^[a-z]+$ ]]; then
        echo "Invalid faculty code: '$code'" >&2
        exit 2
    fi
    FACULTIES+=("$code")
done

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if [ -n "${WATCAL_DEPLOY_KEY:-}" ]; then
    export GIT_SSH_COMMAND="ssh -i $WATCAL_DEPLOY_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
fi

# One run at a time: a slow scrape must not overlap the next cron slot.
# The lock lives in .git so it survives `reset --hard` and is never added.
exec 9>"$(git rev-parse --git-dir)/watcal-remote.lock"
if ! flock -n 9; then
    log "Another remote_scrape.sh is still running here - skipping this run."
    exit 0
fi

# --- 1. Sync to origin --------------------------------------------------
log "Syncing with origin/$BRANCH"
git fetch --quiet --depth 1 origin "$BRANCH"
git reset --quiet --hard "origin/$BRANCH"
# Leftovers of an interrupted run must not sneak into the next commit.
git clean -fdq -- db/calendars
# Each depth-1 fetch leaves the previous commit unreachable; let gc drop
# those instead of keeping them for the default 90 days.
git config gc.reflogExpire now
git config gc.reflogExpireUnreachable now
git gc --auto --quiet

# --- 2. Virtualenv ------------------------------------------------------
# Only plain `pip install -e .`: the faculties scraped here use the HTTP
# strategy, which never imports Playwright, so no `playwright install`.
if [ ! -x .venv/bin/python ]; then
    log "Creating .venv"
    "$PYTHON" -m venv .venv
fi
pyproject_hash="$(sha256sum pyproject.toml | cut -d' ' -f1)"
stamp=.venv/.pyproject.sha256
if [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$pyproject_hash" ]; then
    log "pyproject.toml changed - reinstalling"
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -e .
    echo "$pyproject_hash" > "$stamp"
fi
WATCAL=.venv/bin/watcal

# --- 3. Probe -----------------------------------------------------------
# One request for one group before the ~185 real ones. If Incapsula still
# bans this address, every further request only prolongs the ban, so a
# 403 here means: do nothing today. The probe uses the scraper's own
# headers (Firefox UA, pl-PL) and follows Incapsula's cookie redirect.
probe_url() {
    .venv/bin/python - "$1" <<'PY'
import sys
from watcalendars.core import registry
from watcalendars.core.pipeline import build_pairs, semester_for
from watcalendars.store import groups

spec = registry.get(sys.argv[1])
try:
    pairs = build_pairs(spec, groups.load_groups(spec.code, semester_for(spec)))
except Exception:
    pairs = []
print(pairs[0][1] if pairs else "")
PY
}

curl_headers=()
while IFS= read -r header; do
    curl_headers+=(-H "$header")
done < <(.venv/bin/python -c \
    "from watcalendars.fetch.http import HEADERS; print('\n'.join(f'{k}: {v}' for k, v in HEADERS.items()))" \
    | tr -d '\r')

jar="$(mktemp)"
trap 'rm -f "$jar"' EXIT
reachable=()
broken=0
for code in "${FACULTIES[@]}"; do
    url="$(probe_url "$code")"
    if [ -z "$url" ]; then
        log "No group map for $code - cannot probe, scraping anyway"
        reachable+=("$code")
        continue
    fi
    http_code="$(curl -s -L --max-time 30 -c "$jar" -b "$jar" "${curl_headers[@]}" \
        -o /dev/null -w '%{http_code}' "$url" || true)"
    case "$http_code" in
        200)
            log "Probe $code: HTTP 200"
            reachable+=("$code")
            ;;
        403)
            log "IP still blocked by WAF, skipping $code (probe: HTTP 403 on $url)"
            ;;
        *)
            # 400/5xx/000 (no network): not a ban, but no reason to fire
            # the real requests either. Non-zero exit so cron reports it.
            log "Probe $code: HTTP $http_code on $url - not scraping $code today"
            broken=1
            ;;
    esac
done

if [ "${#reachable[@]}" -eq 0 ]; then
    if [ "$broken" -eq 1 ]; then
        exit 1
    fi
    log "IP still blocked by WAF, skipping"
    exit 0
fi
FACULTIES=("${reachable[@]}")
# Do not follow the probe with the first real request back to back.
sleep 5

# --- 4. Scrape ----------------------------------------------------------
mkdir -p logs
find logs -name "remote_*.txt" -type f -mtime +14 -delete 2>/dev/null || true
LOG_PATH="logs/remote_$(date +'%Y-%m-%d_%H-%M').txt"

log "Scraping: ${FACULTIES[*]} (log: $LOG_PATH)"
status=0
# Shown on the website next to each faculty's status dot.
WATCAL_SOURCE="$MACHINE" "$WATCAL" --verbose --log-file "$LOG_PATH" calendars "${FACULTIES[@]}" || status=$?
log "watcal calendars exited with $status"

"$WATCAL" --log-file "$LOG_PATH" index || log "watcal index failed - committing the calendars anyway"

# status.json belongs to the GitHub workflow; the CLI rewrote it locally.
git checkout -- db/calendars/status.json 2>/dev/null || true

# --- 5. Commit ----------------------------------------------------------
paths=()
for code in "${FACULTIES[@]}"; do
    if [ -d "db/calendars/${code}_calendars" ]; then
        paths+=("db/calendars/${code}_calendars")
    fi
done

if [ "${#paths[@]}" -eq 0 ]; then
    log "No calendar directories produced - nothing to commit."
    exit "$status"
fi

git add -A -- "${paths[@]}"
# Each faculty directory holds its status.json (last scrape time), so a
# successful run always has something to commit - that is what keeps the
# faculty's dot green on the website even when no plan changed.
if git diff --cached --quiet; then
    log "Calendars unchanged - nothing to commit."
    git reset --quiet --hard HEAD
    exit "$status"
fi
git add -- db/calendars/index.json

label="$(echo "${FACULTIES[*]}" | tr '[:lower:]' '[:upper:]' | sed 's/ /, /g')"
identity=()
if [ -z "$(git config user.email || true)" ]; then
    identity=(-c "user.name=WATcalendars ($MACHINE)" -c "user.email=actions@github.com")
fi
git "${identity[@]}" commit --quiet -m "Remote scrape: $label ($MACHINE)"
log "Committed: $(git log -1 --format='%h %s')"
# Drop everything not committed (status.json, stray files) so the rebase
# below starts from a clean tree.
git reset --quiet --hard HEAD

# --- 6. Push ------------------------------------------------------------
# Plain fetch, not --depth 1: in a shallow clone it fetches just the new
# commits down to our base, so the rebase still finds the merge base.
# (A --depth 1 fetch would cut that link and the rebase would try to
# replay the whole tree.) -X theirs: in a rebase "theirs" is our commit
# being replayed, so our calendars win any conflict. index.json is then
# rebuilt from the merged tree rather than trusting either side's copy.
pushed=0
for attempt in 1 2 3; do
    if git fetch --quiet origin "$BRANCH" \
        && git "${identity[@]}" rebase --quiet -X theirs "origin/$BRANCH"; then
        if "$WATCAL" --log-file "$LOG_PATH" index; then
            git add -- db/calendars/index.json
            git diff --cached --quiet || git "${identity[@]}" commit --quiet --amend --no-edit
        fi
        git checkout -- db/calendars/status.json 2>/dev/null || true
        if git push --quiet origin "HEAD:$BRANCH"; then
            pushed=1
            break
        fi
    else
        git rebase --abort 2>/dev/null || true
    fi
    log "Push attempt $attempt failed"
    sleep $((attempt * 20))
done

if [ "$pushed" -ne 1 ]; then
    log "ERROR: could not push after 3 attempts"
    exit 1
fi
log "Pushed $(git log -1 --format='%h') to $BRANCH"
exit "$status"
