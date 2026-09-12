#!/usr/bin/env python3
"""Genera index.html a partir de la base compacta en data/.

Incluye:
  - Selector de anio.
  - Scatter de 3 paneles (Matematica / Lectura / Ciencias) por escuela.
  - Grafico de lineas de 3 paneles con la evolucion por anio.
  - Filtros de region, gestion y ajustes de tendencia.

Uso:
    python scripts/build_page.py
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

REGION_ORDER = ["CABA", "Buenos Aires", "Córdoba", "Santa Fe", "Mendoza",
                "NOA", "NEA", "Cuyo", "Patagonia"]
REGION_COLOR = {
    "CABA": "#E41A1C", "Buenos Aires": "#377EB8", "Córdoba": "#4DAF4A",
    "Santa Fe": "#FF7F00", "Mendoza": "#984EA3", "NOA": "#A65628",
    "NEA": "#F781BF", "Cuyo": "#1B9E77", "Patagonia": "#E6AB02",
}
SUBJECTS = [("math", "Matemática"), ("read", "Lectura"), ("scie", "Ciencias")]
DIV_ID = "pisa-graph-scatter"
EVO_ID = "pisa-graph-evolution"


def load_data() -> dict:
    schools = pd.read_csv(os.path.join(DATA, "pisa_arg_schools.csv"))
    trends = pd.read_csv(os.path.join(DATA, "pisa_arg_trends.csv")) if \
        os.path.exists(os.path.join(DATA, "pisa_arg_trends.csv")) else pd.DataFrame()
    meta = json.load(open(os.path.join(DATA, "pisa_arg_meta.json"), encoding="utf-8"))

    rows = []
    for r in schools.itertuples(index=False):
        region = r.region if isinstance(r.region, str) else None
        rows.append([
            int(r.year), str(r.school_id), region,
            None if (not isinstance(r.sector, str)) else r.sector,
            int(r.n_stu), int(r.n_escs),
            None if pd.isna(r.escs) else round(float(r.escs), 4),
            None if pd.isna(r.math) else round(float(r.math), 1),
            None if pd.isna(r.read) else round(float(r.read), 1),
            None if pd.isna(r.scie) else round(float(r.scie), 1),
            None if pd.isna(r.sd_escs) else round(float(r.sd_escs), 3),
            None if pd.isna(r.sd_math) else round(float(r.sd_math), 1),
            None if pd.isna(r.sd_read) else round(float(r.sd_read), 1),
            None if pd.isna(r.sd_scie) else round(float(r.sd_scie), 1),
            None if pd.isna(r.w_sum) else round(float(r.w_sum), 1),
        ])

    tr = {"ARG": {}, "OCDE": {}}
    for r in trends.itertuples(index=False):
        tr.setdefault(r.scope, {}).setdefault(str(int(r.year)), {})[r.subject] = {
            "b": round(float(r.slope), 4), "a": round(float(r.intercept), 4),
            "r": round(float(r.r), 3), "n": int(r.n_schools),
            "x0": round(float(r.x_min), 4), "x1": round(float(r.x_max), 4),
        }

    national = {}
    nat_path = os.path.join(DATA, "pisa_arg_national.csv")
    if os.path.exists(nat_path):
        for r in pd.read_csv(nat_path).itertuples(index=False):
            national.setdefault(str(int(r.year)), {})[r.subject] = {
                "mean": round(float(r.mean), 2), "sd": round(float(r.sd), 2), "n": int(r.n)}

    est = {}
    ep = os.path.join(DATA, "pisa_arg_estimates.csv")
    if os.path.exists(ep):
        for r in pd.read_csv(ep).itertuples(index=False):
            est.setdefault(str(int(r.year)), {}).setdefault(r.region, {}).setdefault(r.sector, {})[r.subject] = {
                "mean": round(float(r.mean), 2), "se": round(float(r.se), 3)}

    links = []
    lp = os.path.join(DATA, "linking_errors.csv")
    if os.path.exists(lp):
        links = pd.read_csv(lp).to_dict(orient="records")

    ws = [r[14] for r in rows if r[14] is not None]
    wmed = float(pd.Series(ws).median()) if ws else 1.0
    rng = []
    for regs in est.values():
        for d2 in regs.values():
            for d3 in d2.values():
                for cell in d3.values():
                    rng += [cell['mean'] - 1.96 * cell['se'], cell['mean'] + 1.96 * cell['se']]
    evo_range = [round(min(rng) - 5), round(max(rng) + 5)] if rng else [320, 460]

    return {
        "years": sorted(int(y) for y in schools["year"].unique()),
        "regions": REGION_ORDER,
        "subjects": [s[0] for s in SUBJECTS],
        "schools": rows,
        "trends": tr,
        "national": national,
        "est": est,
        "links": links,
        "wmed": wmed,
        "evoRange": evo_range,
        "meta": meta,
        "built": meta.get("built", ""),
    }


def build_html(db: dict) -> str:
    data_js = json.dumps(db, ensure_ascii=False, separators=(",", ":"))
    region_js = json.dumps([{"key": k, "color": REGION_COLOR[k]} for k in REGION_ORDER], ensure_ascii=False)
    subject_js = json.dumps([{"key": k, "label": lbl} for k, lbl in SUBJECTS], ensure_ascii=False)
    years = db["years"]
    default_year = years[-1] if years else 2025
    year_buttons = "\n".join(
        f'<button type="button" class="pisa-chip pisa-year" data-year="{y}" '
        f'aria-pressed="{"true" if y == default_year else "false"}">{y}</button>'
        for y in years
    )
    region_buttons = "\n".join(
        f'<button type="button" class="pisa-chip" data-region="{k}" aria-pressed="true" '
        f'title="Mostrar/ocultar {k}"><span class="pisa-dot" style="background:{REGION_COLOR[k]}"></span>{k}</button>'
        for k in REGION_ORDER
    )

    return _TEMPLATE.replace("__DATA_JS__", data_js) \
                    .replace("__REGIONS_JS__", region_js) \
                    .replace("__SUBJECTS_JS__", subject_js) \
                    .replace("__DEFAULT_YEAR__", str(default_year)) \
                    .replace("__YEAR_BUTTONS__", year_buttons) \
                    .replace("__REGION_BUTTONS__", region_buttons) \
                    .replace("__DIV_ID__", DIV_ID) \
                    .replace("__EVO_ID__", EVO_ID)


_TEMPLATE = r"""<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8" />
    <title>PISA 2025 Argentina: escuelas y nivel socioeconómico</title>
    <meta name="description" content="Visualizador interactivo de PISA Argentina (2000-2025): desempeño por escuela vs. nivel socioeconómico y evolución por año." />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="PISA Argentina" />
    <meta property="og:title" content="PISA Argentina: escuelas y nivel socioeconómico" />
    <meta property="og:description" content="Visualizador interactivo de PISA Argentina (2000-2025): desempeño por escuela vs. nivel socioeconómico y evolución por año." />
    <meta property="og:image" content="https://rquiroga7.github.io/PISA_2025_ARG/pisa2025_OG.png" />
    <meta property="og:image:type" content="image/png" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="PISA Argentina: escuelas y nivel socioeconómico" />
    <meta name="twitter:description" content="Visualizador interactivo de PISA Argentina (2000-2025): desempeño por escuela vs. nivel socioeconómico y evolución por año." />
    <meta name="twitter:image" content="https://rquiroga7.github.io/PISA_2025_ARG/pisa2025_OG.png" />
    <style>
        body {font-family: Arial, Helvetica, sans-serif; margin: 16px 16px 32px;}
        #pisa-controls {position: sticky; top: 0; z-index: 1000; display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; max-width: 1110px; margin: 0 0 8px 70px; padding: 10px 0; background: #fff; border-bottom: 1px solid #e3e3e3; box-shadow: 0 2px 4px rgba(0,0,0,0.04); font-size: 14px; color: #111;}
        .pisa-group {display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap;}
        .pisa-group-label {font-weight: 700; margin-right: 2px;}
        .pisa-chip {cursor: pointer; border: 1px solid #9a9a9a; background: #ececec; border-radius: 999px; padding: 3px 11px; font-size: 13px; line-height: 1.6; display: inline-flex; align-items: center; gap: 7px; color: #111;}
        .pisa-chip[aria-pressed="false"] {opacity: 0.4; background: #fff;}
        .pisa-chip:hover {border-color: #555;}
        .pisa-chip:focus-visible {outline: 2px solid #000; outline-offset: 2px;}
        .pisa-year[aria-pressed="true"] {background:#0b3d91; color:#fff; border-color:#0b3d91; font-weight:700;}
        .pisa-dot {width: 11px; height: 11px; border-radius: 50%; display: inline-block; border: 1px solid rgba(0,0,0,0.35);}
        .pisa-sym {font-size: 12px; width: 14px; text-align: center; display: inline-block;}
        .pisa-dash {display: inline-block; width: 20px; border-top: 3px dashed #111;}
        .pisa-dotline {display: inline-block; width: 20px; border-top: 3px dotted #000;}
        .pisa-reset {cursor: pointer; border: 1px solid #9a9a9a; background: #fff; border-radius: 6px; padding: 4px 12px; font-size: 13px; color: #111;}
        .pisa-reset:hover {background: #f0f0f0;}
        #pisa-caption {max-width: 1110px; margin: 10px 20px 28px 70px; font-size: 13px; line-height: 1.5; color: #555; white-space: normal; overflow-wrap: break-word;}
        .pisa-subtitle {max-width: 1110px; margin: 18px 20px 6px 70px; font-size: 14px; font-weight: 700; color: #222;}
        .pisa-note {max-width: 1110px; margin: 4px 20px 18px 70px; font-size: 12px; color: #777;}
        .pisa-graph {height: 520px; width: 1200px;}
        .pisa-graph-evo {height: 420px; width: 1200px;}
    </style>
</head>
<body>
    <div id="pisa-controls" role="group" aria-label="Filtros del gráfico">
        <span class="pisa-group"><span class="pisa-group-label">Año:</span>
__YEAR_BUTTONS__
        </span>
        <span class="pisa-group"><span class="pisa-group-label">Región:</span>
__REGION_BUTTONS__
        </span>
        <span class="pisa-group"><span class="pisa-group-label">Gestión:</span>
            <button type="button" class="pisa-chip" data-sector="Pública" aria-pressed="true" title="Mostrar/ocultar escuelas públicas"><span class="pisa-sym">●</span>Pública</button>
            <button type="button" class="pisa-chip" data-sector="Privada" aria-pressed="true" title="Mostrar/ocultar escuelas privadas"><span class="pisa-sym">▲</span>Privada</button>
        </span>
        <span class="pisa-group"><span class="pisa-group-label">Ajuste:</span>
            <button type="button" class="pisa-chip" data-trend="arg" aria-pressed="true" title="Tendencia MCO ponderada por estudiantes sobre las escuelas argentinas del año seleccionado."><span class="pisa-dash"></span>Tendencia (ARG)</button>
            <button type="button" class="pisa-chip" data-trend="oecd" aria-pressed="false" title="Tendencia MCO ponderada sobre escuelas de países OCDE del año seleccionado."><span class="pisa-dash" style="border-top-color:#808080"></span>Tendencia (OCDE)</button>
            <button type="button" class="pisa-chip" data-trend="sel" aria-pressed="false" title="Tendencia MCO ponderada sobre las escuelas visibles según los filtros."><span class="pisa-dotline" style="border-top-color:#FF0000"></span>Tendencia (seleccionados)</button>
        </span>
        <button type="button" id="pisa-reset" class="pisa-reset" title="Mostrar todo">Restablecer</button>
    </div>

    <div class="pisa-subtitle">Desempeño por escuela vs. nivel socioeconómico (<span id="pisa-year-label">__DEFAULT_YEAR__</span>)</div>
    <div id="__DIV_ID__" class="pisa-graph"></div>

    <div class="pisa-subtitle">Evolución por año, por región y materia</div>
    <div class="pisa-note">Una línea por región seleccionada y por materia (mismos colores que el gráfico de arriba), con el promedio ponderado por <b>peso de expansión</b> (suma de W_FSTUWT) de sus escuelas en cada año. Los tramos que cruzan años sin datos se dibujan con línea punteada. La línea gris es el promedio general de Argentina —total, pública o privada según la gestión seleccionada— con su <b>IC 95 %</b> (error de replicación BRR/Fay + reglas de Rubin), igual que las líneas por región. Para comparar dos años hay que sumar el <b>linking error</b> de PISA (2018↔2022: mat 2,24 · lec 1,47 · cie 1,61); sin él, el error de la diferencia queda subestimado.</div></div>
    <div id="__EVO_ID__" class="pisa-graph-evo"></div>

    <div id="pisa-caption">
        Cada burbuja = una escuela (solo escuelas con estudiantes en el <b>grado modal</b> de 15 años; metodología de la Figura 5 de la OCDE). El <b>tamaño</b> es proporcional a la población de estudiantes de 15 años que representa (suma de W_FSTUWT, escala fija, no cambia con los filtros); las burbujas más chicas se dibujan encima de las más grandes. X = ESCS promedio (W_FSTUWT); Y = puntaje promedio (media de los valores plausibles, 10 en 2015+ y 5 hasta 2012). Color = región; símbolo = gestión pública (●) / privada (▲). Las regiones se reconstruyen del estrato muestral (mejor esfuerzo); en 2009 y 2012 el estrato «Centro» se asigna a la vez a Buenos Aires, Córdoba y Santa Fe. Fuente: microdatos PISA OCDE; ciclos 2006, 2009, 2012, 2018, 2022 y 2025 (2015 excluido por problemas de muestra). <b>Advertencia metodológica:</b> estimaciones con pesos de expansión (W_FSTUWT); errores estándar por replicación BRR/Fay (80 réplicas, factor de Fay 0.5) y reglas de Rubin sobre los valores plausibles, mostrados como IC 95 %. Para diferencias entre años debe sumarse el <i>linking error</i> de PISA (disponible por ahora solo para 2018↔2022). El gráfico no debe usarse para ordenar escuelas.
    </div></div>

    <script charset="utf-8" src="https://cdn.plot.ly/plotly-4.0.0.min.js" integrity="sha256-FEYfO0yRyLtZCpnW0Dw/0DHKQO7Afrq3ml4+rBB818o=" crossorigin="anonymous"></script>
    <script>
    (function () {
        const DB = __DATA_JS__;
        const REGIONS = __REGIONS_JS__;
        const SUBJECTS = __SUBJECTS_JS__;
        const DEFAULT_YEAR = __DEFAULT_YEAR__;
        const AXES = ["x", "x2", "x3"];
        const EVO_AXES = ["x", "x2", "x3"];
        const EVO_Y = ["y", "y2", "y3"];

        const state = {
            year: DEFAULT_YEAR,
            regions: Object.fromEntries(REGIONS.map(r => [r.key, true])),
            sectors: { "Pública": true, "Privada": true },
            trends: { arg: true, oecd: false, sel: false }
        };

        const REGION_COLOR = Object.fromEntries(REGIONS.map(r => [r.key, r.color]));

        // Tamano de burbuja segun la Figura 5 de OCDE: el area es proporcional a la
        // poblacion de estudiantes de 15 anios que representa cada escuela (w_sum).
        function bubbleSize(w) {
            if (w == null || w <= 0) return 3;
            return Math.max(3, Math.min(34, 9 * Math.sqrt(w / (DB.wmed || 1))));
        }

        function schoolsForYear(year) {
            return DB.schools.filter(s => s[0] === year);
        }
        function schoolRegions(s) {
            return (s[2] || "").split("|").filter(Boolean);
        }
        function visible(s) {
            const regs = schoolRegions(s);
            const regionOk = regs.length === 0 ? true : regs.some(k => state.regions[k]);
            const sectorOk = !s[3] || state.sectors[s[3]];
            return regionOk && sectorOk;
        }
        function fmt(v, d) { return (v === null || v === undefined || isNaN(v)) ? "s/d" : v.toFixed(d); }

        // ---- OLS ponderado ----
        function wols(pts) {
            const n = pts.length;
            if (n < 2) return null;
            let sw = 0, mx = 0, my = 0;
            for (const p of pts) { sw += p.w; mx += p.w * p.x; my += p.w * p.y; }
            if (sw <= 0) return null;
            mx /= sw; my /= sw;
            let sxx = 0, sxy = 0, syy = 0;
            for (const p of pts) { const dx = p.x - mx, dy = p.y - my; sxx += p.w * dx * dx; sxy += p.w * dx * dy; syy += p.w * dy * dy; }
            if (sxx === 0) return null;
            const b = sxy / sxx, a = my - b * mx;
            const r = syy > 0 ? sxy / Math.sqrt(sxx * syy) : 0;
            return { a, b, r, xmin: Math.min(...pts.map(p => p.x)), xmax: Math.max(...pts.map(p => p.x)) };
        }

        // ---- Scatter (burbujas: area proporcional a la poblacion representada, Fig. 5 OCDE) ----
        // Una traza por materia, con los puntos ordenados por tamano DESCENDENTE para que
        // las burbujas mas chicas se dibujen por encima de las mas grandes cuando se solapan.
        function buildScatterTraces() {
            const data = schoolsForYear(state.year);
            const traces = [];
            for (let si = 0; si < SUBJECTS.length; si++) {
                const { key, label } = SUBJECTS[si];
                const pts = data.filter(s => {
                    const regs = schoolRegions(s);
                    const regionOk = regs.some(k => state.regions[k]);
                    const sectorOk = !s[3] || state.sectors[s[3]];
                    return regionOk && sectorOk && s[6] !== null && s[7 + si] !== null;
                });
                if (!pts.length) continue;
                pts.sort((a, b) => (b[14] || 0) - (a[14] || 0)); // grandes primero, chicos ultimos (encima)
                traces.push({
                    type: "scatter", mode: "markers", name: label, showlegend: false,
                    x: pts.map(s => s[6]), y: pts.map(s => s[7 + si]),
                    customdata: pts.map(s => [s[1], (schoolRegions(s)[0] || "s/región"), (s[3] || "s/d"), label,
                                              fmt(s[6], 2), fmt(s[7 + si], 1), s[4],
                                              (s[14] == null ? "s/d" : Math.round(s[14]).toLocaleString("es-AR"))]),
                    marker: {
                        color: pts.map(s => REGION_COLOR[schoolRegions(s)[0]] || "#888888"),
                        symbol: pts.map(s => s[3] === "Privada" ? "triangle-up" : "circle"),
                        size: pts.map(s => bubbleSize(s[14])),
                        line: { color: "white", width: 0.5 }, opacity: 0.6
                    },
                    xaxis: AXES[si], yaxis: "y" + (si ? si + 1 : ""),
                    hovertemplate: "<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>" +
                        "%{customdata[3]}<br>ESCS: %{customdata[4]}<br>" +
                        "Puntaje: %{customdata[5]}<br>N estudiantes: %{customdata[6]}<br>" +
                        "Población 15 años representada: %{customdata[7]}<extra></extra>"
                });
            }
            return traces;
        }

        function trendTraces() {
            const out = [];
            const specs = [
                { key: "arg", name: "Tendencia (ARG)", color: "#111111", dash: "dash" },
                { key: "oecd", name: "Tendencia (OCDE)", color: "#808080", dash: "dash" },
                { key: "sel", name: "Tendencia (seleccionados)", color: "#FF0000", dash: "dot" }
            ];
            for (const sp of specs) {
                for (let si = 0; si < SUBJECTS.length; si++) {
                    let fit = null;
                    if (sp.key === "sel") {
                        const pts = schoolsForYear(state.year).filter(visible)
                            .filter(s => s[6] !== null && s[7 + si] !== null)
                            .map(s => ({ x: s[6], y: s[7 + si], w: (s[14] !== null && s[14] > 0) ? s[14] : s[4] }));
                        fit = wols(pts);
                    } else {
                        const scope = sp.key === "arg" ? "ARG" : "OCDE";
                        const t = DB.trends[scope] && DB.trends[scope][String(state.year)] && DB.trends[scope][String(state.year)][SUBJECTS[si].key];
                        if (t) fit = { a: t.a, b: t.b, r: t.r, xmin: t.x0, xmax: t.x1 };
                    }
                    if (!fit) continue;
                    const y0 = fit.a + fit.b * fit.xmin, y1 = fit.a + fit.b * fit.xmax;
                    out.push({
                        type: "scatter", mode: "lines", name: sp.name, legendgroup: sp.name,
                        showlegend: false, hoverinfo: "skip",
                        visible: state.trends[sp.key],
                        x: [fit.xmin, fit.xmax], y: [y0, y1],
                        xaxis: AXES[si], yaxis: "y" + (si ? si + 1 : ""),
                        line: { color: sp.color, width: 1.6, dash: sp.dash }
                    });
                }
            }
            return out;
        }

        function scatterLayout() {
            const ann = SUBJECTS.map((s, i) => ({
                showarrow: false, text: s.label, x: [0.16, 0.5, 0.84][i], xanchor: "center",
                xref: "paper", y: 1.0, yanchor: "bottom", yref: "paper"
            }));
            ann.push({ showarrow: false, text: "<b>Promedio escolar del índice ESCS (estatus socioeconómico y cultural)</b>",
                       x: 0.5, xanchor: "center", xref: "paper", y: -0.14, yref: "paper", font: { size: 12 } });
            return {
                template: "plotly_white",
                height: 520, margin: { t: 50, b: 70, l: 70, r: 20 },
                annotations: ann,
                xaxis: { domain: [0.0, 0.32], title: { text: "" }, range: [-2.6, 1.6], autorange: false },
                yaxis: { domain: [0.0, 1.0], title: { text: "<b>Puntaje promedio PISA</b>", font: { size: 12 } }, range: [250, 615], autorange: false },
                xaxis2: { domain: [0.34, 0.66], matches: "x", title: { text: "" }, range: [-2.6, 1.6], autorange: false },
                yaxis2: { matches: "y", showticklabels: false, range: [250, 615], autorange: false },
                xaxis3: { domain: [0.68, 1.0], matches: "x", title: { text: "" }, range: [-2.6, 1.6], autorange: false },
                yaxis3: { matches: "y", showticklabels: false, range: [250, 615], autorange: false },
                showlegend: false, hovermode: "closest"
            };
        }

        // ---- Evolución ----
        function hexToRgba(hex, a) {
            const n = parseInt(hex.slice(1), 16);
            return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
        }
        function sectorKey() {
            return (state.sectors["Pública"] && state.sectors["Privada"]) ? "all"
                 : (state.sectors["Pública"] ? "Pública" : "Privada");
        }
        function estCell(year, region, subject) {
            const EST = DB.est || {};
            const sk = sectorKey();
            const y = EST[String(year)];
            const cell = y && y[region] && y[region][sk] && y[region][sk][subject];
            return cell || null;
        }
        function seFor(year, region, subject) {
            const c = estCell(year, region, subject);
            return c ? c.se : null;
        }
        // ---- Evolución: una línea por región seleccionada y por materia ----
        function buildEvoTraces() {
            const agg = {};
            for (const y of DB.years) agg[y] = {};
            for (const s of DB.schools) {
                if (s[3] && !state.sectors[s[3]]) continue;
                for (const k of schoolRegions(s)) {
                    if (!state.regions[k]) continue;
                    const y = s[0];
                    if (!agg[y][k]) agg[y][k] = SUBJECTS.map(() => ({ sum: 0, w: 0 }));
                    for (let si = 0; si < SUBJECTS.length; si++) {
                        const v = s[7 + si];
                        if (v === null) continue;
                        const w = (s[14] !== null && s[14] > 0) ? s[14] : s[4];
                        agg[y][k][si].sum += v * w;
                        agg[y][k][si].w += w;
                    }
                }
            }
            // Referencia nacional: promedio general de Argentina con IC 95 %
            // (misma metodologia BRR/Fay + Rubin que las regiones). Gris.
            // Segun la gestion seleccionada: total, publica o privada.
            const refback = [];
            const refTop = [];
            for (let si = 0; si < SUBJECTS.length; si++) {
                const key = SUBJECTS[si].key;
                const xs = [], up = [], lo = [], mid = [];
                for (const y of DB.years) {
                    const cell = estCell(y, "Argentina", key);
                    if (cell) {
                        xs.push(y); mid.push(cell.mean);
                        up.push(cell.mean + 1.96 * cell.se);
                        lo.push(cell.mean - 1.96 * cell.se);
                    } else { xs.push(y); mid.push(null); up.push(null); lo.push(null); }
                }
                if (mid.every(v => v === null)) continue;
                if (up.some(v => v !== null)) {
                    refback.push({
                        type: "scatter", mode: "lines", name: "Argentina IC+", showlegend: false,
                        hoverinfo: "skip", x: xs, y: up, connectgaps: false,
                        xaxis: EVO_AXES[si], yaxis: EVO_Y[si], line: { width: 0 }
                    });
                    refback.push({
                        type: "scatter", mode: "lines", name: "Argentina IC-", showlegend: false,
                        hoverinfo: "skip", x: xs, y: lo, connectgaps: false,
                        xaxis: EVO_AXES[si], yaxis: EVO_Y[si], line: { width: 0 },
                        fill: "tonexty", fillcolor: "rgba(128,128,128,0.2)"
                    });
                }
                refTop.push({
                    type: "scatter", mode: "lines", name: "Argentina out", showlegend: false, hoverinfo: "skip",
                    x: xs, y: mid, connectgaps: false, xaxis: EVO_AXES[si], yaxis: EVO_Y[si],
                            line: { color: "white", width: 4.15 }
                });
                refTop.push({
                    type: "scatter", mode: "lines+markers", name: "Promedio Argentina", showlegend: false,
                    x: xs, y: mid, xaxis: EVO_AXES[si], yaxis: EVO_Y[si],
                    line: { color: "rgba(70,70,70,0.95)", width: 2.2 },
                    marker: { color: "rgba(70,70,70,0.95)", size: 6, line: { color: "white", width: 1.1 } },
                    hovertemplate: "Argentina · " + SUBJECTS[si].label + " %{x}: %{y:.1f}<extra></extra>"
                });
            }
            const cibands = [];
            const traces = [];
            for (let si = 0; si < SUBJECTS.length; si++) {
                for (const reg of REGIONS) {
                    if (!state.regions[reg.key]) continue;
                    const xs = [], ys = [], up = [], lo = [];
                    for (const y of DB.years) {
                        const cell = agg[y][reg.key] && agg[y][reg.key][si];
                        const v = cell && cell.w > 0 ? cell.sum / cell.w : null;
                        xs.push(y); ys.push(v);
                        const se = v === null ? null : seFor(y, reg.key, SUBJECTS[si].key);
                        up.push(se === null ? null : v + 1.96 * se);
                        lo.push(se === null ? null : v - 1.96 * se);
                    }
                    const idxs = [];
                    for (let i = 0; i < ys.length; i++) if (ys[i] !== null) idxs.push(i);
                    if (!idxs.length) continue;
                    const color = REGION_COLOR[reg.key];
                    // banda de IC 95% (error de replicacion BRR/Fay + Rubin)
                    if (up.some(v => v !== null)) {
                        cibands.push({
                            type: "scatter", mode: "lines", name: reg.key, showlegend: false, hoverinfo: "skip",
                            x: xs, y: up, connectgaps: false, line: { width: 0 },
                            xaxis: EVO_AXES[si], yaxis: EVO_Y[si]
                        });
                        cibands.push({
                            type: "scatter", mode: "lines", name: reg.key, showlegend: false, hoverinfo: "skip",
                            x: xs, y: lo, connectgaps: false, line: { width: 0 },
                            fill: "tonexty", fillcolor: hexToRgba(color, 0.15),
                            xaxis: EVO_AXES[si], yaxis: EVO_Y[si]
                        });
                    }
                    const hover = reg.key + " · " + SUBJECTS[si].label + " %{x}: %{y:.1f}<extra></extra>";
                    // tramos continuos (sólidos) y tramos que cruzan años faltantes (punteados)
                    const solidX = [], solidY = [], dashX = [], dashY = [];
                    for (let k = 0; k < idxs.length - 1; k++) {
                        const a = idxs[k], b = idxs[k + 1];
                        const tx = (b === a + 1) ? solidX : dashX;
                        const ty = (b === a + 1) ? solidY : dashY;
                        tx.push(xs[a], xs[b], null);
                        ty.push(ys[a], ys[b], null);
                    }
                    if (solidX.length) {
                        traces.push({
                            type: "scatter", mode: "lines", name: reg.key, showlegend: false,
                            hoverinfo: "skip", x: solidX, y: solidY, connectgaps: false,
                            xaxis: EVO_AXES[si], yaxis: EVO_Y[si],
                            line: { color: "white", width: 3.85 }
                        });
                        traces.push({
                            type: "scatter", mode: "lines", name: reg.key, showlegend: false,
                            hoverinfo: "skip", x: solidX, y: solidY, connectgaps: false,
                            xaxis: EVO_AXES[si], yaxis: EVO_Y[si],
                            line: { color: color, width: 2.2 }
                        });
                    }
                    if (dashX.length) {
                        traces.push({
                            type: "scatter", mode: "lines", name: reg.key, showlegend: false,
                            hoverinfo: "skip", x: dashX, y: dashY, connectgaps: false,
                            xaxis: EVO_AXES[si], yaxis: EVO_Y[si],
                            line: { color: "white", width: 3.65, dash: "dash" }
                        });
                        traces.push({
                            type: "scatter", mode: "lines", name: reg.key, showlegend: false,
                            hoverinfo: "skip", x: dashX, y: dashY, connectgaps: false,
                            xaxis: EVO_AXES[si], yaxis: EVO_Y[si],
                            line: { color: color, width: 2, dash: "dash" }
                        });
                    }
                    // puntos
                    traces.push({
                        type: "scatter", mode: "markers", name: reg.key,
                        showlegend: false, x: xs, y: ys,
                        xaxis: EVO_AXES[si], yaxis: EVO_Y[si],
                        marker: { size: 6, color: color, line: { color: "white", width: 1.1 } }, hovertemplate: hover
                    });
                }
            }
            return refback.concat(cibands, traces, refTop);
        }

        function evoLayout(yRange) {
            const ann = SUBJECTS.map((s, i) => ({
                showarrow: false, text: s.label, x: [0.16, 0.5, 0.84][i], xanchor: "center",
                xref: "paper", y: 1.0, yanchor: "bottom", yref: "paper"
            }));
            ann.push({ showarrow: false, text: "<b>Año</b>", x: 0.5, xanchor: "center", xref: "paper", y: -0.18, yref: "paper", font: { size: 12 } });
            const tickvals = DB.years;
            const xr = [Math.min(...tickvals) - 1, Math.max(...tickvals) + 1];
            return {
                template: "plotly_white", height: 420, margin: { t: 40, b: 70, l: 70, r: 20 },
                annotations: ann, showlegend: false, hovermode: "closest",
                xaxis: { domain: [0.0, 0.32], tickvals, range: xr, title: { text: "" } },
                yaxis: { domain: [0.0, 1.0], range: yRange, autorange: false, title: { text: "<b>Puntaje promedio PISA</b>", font: { size: 12 } } },
                xaxis2: { domain: [0.34, 0.66], matches: "x", tickvals, title: { text: "" } },
                yaxis2: { matches: "y", showticklabels: false },
                xaxis3: { domain: [0.68, 1.0], matches: "x", tickvals, title: { text: "" } },
                yaxis3: { matches: "y", showticklabels: false }
            };
        }

        const scatterDiv = document.getElementById("__DIV_ID__");
        const evoDiv = document.getElementById("__EVO_ID__");
        const PLOTLY_CONFIG = { responsive: true, displayModeBar: false, displaylogo: false };

        function redrawScatter() {
            Plotly.react(scatterDiv, buildScatterTraces().concat(trendTraces()), scatterLayout(), PLOTLY_CONFIG);
            document.getElementById("pisa-year-label").textContent = state.year;
        }
        function redrawEvo() {
            const traces = buildEvoTraces();
            Plotly.react(evoDiv, traces, evoLayout(DB.evoRange || [320, 460]), PLOTLY_CONFIG);
            document.getElementById("pisa-year-label").textContent = state.year;
        }

        function wire() {
            document.querySelectorAll(".pisa-year").forEach(btn => btn.addEventListener("click", function () {
                state.year = parseInt(this.getAttribute("data-year"), 10);
                document.querySelectorAll(".pisa-year").forEach(b => b.setAttribute("aria-pressed", "false"));
                this.setAttribute("aria-pressed", "true");
                redrawScatter(); redrawEvo();
            }));
            document.querySelectorAll("[data-region]").forEach(btn => btn.addEventListener("click", function () {
                const k = this.getAttribute("data-region");
                state.regions[k] = !state.regions[k];
                this.setAttribute("aria-pressed", state.regions[k] ? "true" : "false");
                redrawScatter(); redrawEvo();
            }));
            document.querySelectorAll("[data-sector]").forEach(btn => btn.addEventListener("click", function () {
                const k = this.getAttribute("data-sector");
                state.sectors[k] = !state.sectors[k];
                this.setAttribute("aria-pressed", state.sectors[k] ? "true" : "false");
                redrawScatter(); redrawEvo();
            }));
            document.querySelectorAll("[data-trend]").forEach(btn => btn.addEventListener("click", function () {
                const k = this.getAttribute("data-trend");
                state.trends[k] = !state.trends[k];
                this.setAttribute("aria-pressed", state.trends[k] ? "true" : "false");
                redrawScatter();
            }));
            document.getElementById("pisa-reset").addEventListener("click", function () {
                state.regions = Object.fromEntries(REGIONS.map(r => [r.key, true]));
                state.sectors = { "Pública": true, "Privada": true };
                state.trends = { arg: true, oecd: false, sel: false };
                document.querySelectorAll("#pisa-controls [data-region],#pisa-controls [data-sector]").forEach(b => b.setAttribute("aria-pressed", "true"));
                document.querySelectorAll("#pisa-controls [data-trend]").forEach(b => b.setAttribute("aria-pressed", b.getAttribute("data-trend") === "arg" ? "true" : "false"));
                redrawScatter(); redrawEvo();
            });
        }

        function init() {
            wire();
            redrawScatter();
            redrawEvo();
        }
        if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
        else init();
    })();
    </script>
</body>
</html>
"""


def main() -> int:
    db = load_data()
    html = build_html(db)
    for name in ["index.html", "pisa2025_arg_school_dotplot.html"]:
        with open(os.path.join(ROOT, name), "w", encoding="utf-8") as fh:
            fh.write(html)
    print(f"OK index.html y pisa2025_arg_school_dotplot.html generados "
          f"({len(html)/1024:.0f} KB, {len(db['schools'])} escuelas, años {db['years']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
