#!/usr/bin/env bash
#
# Local equivalent of .github/workflows/full_scrape.yml - same stages,
# same flags, same log file naming. Use it to reproduce a nightly run
# on your machine before trusting it in CI.
#
#   ./scripts/daily.sh                  # everything, into db/
#   ./scripts/daily.sh wcy wim          # selected faculties
#   SEMESTER=lato ./scripts/daily.sh    # force a semester
#   DRY=1 ./scripts/daily.sh            # write to a temp dir, leave db/ alone
#   SKIP_EMPLOYEES=1 ./scripts/daily.sh # skip the USOSweb stage
#
set -uo pipefail
cd "$(dirname "$0")/.."

if [ -x .venv/bin/watcal ]; then
    WATCAL=.venv/bin/watcal
elif command -v watcal >/dev/null 2>&1; then
    WATCAL=watcal
else
    echo "watcal not found - run: python3 -m venv .venv && .venv/bin/pip install -e . && .venv/bin/playwright install firefox chromium" >&2
    exit 1
fi

FACULTIES="${*:-all}"
# Plain string, not an array: macOS ships bash 3.2, where expanding an
# empty array under `set -u` is a fatal error.
SEMESTER_ARG=""
[ -n "${SEMESTER:-}" ] && SEMESTER_ARG="--semester $SEMESTER"

# Same retention policy as the workflow.
mkdir -p logs
find logs -name "*.txt" -type f -mtime +14 -delete 2>/dev/null

LOG_PATH="logs/scrape_$(date +'%Y-%m-%d_%H-%M').txt"

if [ -n "${DRY:-}" ]; then
    export WATCALENDARS_DB_DIR="${WATCALENDARS_DB_DIR:-$(mktemp -d)}"
    echo "DRY RUN -> output goes to $WATCALENDARS_DB_DIR (db/ untouched)"
fi

echo "Faculties: $FACULTIES"
echo "Log file : $LOG_PATH"
echo

failed=0

if [ -z "${SKIP_EMPLOYEES:-}" ]; then
    echo "=== [1/3] employees ==="
    # continue-on-error in the workflow: lecturer titles are a nice-to-have
    "$WATCAL" --verbose --log-file "$LOG_PATH" employees || \
        echo "employees stage failed - continuing (calendars still build)"
fi

echo "=== [2/3] groups ==="
"$WATCAL" --verbose --log-file "$LOG_PATH" $SEMESTER_ARG groups $FACULTIES || \
    echo "some faculties failed group discovery - continuing"

echo "=== [3/3] calendars ==="
"$WATCAL" --verbose --log-file "$LOG_PATH" $SEMESTER_ARG calendars $FACULTIES || failed=1

echo
echo "Log: $LOG_PATH"
[ -n "${DRY:-}" ] && echo "Output: $WATCALENDARS_DB_DIR"
exit $failed
