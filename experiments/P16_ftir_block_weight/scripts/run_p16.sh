#!/usr/bin/env bash
# P16 automation: sanity first, then full 10-seed run.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p experiments/P16_ftir_block_weight/{logs,results}

MODE="${1:-all}"

if [[ "$MODE" == "all" || "$MODE" == "sanity" ]]; then
  tooling/run.sh python3 experiments/P16_ftir_block_weight/scripts/p16_block_weight.py \
    --mode sanity --tag sanity > experiments/P16_ftir_block_weight/logs/p16_sanity.log 2>&1
fi

if [[ "$MODE" == "all" || "$MODE" == "full" ]]; then
  tooling/run.sh python3 experiments/P16_ftir_block_weight/scripts/p16_block_weight.py \
    --mode full --tag full > experiments/P16_ftir_block_weight/logs/p16_full.log 2>&1
fi

echo "P16 done: $MODE"
