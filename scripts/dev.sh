#!/usr/bin/env bash
# Dev runner: everything executes inside Docker, nothing is installed on the host.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=prebounce-dev

build() {
  docker build -q -f Dockerfile.dev -t "$IMAGE" . >/dev/null
}

run() {
  docker run --rm --network none -v "$PWD":/app -w /app -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" "$@"
}

cmd_test() { run python -m pytest -p no:cacheprovider "$@"; }
cmd_lint() { run ruff check . && run ruff format --check .; }
cmd_types() { run mypy --strict src; }

sub="${1:-all}"
[ $# -gt 0 ] && shift
build
case "$sub" in
  test) cmd_test "$@" ;;
  lint) cmd_lint ;;
  types) cmd_types ;;
  all) cmd_lint && cmd_types && cmd_test ;;
  *) echo "usage: scripts/dev.sh {test [pytest args]|lint|types|all}" >&2; exit 2 ;;
esac
