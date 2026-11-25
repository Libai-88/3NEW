#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT:$ROOT/core:$ROOT/scripts:${PYTHONPATH:-}"
exec "$@"
