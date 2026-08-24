#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
STATE_FILE=${HYPEROPS_LOGROTATE_STATE:-"$PROJECT_ROOT/data/logs/.logrotate.status"}
RENDERED_CONFIG=$(mktemp)

cleanup() {
    rm -f "$RENDERED_CONFIG"
}
trap cleanup EXIT INT TERM

mkdir -p "$(dirname -- "$STATE_FILE")"
sed "s|__HYPEROPS_ROOT__|$PROJECT_ROOT|g" \
    "$PROJECT_ROOT/docker/logrotate.conf" > "$RENDERED_CONFIG"

logrotate -s "$STATE_FILE" "$@" "$RENDERED_CONFIG"
