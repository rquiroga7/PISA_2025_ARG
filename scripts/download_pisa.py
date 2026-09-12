#!/usr/bin/env python3
"""Descarga los microdatos PUF de PISA (ciclos 2000-2025) y los archivos de
re-escalamiento de ESCS a raw/.

Uso:
    python scripts/download_pisa.py                # todos los ciclos de Argentina
    python scripts/download_pisa.py --cycles 2022 2018
    python scripts/download_pisa.py --only escs    # solo archivos de ESCS
    python scripts/download_pisa.py --list

Los archivos son grandes (~4 GB en total) y quedan en raw/, que esta en
.gitignore. Se pueden borrar despues de correr build_database.py.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "raw")
LOG = os.path.join(RAW, "download_log.txt")

# Ciclos en los que participo Argentina (2003 no participo).
AR_CYCLES = [2000, 2006, 2009, 2012, 2015, 2018, 2022, 2025]

# Manifiesto de URLs. Cada entrada: (nombre local, url).
MANIFEST: dict[int, list[tuple[str, str]]] = {
    2025: [
        ("CY09_MS_STU_PUF.zip", "https://webfs.oecd.org/pisa2022/2025/CY09_MS_STU_PUF.zip"),
        ("CY09_MS_SCH_PUF.zip", "https://webfs.oecd.org/pisa2022/2025/CY09_MS_SCH_PUF.zip"),
    ],
    2022: [
        ("STU_QQQ_SPSS.zip", "https://webfs.oecd.org/pisa2022/STU_QQQ_SPSS.zip"),
        ("SCH_QQQ_SPSS.zip", "https://webfs.oecd.org/pisa2022/SCH_QQQ_SPSS.zip"),
    ],
    2018: [
        ("SPSS_STU_QQQ.zip", "https://webfs.oecd.org/pisa2018/SPSS_STU_QQQ.zip"),
        ("SPSS_SCH_QQQ.zip", "https://webfs.oecd.org/pisa2018/SPSS_SCH_QQQ.zip"),
    ],
    2015: [
        ("PUF_SPSS_COMBINED_CMB_STU_QQQ.zip", "https://webfs.oecd.org/pisa/PUF_SPSS_COMBINED_CMB_STU_QQQ.zip"),
        ("PUF_SPSS_COMBINED_CMB_SCH_QQQ.zip", "https://webfs.oecd.org/pisa/PUF_SPSS_COMBINED_CMB_SCH_QQQ.zip"),
        ("PUF_SPSS_COMBINED_CM2_STU_QQQ_COG_QTM_SCH_TCH.zip",
         "https://webfs.oecd.org/pisa/PUF_SPSS_COMBINED_CM2_STU_QQQ_COG_QTM_SCH_TCH.zip"),
    ],
    2012: [
        ("INT_STU12_DEC03.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2012-datasets/main-survey/data-sets-in-txt-format/INT_STU12_DEC03.zip"),
        ("INT_SCQ12_DEC03.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2012-datasets/main-survey/data-sets-in-txt-format/INT_SCQ12_DEC03.zip"),
        ("PISA2012_SPSS_student.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2012-datasets/main-survey/sas-and-spss-control-files/SPSS%20syntax%20to%20read%20in%20student%20questionnaire%20data%20file.txt"),
        ("PISA2012_SPSS_school.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2012-datasets/main-survey/sas-and-spss-control-files/SPSS%20syntax%20to%20read%20in%20school%20questionnaire%20data%20file.txt"),
    ],
    2009: [
        ("INT_STQ09_DEC11.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2009-datasets/data-sets-in-txt-format/INT_STQ09_DEC11.zip"),
        ("INT_SCQ09_Dec11.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2009-datasets/data-sets-in-txt-format/INT_SCQ09_Dec11.zip"),
        ("PISA2009_SPSS_student.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2009-datasets/sas-and-spss-control-files/PISA2009_SPSS_student.txt"),
        ("PISA2009_SPSS_school.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2009-datasets/sas-and-spss-control-files/PISA2009_SPSS_school.txt"),
    ],
    2006: [
        ("INT_Stu06_Dec07.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2006-datasets/data-sets-in-txt-format/INT_Stu06_Dec07.zip"),
        ("INT_Sch06_Dec07.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2006-datasets/data-sets-in-txt-format/INT_Sch06_Dec07.zip"),
        ("PISA2006_SPSS_student.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2006-datasets/sas-and-spss-control-files/PISA2006_SPSS_student.txt"),
        ("PISA2006_SPSS_school.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2006-datasets/sas-and-spss-control-files/PISA2006_SPSS_school.txt"),
    ],
    2000: [
        ("intstud_read.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/data-sets-in-txt-formats/intstud_read.zip"),
        ("intstud_math.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/data-sets-in-txt-formats/intstud_math.zip"),
        ("intstud_scie.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/data-sets-in-txt-formats/intstud_scie.zip"),
        ("intscho.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/data-sets-in-txt-formats/intscho.zip"),
        ("PISA2000_ESCS.zip",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/PISA2000_ESCS.zip"),
        ("PISA2000_SPSS_student_mathematics.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/sas-and-spss-control-files/PISA2000_SPSS_student_mathematics.txt"),
        ("PISA2000_SPSS_student_reading.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/sas-and-spss-control-files/PISA2000_SPSS_student_reading.txt"),
        ("PISA2000_SPSS_student_science.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/sas-and-spss-control-files/PISA2000_SPSS_student_science.txt"),
        ("PISA2000_SPSS_school_questionnaire.txt",
         "https://www.oecd.org/content/dam/oecd/en/data/datasets/pisa/pisa-2000-datasets/sas-and-spss-control-files/PISA2000_SPSS_school_questionnaire.txt"),
    ],
}

# Archivos de ESCS re-escalado para analisis de tendencia.
ESCS_FILES = [
    ("trend_escs_SPSS.zip", "https://webfs.oecd.org/pisa/trend_escs_SPSS.zip"),
    ("escs_trend.zip", "https://webfs.oecd.org/pisa2022/escs_trend.zip"),
]


def log(msg: str) -> None:
    os.makedirs(RAW, exist_ok=True)
    line = time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def already_have(path: str) -> bool:
    """True si el archivo existe y no tiene un .part pendiente."""
    return os.path.exists(path) and os.path.getsize(path) > 0 and not os.path.exists(path + ".part")


def download_ps(url: str, dest: str) -> bool:
    """Fallback con PowerShell/System.Net (Schannel), para www.oecd.org (403 a OpenSSL)."""
    ps = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_ps.ps1")
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", ps, "-Url", url, "-Dest", dest],
                       check=True, timeout=7200)
        log(f"OK  {os.path.basename(dest)} (powershell, {os.path.getsize(dest)/1e6:.1f} MB)")
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"ERROR powershell {os.path.basename(dest)}: {exc}")
        return False


def download(url: str, dest: str, retries: int = 4, chunk: int = 1 << 20) -> bool:
    """Descarga con reanudacion (HTTP Range) y reintentos. Devuelve True si OK."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    for attempt in range(1, retries + 1):
        try:
            pos = os.path.getsize(part) if os.path.exists(part) else 0
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (PISA-ARG build)"})
            if pos:
                req.add_header("Range", f"bytes={pos}-")
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = resp.length + pos if resp.length is not None else None
                mode = "ab" if pos and resp.status == 206 else "wb"
                if mode == "wb":
                    pos = 0
                got = pos
                with open(part, mode) as fh:
                    while True:
                        buf = resp.read(chunk)
                        if not buf:
                            break
                        fh.write(buf)
                        got += len(buf)
                        if total:
                            pct = 100.0 * got / total
                            print(f"\r  {os.path.basename(dest)}: {pct:5.1f}% "
                                  f"({got/1e6:7.1f}/{total/1e6:7.1f} MB)", end="", flush=True)
            print()
            os.replace(part, dest)
            log(f"OK  {os.path.basename(dest)} ({os.path.getsize(dest)/1e6:.1f} MB)")
            return True
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            log(f"WARN intento {attempt}/{retries} fallo {os.path.basename(dest)}: {exc}")
            time.sleep(3 * attempt)
    log(f"ERROR no se pudo descargar {url}")
    return False


