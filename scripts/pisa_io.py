#!/usr/bin/env python3
"""Lectores y utilidades para microdatos PISA.

Soporta:
  - SPSS .sav (ciclos 2015-2025) via pyreadstat.
  - TXT de ancho fijo (ciclos 2000-2012) usando los archivos de control SPSS.

Tambien incluye la lista de paises OCDE por ciclo y el envejecimiento de
nombres de variables entre ciclos.
"""
from __future__ import annotations

import os
import re
import zipfile

import numpy as np
import pandas as pd

# --- Paises OCDE por ciclo (miembros al momento del ciclo). -----------------
_OCDE_BASE = ["AUT", "AUS", "BEL", "CAN", "CZE", "DNK", "FIN", "FRA", "DEU",
              "GRC", "HUN", "ISL", "IRL", "ITA", "JPN", "KOR", "LUX", "MEX",
              "NLD", "NZL", "NOR", "POL", "PRT", "ESP", "SWE", "CHE", "TUR",
              "GBR", "USA"]
_OCDE_ADD = [
    (2000, ["SVK"]),
    (2010, ["CHL", "SVN", "ISR", "EST"]),
    (2016, ["LVA"]),
    (2018, ["LTU"]),
    (2020, ["COL"]),
    (2021, ["CRI"]),
]


def oecd_countries(year: int) -> list[str]:
    out = list(_OCDE_BASE)
    for y, add in _OCDE_ADD:
        if year >= y:
            out += add
    return sorted(set(out))


# --- Variables por ciclo. ----------------------------------------------------
# Cantidad de valores plausibles por area.
def n_pv(year: int) -> int:
    return 5 if year <= 2012 else 10


def pv_names(year: int, subject: str) -> list[str]:
    """Nombres de los valores plausibles. subject in {MATH, READ, SCIE}."""
    return [f"PV{i}{subject}" for i in range(1, n_pv(year) + 1)]


# --- .sav --------------------------------------------------------------------
def read_sav(path: str, usecols: list[str] | None = None) -> pd.DataFrame:
    import pyreadstat
    df, _ = pyreadstat.read_sav(path, usecols=usecols)
    return df


def sav_columns(path: str) -> list[str]:
    import pyreadstat
    _, meta = pyreadstat.read_sav(path, metadataonly=True)
    return list(meta.column_names)


# --- TXT de ancho fijo -------------------------------------------------------
_SPS_SPEC = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s+(\d+)\s*-\s*(\d+)(?:\s*\(([A-Za-z])[^)]*\))?", re.I)


def parse_sps_spec(sps_path: str) -> list[tuple[str, int, int, str]]:
    """Devuelve [(nombre, inicio, fin, tipo)] a partir de un DATA LIST SPSS."""
    specs: list[tuple[str, int, int, str]] = []
    with open(sps_path, encoding="latin-1") as fh:
        for line in fh:
            m = _SPS_SPEC.match(line.strip())
            if m:
                name, a, b = m.group(1), int(m.group(2)), int(m.group(3))
                t = (m.group(4) or "F").upper()
                specs.append((name, a, b, t))
    return specs


def read_txt(sps_path: str, txt_path: str, usecols: list[str] | None = None,
             filter_cnt: str | None = None, chunksize: int = 200000) -> pd.DataFrame:
    """Lee un TXT de ancho fijo usando las posiciones del control SPSS.

    Los indices del control son 1-based e inclusivos. Si filter_cnt se indica,
    conserva solo las filas cuyo CNT coincida (para archivos de todos los paises).
    """
    specs = parse_sps_spec(sps_path)
    if usecols:
        want = {c.upper() for c in usecols}
        specs = [s for s in specs if s[0].upper() in want]
    specs = sorted(specs, key=lambda s: s[1])
    colspecs = [(s[1] - 1, s[2]) for s in specs]
    names = [s[0] for s in specs]
    str_cols = {s[0] for s in specs if s[3] == "A"}
    parts = []
    for chunk in pd.read_fwf(txt_path, colspecs=colspecs, names=names, dtype=object,
                             encoding="latin-1", header=None, chunksize=chunksize):
        if filter_cnt and "CNT" in chunk.columns:
            chunk = chunk[chunk["CNT"].astype(str).str.strip() == filter_cnt]
        if not len(chunk):
            continue
        for c in chunk.columns:
            if c in str_cols:
                chunk[c] = chunk[c].astype(str).str.strip()
            else:
                chunk[c] = pd.to_numeric(chunk[c], errors="coerce")
        parts.append(chunk)
    if not parts:
        return pd.DataFrame(columns=names)
    return pd.concat(parts, ignore_index=True)


def clean_missing(df: pd.DataFrame, cols: list[str], threshold: float = 9990.0) -> pd.DataFrame:
    """En los TXT de PISA los faltantes se codifican como 9999/9998/etc.
    Reemplaza esos centinelas por NaN en las columnas indicadas."""
    for c in cols:
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce")
            df[c] = v.mask(v.abs() >= threshold)
    return df


def unzip(zip_path: str, dest_dir: str) -> list[str]:
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
        return zf.namelist()


# --- Agregacion a nivel escuela ---------------------------------------------
def add_subject_means(df: pd.DataFrame, year: int) -> pd.DataFrame:
    for subj in ["MATH", "READ", "SCIE"]:
        cols = [c for c in pv_names(year, subj) if c in df.columns]
        if cols:
            df[subj.lower() + "_m"] = df[cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    return df


def _wm(g: pd.DataFrame, col: str, wcol: str) -> float:
    v = pd.to_numeric(g[col], errors="coerce").to_numpy(dtype=float)
    w = pd.to_numeric(g[wcol], errors="coerce").to_numpy(dtype=float)
    m = ~np.isnan(v) & ~np.isnan(w)
    if not m.any() or w[m].sum() == 0:
        return float("nan")
    return float(np.average(v[m], weights=w[m]))


def _sd(g: pd.DataFrame, col: str) -> float:
    """Desvio estandar muestral (ddof=1) de una columna, entre estudiantes de la escuela."""
    if col not in g.columns:
        return float("nan")
    v = pd.to_numeric(g[col], errors="coerce").to_numpy(dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return float("nan")
    return float(np.std(v, ddof=1))


def aggregate_schools(stu: pd.DataFrame, year: int, id_col: str = "CNTSCHID",
                      w_col: str = "W_FSTUWT", escs_col: str = "ESCS") -> pd.DataFrame:
    """Agrega estudiantes a nivel escuela (promedios ponderados por W_FSTUWT).

    Incluye el desvio estandar intraescuela (no ponderado) de cada area y de ESCS,
    para poder mostrar la dispersion de la muestra de cada escuela.
    """
    rows = []
    for sid, g in stu.groupby(id_col, sort=False):
        ge = g[g[escs_col].notna()] if escs_col in g.columns else g.iloc[0:0]
        rec = {
            "school_id": str(sid),
            "n_stu": int(len(g)),
            "n_escs": int(len(ge)),
            "w_sum": float(pd.to_numeric(g[w_col], errors="coerce").sum()),
            "escs": _wm(ge, escs_col, w_col) if len(ge) else float("nan"),
            "sd_escs": _sd(ge, escs_col) if len(ge) else float("nan"),
        }
        for subj in ["math", "read", "scie"]:
            col = subj + "_m"
            rec[subj] = _wm(g, col, w_col) if col in g.columns else float("nan")
            rec["sd_" + subj] = _sd(g, col)
        rows.append(rec)
    return pd.DataFrame(rows)
