#!/usr/bin/env python3
"""Verifica que los promedios generales de Argentina calculados desde los
microdatos coincidan con los valores oficiales publicados por la OCDE.

Uso:
    python scripts/verify_national.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# Promedios oficiales PISA (Argentina), redondeados a entero. Fuente: bases y
# publicaciones OCDE (PISA 2006-2022). 2025 aun sin publicacion oficial.
OFFICIAL = {
    2006: {"math": 381, "read": 374, "scie": 391},
    2009: {"math": 388, "read": 398, "scie": 401},
    2012: {"math": 388, "read": 396, "scie": 406},
    2018: {"math": 379, "read": 402, "scie": 404},
    2022: {"math": 378, "read": 401, "scie": 406},
}
TOL = 1.0  # tolerancia por redondeo


def main() -> int:
    path = os.path.join(DATA, "pisa_arg_national.csv")
    if not os.path.exists(path):
        print("No existe data/pisa_arg_national.csv. Corre build_database.py --only-national.")
        return 1
    nat = pd.read_csv(path)
    ok = True
    print(f"{'año':>5} {'materia':<7} {'calculado':>10} {'oficial':>8} {'dif':>6}  estado")
    for year in sorted(nat["year"].unique()):
        for subj in ["math", "read", "scie"]:
            row = nat[(nat.year == year) & (nat.subject == subj)]
            if not len(row):
                continue
            calc = float(row["mean"].iloc[0])
            off = OFFICIAL.get(int(year), {}).get(subj)
            if off is None:
                print(f"{year:>5} {subj:<7} {calc:>10.2f} {'s/d':>8} {'':>6}  (sin oficial)")
                continue
            d = calc - off
            good = abs(d) <= TOL
            ok &= good
            print(f"{year:>5} {subj:<7} {calc:>10.2f} {off:>8} {d:>+6.2f}  {'OK' if good else 'DIF'}")
    print("\nRESULTADO:", "todos coinciden con la OCDE (tolerancia 1 pto)" if ok else "hay diferencias")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
