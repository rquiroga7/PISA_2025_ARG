#!/usr/bin/env python3
"""Inspecciona los estratos (STRATUM) de Argentina por ciclo para curar
region_mapping.json.

Uso:
    python scripts/inspect_strata.py 2015 2018 2022
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_database as bd  # noqa: E402
import pisa_io as io  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cycles", nargs="*", type=int, default=[2015, 2018, 2022, 2025])
    args = ap.parse_args()

    for year in args.cycles:
        print("=" * 70)
        print(f"CICLO {year}")
        bd.ensure_extracted(year)
        sch = bd.find_sav(year, "sch")
        if not sch:
            print("  sin archivo de escuela")
            continue
        import pyreadstat
        _, meta = pyreadstat.read_sav(sch, metadataonly=True)
        cols = list(meta.column_names)
        if "CNT" not in cols:
            print("  sin CNT")
            continue
        use = [c for c in ["CNT", "CNTSCHID", "STRATUM", "SUBNATIO", "SC013Q01TA"] if c in cols]
        df = io.read_sav(sch, usecols=use)
        df["CNT"] = df["CNT"].astype(str).str.strip()
        arg = df[df["CNT"] == "ARG"]
        print(f"  archivo: {os.path.basename(sch)}  escuelas ARG: {len(arg)}")
        print(f"  STRATUM unicos: {sorted(arg['STRATUM'].astype(str).unique())}")
        labels = {}
        for v in ("STRATUM", "SUBNATIO"):
            lv = meta.variable_value_labels.get(v, {})
            labels[v] = lv
        for v in ("STRATUM", "SUBNATIO"):
            lv = labels.get(v, {})
            if lv:
                print(f"  etiquetas {v}:")
                for k in sorted(lv, key=lambda z: str(z)):
                    if str(k) in set(arg[v].astype(str).unique()):
                        print(f"    {k}: {lv[k]}")
        if "SC013Q01TA" in arg.columns:
            print("  SC013Q01TA (gestion):")
            print(arg["SC013Q01TA"].value_counts(dropna=False).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
