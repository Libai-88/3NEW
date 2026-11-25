#!/usr/bin/env bash
# P15 automation: sanity first, then full.  Results are not overwritten because
# sanity and full use different --tag values.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p experiments/P15_feature_robustness/logs experiments/P15_feature_robustness/results

MODE="${1:-all}"

if [[ "$MODE" == "all" || "$MODE" == "sanity" ]]; then
  tooling/run.sh python3 experiments/P15_feature_robustness/scripts/p15a_residual_pilot.py \
    --mode sanity --tag sanity > experiments/P15_feature_robustness/logs/p15a_sanity.log 2>&1
  tooling/run.sh python3 experiments/P15_feature_robustness/scripts/p15b_nested_selection.py \
    --mode sanity --tag sanity > experiments/P15_feature_robustness/logs/p15b_sanity.log 2>&1
fi

if [[ "$MODE" == "all" || "$MODE" == "full" ]]; then
  tooling/run.sh python3 experiments/P15_feature_robustness/scripts/p15b_nested_selection.py \
    --mode full --tag full > experiments/P15_feature_robustness/logs/p15b_full.log 2>&1
fi

echo "P15 done: $MODE"
