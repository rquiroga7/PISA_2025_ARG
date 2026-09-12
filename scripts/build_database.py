#!/usr/bin/env python3
"""Construye la base compacta de PISA Argentina a partir de los microdatos crudos.

Salidas (en data/):
  - pisa_arg_schools.csv : 1 fila por escuela-ciclo
  - pisa_arg_trends.csv  : parametros de tendencia (ARG y OCDE) por ciclo/materia
  - pisa_arg_meta.json   : metadatos, banderas y notas

Uso:
    python scripts/build_database.py                  # todos los ciclos con datos crudos
    python scripts/build_database.py --cycles 2025
    python scripts/build_database.py --no-oecd        # omitir tendencia OCDE
    python scripts/build_database.py --keep-raw
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import shutil
import sys
import time
import zipfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pisa_io as io  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
EXTRACT = os.path.join(RAW, "extracted")
DATA = os.path.join(ROOT, "data")

# Archivos de estudiante/escuela que aparecen en los .zip descargados.
STU_HINTS = ["STU_QQQ", "CY09_MS_STU", "CY08_MS_STU", "CY07_MS_STU", "CY06_MS_STU"]
SCH_HINTS = ["SCH_QQQ", "CY09_MS_SCH", "CY08_MS_SCH", "CY07_MS_SCH", "CY06_MS_SCH"]

# Zips por ciclo (nombre en raw/) para extraer.
CYCLE_ZIPS = {
    2025: ["CY09_MS_STU_PUF.zip", "CY09_MS_SCH_PUF.zip"],
    2022: ["STU_QQQ_SPSS.zip", "SCH_QQQ_SPSS.zip"],
    2018: ["SPSS_STU_QQQ.zip", "SPSS_SCH_QQQ.zip"],
    2015: ["PUF_SPSS_COMBINED_CMB_STU_QQQ.zip", "PUF_SPSS_COMBINED_CMB_SCH_QQQ.zip",
           "PUF_SPSS_COMBINED_CM2_STU_QQQ_COG_QTM_SCH_TCH.zip"],
    2012: ["INT_STU12_DEC03.zip", "INT_SCQ12_DEC03.zip"],
    2009: ["INT_STQ09_DEC11.zip", "INT_SCQ09_Dec11.zip"],
    2006: ["INT_Stu06_Dec07.zip", "INT_Sch06_Dec07.zip"],
    2000: ["intstud_read.zip", "intstud_math.zip", "intstud_scie.zip", "intscho.zip", "PISA2000_ESCS.zip"],
}

# Ciclos con problemas conocidos (se documentan en meta).
FLAGS = {
    2000: ["Datos de 2000 en archivos separados por área; ESCS en archivo aparte."],
    2015: ["Muestra argentina con problemas técnicos; datos en archivo adicional de la OCDE."],
    2022: ["Prueba en computadora (los ciclos previos fueron en papel)."],
    2025: ["Prueba en computadora."],
}

# Resultados región-año excluidos por ser atípicos/no comparables.
# Cuyo 2009 (≈413) se aparta fuertemente del resto de Cuyo (≈354-383) y de NEA/NOA.
EXCLUDE_REGION_YEARS = {(2009, "Cuyo")}


def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_extracted(year: int) -> None:
    dest = os.path.join(EXTRACT, str(year))
    os.makedirs(dest, exist_ok=True)
    for name in CYCLE_ZIPS.get(year, []):
        zp = os.path.join(RAW, name)
        if os.path.exists(zp):
            marker = os.path.join(dest, "." + name + ".done")
            if not os.path.exists(marker):
                log(f"  extrayendo {name} ...")
                with zipfile.ZipFile(zp) as zf:
                    zf.extractall(dest)
                open(marker, "w").close()


# Nombres exactos preferidos por (ciclo, tipo). En 2015 el archivo adicional CM2
# contiene la muestra argentina; el CMB contiene todos los paises.
PREFERRED = {
    (2015, "stu"): ["CY6_MS_CM2_STU_QQQ.sav", "CY6_MS_CMB_STU_QQQ.sav"],
    (2015, "sch"): ["CY6_MS_CM2_SCH_QQQ.sav", "CY6_MS_CMB_SCH_QQQ.sav"],
}


def find_sav(year: int, kind: str) -> str | None:
    """Busca el .sav de estudiantes/escuela del ciclo, en raw/extracted o raiz."""
    hints = STU_HINTS if kind == "stu" else SCH_HINTS
    candidates: list[str] = []
    # Solo el directorio extraido del ciclo + la raiz (no recursivo), para no
    # tomar archivos de otros ciclos.
    year_dir = os.path.join(EXTRACT, str(year))
    if os.path.isdir(year_dir):
        candidates += glob.glob(os.path.join(year_dir, "**", "*.sav"), recursive=True)
    for base in (ROOT, RAW):
        if os.path.isdir(base):
            candidates += glob.glob(os.path.join(base, "*.sav"))
    by_name = {os.path.basename(c).upper(): c for c in candidates}
    for want in PREFERRED.get((year, kind), []):
        if want.upper() in by_name:
            return by_name[want.upper()]
    lower = [(c, os.path.basename(c).upper()) for c in candidates]
    for hint in hints:
        for c, b in lower:
            if hint.upper() in b:
                return c
    # 2025 local con nombres CY09 en raiz
    for c, b in lower:
        if kind == "stu" and "STU" in b:
            return c
        if kind == "sch" and "SCH" in b:
            return c
    return None


def load_school_frame(year: int) -> pd.DataFrame | None:
    sch_path = find_sav(year, "sch")
    if not sch_path:
        return None
    cols = io.sav_columns(sch_path)
    keep = [c for c in ["CNT", "CNTSCHID", "STRATUM", "SUBNATIO", "SC013Q01TA"] if c in cols]
    df = io.read_sav(sch_path, usecols=keep)
    if "CNT" in df.columns:
        df = df[df["CNT"].astype(str).str.strip() == "ARG"].copy()
    return df


def load_arg_students(year: int) -> pd.DataFrame | None:
    # Atajo: extracto ARG ya generado para 2025.
    local = os.path.join(ROOT, f"ARG_STU_{year}.csv.gz")
    if os.path.exists(local):
        log(f"  usando extracto local {os.path.basename(local)}")
        with gzip.open(local, "rt") as fh:
            return pd.read_csv(fh)
    stu_path = find_sav(year, "stu")
    if not stu_path:
        return None
    cols = io.sav_columns(stu_path)
    keep = [c for c in (["CNT", "CNTSCHID", "W_FSTUWT", "ESCS", "GRADE"]
                        + io.pv_names(year, "MATH") + io.pv_names(year, "READ") + io.pv_names(year, "SCIE"))
            if c in cols]
    df = io.read_sav(stu_path, usecols=keep)
    if "CNT" in df.columns:
        df = df[df["CNT"].astype(str).str.strip() == "ARG"].copy()
    return df


def norm_id(series: pd.Series) -> pd.Series:
    """Normaliza IDs de escuela a string sin ceros a la izquierda."""
    num = pd.to_numeric(series, errors="coerce")
    out = num.astype("Int64").astype(str)
    return out.where(num.notna(), series.astype(str).str.strip())


def modal_school_ids(df: pd.DataFrame):
    """IDs de escuelas con estudiantes en el grado modal (Fig. 5 OCDE).
    Usa GRADE (0 = modal) o, si no existe, el grado modal de ST01Q01."""
    if "GRADE" in df.columns:
        col, val = "GRADE", 0
    elif "ST01Q01" in df.columns:
        col = "ST01Q01"
        m = df[col].mode()
        if not len(m):
            return None
        val = m.iloc[0]
    else:
        return None
    return set(norm_id(df.loc[df[col] == val, "CNTSCHID"]))


def assign_region_sector(frame: pd.DataFrame, year: int, mapping: dict) -> pd.DataFrame:
    cfg = mapping.get(str(year), {})
    strata_map = cfg.get("strata", {})
    rule = cfg.get("sector_rule")
    frame = frame.copy()
    frame["STRATUM"] = frame.get("STRATUM", pd.Series(dtype=str)).astype(str).str.strip()

    def _map_region(v):
        return "|".join(v) if isinstance(v, list) else v

    frame["region"] = frame["STRATUM"].map(strata_map).map(_map_region)

    if "SC013Q01TA" in frame.columns:
        s = pd.to_numeric(frame["SC013Q01TA"], errors="coerce")
        frame["sector"] = np.where(s == 1, "Pública", np.where(s == 2, "Privada", None))
    else:
        frame["sector"] = None

    if rule == "odd_public":
        idx = pd.to_numeric(frame["STRATUM"].str.extract(r"(\d+)$")[0], errors="coerce")
        fallback = np.where(idx % 2 == 1, "Pública", "Privada")
        frame["sector"] = frame["sector"].fillna(pd.Series(fallback, index=frame.index))
    frame["sector"] = frame["sector"].fillna("NR")
    return frame


def wols(x: np.ndarray, y: np.ndarray, w: np.ndarray):
    sw = w.sum()
    if sw <= 0 or len(x) < 2:
        return None
    mx = (w * x).sum() / sw
    my = (w * y).sum() / sw
    sxx = (w * (x - mx) ** 2).sum()
    sxy = (w * (x - mx) * (y - my)).sum()
    syy = (w * (y - my) ** 2).sum()
    if sxx == 0:
        return None
    b = sxy / sxx
    a = my - b * mx
    r = sxy / np.sqrt(sxx * syy) if syy > 0 else 0.0
    return dict(slope=float(b), intercept=float(a), r=float(r))


def trend_from_schools(df: pd.DataFrame) -> list[dict]:
    d = df.dropna(subset=["escs"]).copy()
    if len(d) < 2:
        return []
    wcol = "w_sum" if "w_sum" in d.columns else "n_stu"
    out = []
    for subj in ["math", "read", "scie"]:
        dd = d.dropna(subset=[subj])
        # Peso de expansion: suma de pesos estudiantiles de la escuela (W_FSTUWT).
        w = pd.to_numeric(dd[wcol], errors="coerce").fillna(0).to_numpy(float)
        if not (w > 0).any():
            w = dd["n_stu"].to_numpy(float)
        fit = wols(dd["escs"].to_numpy(float), dd[subj].to_numpy(float), w)
        if fit:
            fit.update(subject=subj, n_schools=int(len(dd)),
                       x_min=float(dd["escs"].min()), x_max=float(dd["escs"].max()))
            out.append(fit)
    return out


def find_sav_all(year: int) -> str | None:
    """Archivo de estudiantes con TODOS los paises (para tendencia OCDE)."""
    if year == 2015:
        p = os.path.join(EXTRACT, "2015", "CY6_MS_CMB_STU_QQQ.sav")
        if os.path.exists(p):
            return p
    return find_sav(year, "stu")


def load_oecd_students(year: int) -> pd.DataFrame | None:
    pvs = io.pv_names(year, "MATH") + io.pv_names(year, "READ") + io.pv_names(year, "SCIE")
    if year in OLD_CYCLES:
        cfg = OLD_CYCLES[year]
        cols = ["CNT", "SCHOOLID", "ESCS", "W_FSTUWT", "GRADE", "ST01Q01"] + pvs
        txt, sps = _abs(cfg["stu"][0]), _abs(cfg["stu"][1])
        if not (os.path.exists(txt) and os.path.exists(sps)):
            return None
        df = io.read_txt(sps, txt, usecols=cols)
        df = df.rename(columns={"SCHOOLID": "CNTSCHID"})
    else:
        path = find_sav_all(year)
        if not path:
            return None
        cols = io.sav_columns(path)
        keep = [c for c in (["CNT", "CNTSCHID", "W_FSTUWT", "ESCS", "GRADE"] + pvs) if c in cols]
        df = io.read_sav(path, usecols=keep)
    df = io.clean_missing(df, ["ESCS"], threshold=10.0)
    df = io.clean_missing(df, pvs, threshold=9990.0)
    if "CNT" not in df.columns:
        return None
    df["CNT"] = df["CNT"].astype(str).str.strip()
    return df[df["CNT"].isin(io.oecd_countries(year))]


def build_oecd_trends(year: int) -> list[dict]:
    log(f"  tendencia OCDE {year}: leyendo todos los paises ...")
    df = load_oecd_students(year)
    if df is None or not len(df):
        return []
    io.add_subject_means(df, year)
    schools = io.aggregate_schools(df, year)
    # Fig. 5 OCDE: solo escuelas con estudiantes en el grado modal.
    ids = modal_school_ids(df)
    if ids is not None:
        schools["school_id"] = norm_id(schools["school_id"])
        schools = schools[schools["school_id"].isin(ids)].copy()
    log(f"  OCDE {year}: {len(schools)} escuelas (con grado modal)")
    return trend_from_schools(schools)


# Ciclos en formato TXT de ancho fijo (2000-2012). Se usa el control SPSS para
# las posiciones y una variable de gestion propia de cada ciclo.
OLD_CYCLES = {
    2012: dict(stu=("raw/extracted/2012/INT_STU12_DEC03.txt", "raw/PISA2012_SPSS_student.txt"),
               sch=("raw/extracted/2012/INT_SCQ12_DEC03.txt", "raw/PISA2012_SPSS_school.txt"),
               schtype="SC01Q01"),
    2009: dict(stu=("raw/extracted/2009/INT_STQ09_DEC11.txt", "raw/PISA2009_SPSS_student.txt"),
               sch=("raw/extracted/2009/INT_SCQ09_Dec11.txt", "raw/PISA2009_SPSS_school.txt"),
               schtype="SC02Q01"),
    2006: dict(stu=("raw/extracted/2006/INT_Stu06_Dec07.txt", "raw/PISA2006_SPSS_student.txt"),
               sch=("raw/extracted/2006/INT_Sch06_Dec07.txt", "raw/PISA2006_SPSS_school.txt"),
               schtype="SC02Q01"),
}


def _abs(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def load_old_students(year: int) -> pd.DataFrame | None:
    cfg = OLD_CYCLES[year]
    pvs = io.pv_names(year, "MATH") + io.pv_names(year, "READ") + io.pv_names(year, "SCIE")
    cols = ["CNT", "STRATUM", "SCHOOLID", "ESCS", "W_FSTUWT", "GRADE", "ST01Q01"] + pvs
    txt, sps = _abs(cfg["stu"][0]), _abs(cfg["stu"][1])
    if not (os.path.exists(txt) and os.path.exists(sps)):
        return None
    df = io.read_txt(sps, txt, usecols=cols, filter_cnt="ARG")
    df = df.rename(columns={"SCHOOLID": "CNTSCHID"})
    df = io.clean_missing(df, ["ESCS"], threshold=10.0)
    return io.clean_missing(df, pvs, threshold=9990.0)


def load_old_school_frame(year: int) -> pd.DataFrame | None:
    cfg = OLD_CYCLES[year]
    cols = ["CNT", "STRATUM", "SCHOOLID", cfg["schtype"]]
    txt, sps = _abs(cfg["sch"][0]), _abs(cfg["sch"][1])
    if not (os.path.exists(txt) and os.path.exists(sps)):
        return None
    df = io.read_txt(sps, txt, usecols=cols, filter_cnt="ARG")
    return df.rename(columns={"SCHOOLID": "CNTSCHID", cfg["schtype"]: "SC013Q01TA"})


def national_from_students(stu: pd.DataFrame, year: int, w_col: str = "W_FSTUWT") -> list[dict]:
    """Promedio y desvio estandar GENERALES de Argentina (nivel estudiante,
    ponderados por W_FSTUWT), por materia. Es la referencia nacional oficial."""
    out: list[dict] = []
    if w_col not in stu.columns:
        return out
    w = pd.to_numeric(stu[w_col], errors="coerce").to_numpy(dtype=float)
    for subj in ["math", "read", "scie"]:
        col = subj + "_m"
        if col not in stu.columns:
            continue
        x = pd.to_numeric(stu[col], errors="coerce").to_numpy(dtype=float)
        m = ~np.isnan(x) & ~np.isnan(w) & (w > 0)
        if not m.any() or w[m].sum() == 0:
            continue
        W = w[m].sum()
        mean = float((w[m] * x[m]).sum() / W)
        var = float((w[m] * (x[m] - mean) ** 2).sum() / W)
        out.append({"year": int(year), "subject": subj, "mean": round(mean, 2),
                    "sd": round(var ** 0.5, 2), "n": int(m.sum())})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", nargs="*", type=int,
                    default=[2025, 2022, 2018, 2012, 2009, 2006, 2000],
                    help="ciclos a construir (2015 excluido por problemas de muestra; 2000 pendiente)")
    ap.add_argument("--no-oecd", action="store_true")
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--only-national", action="store_true",
                    help="solo calcula data/pisa_arg_national.csv y no toca escuelas/tendencias")
    args = ap.parse_args()

    os.makedirs(DATA, exist_ok=True)
    mapping = json.load(open(os.path.join(os.path.dirname(__file__), "region_mapping.json"), encoding="utf-8"))

    all_schools: list[pd.DataFrame] = []
    all_trends: list[dict] = []
    all_national: list[dict] = []

    for year in sorted(set(args.cycles)):
        log(f"== Ciclo {year} ==")
        ensure_extracted(year)
        if year in OLD_CYCLES:
            stu = load_old_students(year)
            frame = load_old_school_frame(year)
        else:
            stu = load_arg_students(year)
            frame = load_school_frame(year)
        if stu is None or not len(stu):
            log(f"  sin microdatos de estudiantes; se omite {year}")
            continue
        stu.columns = [c.strip() for c in stu.columns]
        io.add_subject_means(stu, year)

        nat = national_from_students(stu, year)
        all_national.extend(nat)
        if args.only_national:
            log(f"  nacional {year}: " + ", ".join(f"{r['subject']}={r['mean']}±{r['sd']}" for r in nat))
            continue

        schools = io.aggregate_schools(stu, year, id_col="CNTSCHID")

        if frame is not None:
            frame.columns = [c.strip() for c in frame.columns]
            frame["CNTSCHID"] = norm_id(frame["CNTSCHID"])
            schools["school_id"] = norm_id(schools["school_id"])
            frame = assign_region_sector(frame, year, mapping)
            schools = schools.merge(
                frame[["CNTSCHID", "region", "sector"]].rename(columns={"CNTSCHID": "school_id"}),
                on="school_id", how="left")
        else:
            schools["region"] = None
            schools["sector"] = "NR"

        # Fig. 5 OCDE: solo escuelas con estudiantes en el grado modal.
        ids = modal_school_ids(stu)
        if ids is not None:
            before = len(schools)
            schools = schools[schools["school_id"].isin(ids)].copy()
            log(f"  grado modal: {before} -> {len(schools)} escuelas con estudiantes en grado modal")

        schools["year"] = year
        schools = schools[["year", "school_id", "region", "sector", "n_stu", "n_escs",
                           "w_sum", "escs", "math", "read", "scie",
                           "sd_escs", "sd_math", "sd_read", "sd_scie"]]

        # Excluir resultados región-año atípicos definidos en EXCLUDE_REGION_YEARS.
        drop = pd.Series(False, index=schools.index)
        for (yy, rr) in EXCLUDE_REGION_YEARS:
            if yy == year:
                drop |= schools["region"].astype(str).apply(lambda v: rr in v.split("|"))
        if drop.any():
            log(f"  excluidas {int(drop.sum())} escuelas de {year} por región atípica")
            schools = schools[~drop].copy()

        all_schools.append(schools)
        log(f"  escuelas: {len(schools)} | regiones: {schools['region'].notna().sum()}")

        for t in trend_from_schools(schools):
            t.update(year=year, scope="ARG")
            all_trends.append(t)
        if not args.no_oecd:
            for t in build_oecd_trends(year):
                t.update(year=year, scope="OCDE")
                all_trends.append(t)

    nat_df = pd.DataFrame(all_national)
    if len(nat_df):
        nat_df = nat_df[["year", "subject", "mean", "sd", "n"]]
        nat_df.to_csv(os.path.join(DATA, "pisa_arg_national.csv"), index=False, float_format="%.2f")
        log(f"OK nacional: {len(nat_df)} filas -> data/pisa_arg_national.csv")

    if args.only_national:
        return 0

    if not all_schools:
        log("No se construyo ninguna base. Revisar raw/.")
        return 1

    schools_all = pd.concat(all_schools, ignore_index=True)
    schools_all.to_csv(os.path.join(DATA, "pisa_arg_schools.csv"), index=False,
                       float_format="%.5f")
    trends = pd.DataFrame(all_trends)
    if len(trends):
        trends = trends[["year", "scope", "subject", "slope", "intercept", "r", "n_schools", "x_min", "x_max"]]
        trends.to_csv(os.path.join(DATA, "pisa_arg_trends.csv"), index=False, float_format="%.5f")

    meta = {
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "years": sorted(schools_all["year"].unique().tolist()),
        "n_schools": {int(y): int(n) for y, n in schools_all.groupby("year").size().items()},
        "flags": {str(k): v for k, v in FLAGS.items() if k in set(schools_all["year"])},
        "excluded_region_years": [f"{y} {r}" for (y, r) in sorted(EXCLUDE_REGION_YEARS)],
        "source": "Microdatos PISA OCDE (public use files)",
        "note": "Regiones mapeadas a partir de STRATUM (mejor esfuerzo); pueden faltar en ciclos antiguos.",
    }
    with open(os.path.join(DATA, "pisa_arg_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    log(f"OK escuelas: {len(schools_all)} filas -> data/pisa_arg_schools.csv")
    log(f"OK tendencias: {len(trends)} filas -> data/pisa_arg_trends.csv")

    if not args.keep_raw:
        log("Borrando raw/ (usar --keep-raw para conservar).")
        shutil.rmtree(RAW, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
