#!/usr/bin/env python3
"""Calcula estimaciones de Argentina con el diseno muestral complejo de PISA:

  - Errores estandar por replicacion BRR/Fay (80 replicas, factor de Fay 0.5).
  - Combinacion de los valores plausibles con las reglas de Rubin.
  - Medias por anio, por region y por gestion.

Salida: data/pisa_arg_estimates.csv
    year, region, sector, subject, mean, se, n
donde region = "Argentina" para el total nacional.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_database as bd  # noqa: E402
import pisa_io as io  # noqa: E402

FAY = 0.5
ROOT = bd.ROOT
DATA = bd.DATA
REGIONS = ["CABA", "Buenos Aires", "Córdoba", "Santa Fe", "Mendoza", "NOA", "NEA", "Cuyo", "Patagonia"]


def rep_names(year: int, cols: set[str]) -> list[str]:
    if year >= 2015:
        cand = [f"W_FSTURWT{i}" for i in range(1, 81)]
    else:
        cand = [f"W_FSTR{i}" for i in range(1, 81)]
    got = [c for c in cand if c in cols]
    if got:
        return got
    # busqueda tolerante
    return sorted([c for c in cols if c.upper().startswith("W_FST") and c.upper() != "W_FSTUWT"],
                  key=lambda s: int("".join(ch for ch in s if ch.isdigit()) or 0))


def load_cycle(year: int) -> pd.DataFrame | None:
    pvs = io.pv_names(year, "MATH") + io.pv_names(year, "READ") + io.pv_names(year, "SCIE")
    if year in bd.OLD_CYCLES:
        cfg = bd.OLD_CYCLES[year]
        txt, sps = bd._abs(cfg["stu"][0]), bd._abs(cfg["stu"][1])
        if not (os.path.exists(txt) and os.path.exists(sps)):
            return None
        allspec = {s[0].upper() for s in io.parse_sps_spec(sps)}
        reps = rep_names(year, allspec)
        cols = ["CNT", "SCHOOLID", "W_FSTUWT"] + reps + pvs
        df = io.read_txt(sps, txt, usecols=cols, filter_cnt="ARG")
        df = df.rename(columns={"SCHOOLID": "CNTSCHID"})
    else:
        bd.ensure_extracted(year)
        path = bd.find_sav(year, "stu")
        if not path:
            return None
        allspec = set(io.sav_columns(path))
        reps = rep_names(year, allspec)
        cols = [c for c in (["CNT", "CNTSCHID", "W_FSTUWT"] + reps + pvs) if c in allspec]
        df = io.read_sav(path, usecols=cols)
        df = df[df["CNT"].astype(str).str.strip() == "ARG"].copy()
    if not len(df):
        return None
    df["CNTSCHID"] = bd.norm_id(df["CNTSCHID"])
    io.add_subject_means(df, year)
    return df, reps


def brr_rubin(sub: pd.DataFrame, reps: list[str], pvcols: list[str]) -> tuple[float, float, int]:
    w = pd.to_numeric(sub["W_FSTUWT"], errors="coerce").to_numpy(float)
    W = sub[reps].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    X = sub[pvcols].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    ok = ~np.isnan(w) & (w > 0)
    w, W, X = w[ok], W[ok], X[ok]
    M = X.shape[1]
    if w.sum() == 0 or len(w) < 2:
        return float("nan"), float("nan"), int(ok.sum())
    theta = (w @ X) / w.sum()
    colsum = W.sum(axis=0)
    rep = (W.T @ X) / colsum[:, None]
    var_pv = np.nansum((rep - np.nanmean(rep, axis=0)) ** 2, axis=0) / (len(reps) * (1 - FAY) ** 2)
    theta_bar = np.nanmean(theta)
    Wbar = np.nanmean(var_pv)
    B = np.nansum((theta - theta_bar) ** 2) / (M - 1)
    T = Wbar + (1 + 1 / M) * B
    return float(theta_bar), float(np.sqrt(max(T, 0))), int(ok.sum())


def main() -> int:
    school_map = {}
    sp = os.path.join(DATA, "pisa_arg_schools.csv")
    if os.path.exists(sp):
        sm = pd.read_csv(sp)
        for r in sm.itertuples(index=False):
            regs = [] if not isinstance(r.region, str) else r.region.split("|")
            school_map[(int(r.year), str(r.school_id))] = (regs, r.sector)

    rows = []
    for year in [2025, 2022, 2018, 2012, 2009, 2006]:
        loaded = load_cycle(year)
        if not loaded:
            print(f"  {year}: sin datos")
            continue
        df, reps = loaded
        print(f"== {year}: {len(df)} estudiantes, {len(reps)} replicas ==")
        maps = df["CNTSCHID"].map(lambda s: school_map.get((year, s), ([], "NR")))
        df["regs"] = [m[0] for m in maps]
        df["sec"] = [m[1] for m in maps]

        def record(label_reg, label_sec, sub):
            for subj in ["MATH", "READ", "SCIE"]:
                pvc = [c for c in io.pv_names(year, subj) if c in sub.columns]
                if not pvc or not len(sub):
                    continue
                m, se, n = brr_rubin(sub, reps, pvc)
                rows.append({"year": year, "region": label_reg, "sector": label_sec,
                             "subject": subj.lower(), "mean": round(m, 3),
                             "se": round(se, 3), "n": n})

        record("Argentina", "all", df)
        for sec in ["Pública", "Privada"]:
            ds = df[df["sec"] == sec]
            if len(ds):
                record("Argentina", sec, ds)
        for reg in REGIONS:
            d = df[df["regs"].map(lambda rs: reg in rs)]
            if len(d):
                record(reg, "all", d)
                for sec in ["Pública", "Privada"]:
                    ds = d[d["sec"] == sec]
                    if len(ds):
                        record(reg, sec, ds)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DATA, "pisa_arg_estimates.csv"), index=False)
    print(f"OK {len(out)} filas -> data/pisa_arg_estimates.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