# .sav ya presentes en la raiz del repo que permiten omitir el .zip del ciclo.
LOCAL_SAV = {
    2025: ["CY09_MS_STU_PUF.sav", "CY09_MS_SCH_PUF.sav"],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", nargs="*", type=int, default=AR_CYCLES,
                    help="ciclos a descargar (por defecto: los de Argentina)")
    ap.add_argument("--only", choices=["cycles", "escs"], default=None)
    ap.add_argument("--list", action="store_true", help="mostrar el manifiesto y salir")
    ap.add_argument("--force", action="store_true", help="re-descargar aunque exista")
    args = ap.parse_args()

    os.makedirs(RAW, exist_ok=True)
    if args.list:
        for cyc in sorted(MANIFEST, reverse=True):
            print(f"{cyc}:")
            for name, url in MANIFEST[cyc]:
                print(f"   {name}")
        print("ESCS:")
        for name, _ in ESCS_FILES:
            print(f"   {name}")
        return 0

    jobs: list[tuple[str, str]] = []
    if args.only in (None, "cycles"):
        for cyc in args.cycles:
            local = LOCAL_SAV.get(cyc, [])
            if local and all(os.path.exists(os.path.join(os.path.dirname(RAW), f)) for f in local):
                print(f"[skip] ciclo {cyc}: ya hay {', '.join(local)} en la raiz")
                continue
            jobs += MANIFEST.get(cyc, [])
    if args.only in (None, "escs"):
        jobs += ESCS_FILES

    total = len(jobs)
    log(f"Iniciando descarga de {total} archivo(s) a {RAW}")
    for i, (name, url) in enumerate(jobs, 1):
        dest = os.path.join(RAW, name)
        if not args.force and already_have(dest):
            print(f"[{i}/{total}] ya existe: {name}")
            continue
        print(f"[{i}/{total}] {name}")
        ok = download(url, dest)
        if not ok:
            log(f"reintentando {name} con PowerShell ...")
            download_ps(url, dest)

    log("Descarga finalizada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
