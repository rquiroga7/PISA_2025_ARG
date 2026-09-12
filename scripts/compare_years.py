#!/usr/bin/env python3
"""Compara años para Argentina aplicando el linking error de PISA.

SE(diferencia) = sqrt(SE_a^2 + SE_b^2 + link_error^2)

Uso:
    python scripts/compare_years.py
"""
from __future__ import annotations

import math
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def main() -> int:
    est = pd.read_csv(os.path.join(DATA, "pisa_arg_estimates.csv"))
    nat = est[(est.region == "Argentina") & (est.sector == "all")]
    links = pd.read_csv(os.path.join(DATA, "linking_errors.csv")) if \
        os.path.exists(os.path.join(DATA, "linking_errors.csv")) else pd.DataFrame()
    link_map = {(int(r.year1), int(r.year2), r.subject): float(r.link_error) for r in links.itertuples(index=False)}

    years = sorted(nat.year.unique())
    print("Diferencias entre años (Argentina total). '*' = significativa al 95%\n")
    print(f"{'par':>13} {'mat':>18} {'lec':>18} {'cie':>18}")
    for i in range(len(years) - 1):
        y1, y2 = int(years[i]), int(years[i + 1])
        cells = []
        for subj in ["math", "read", "scie"]:
            a = nat[(nat.year == y1) & (nat.subject == subj)].iloc[0]
            b = nat[(nat.year == y2) & (nat.subject == subj)].iloc[0]
            diff = b["mean"] - a["mean"]
            link = link_map.get((y1, y2, subj), link_map.get((y2, y1, subj), 0.0))
            se = math.sqrt(a["se"] ** 2 + b["se"] ** 2 + link ** 2)
            z = diff / se if se else 0
            sig = "*" if abs(z) > 1.96 else " "
            cells.append(f"{diff:+6.1f} (SE {se:4.1f}){sig}")
        print(f"{y1}->{y2:>4} " + " ".join(f"{c:>18}" for c in cells))
    print("\n(linking error solo disponible para 2018-2022; en el resto se usa 0 = cota inferior)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
