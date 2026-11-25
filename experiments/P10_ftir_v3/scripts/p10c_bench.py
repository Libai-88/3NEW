# -*- coding: utf-8 -*-
"""P10 compatibility helpers required by the P14 evidence-chain scripts.

This is intentionally a small P14-support subset, not the full P10 benchmark.
The full P10 script remains in the local workspace."""
from __future__ import annotations

import numpy as np

FTIR_RAW8 = [
    "ftir_oh_phen",
    "ftir_oh_epox",
    "ftir_meoh_phen",
    "ftir_aroc_phen",
    "ftir_coc_all",
    "ftir_arsub_all",
    "ftir_ch_all",
    "ftir_co_all",
]


def subset_target(target: dict, ids: list) -> dict:
    keep = [s for s in target["ids"] if s in set(ids)]
    idx = [target["ids"].index(s) for s in keep]
    return {
        "ids": keep,
        "raw": np.asarray(target["raw"])[idx],
        "groups": np.asarray(target["groups"])[idx],
        "schemas": target["schemas"],
        "transform": target["transform"],
        "inverse": target["inverse"],
        "not_run": target.get("not_run", {}),
    }
