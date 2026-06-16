import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from datetime import datetime, timezone
from io import BytesIO
import pandas as pd
from flask import Flask, request, jsonify, render_template_string

try:
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

from compiler.lexer import tokenizar, tokenizar_nombre_variable, ErrorLexico
from compiler.parser import parsear_valor, validar_tipo_registro, validar_nombre_variable, ErrorSintactico
from compiler.semantic import TablaSimbolos, ErrorSemantico

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB  = os.environ.get("MONGODB_DB", "compilador_usil")
MONGODB_COL = os.environ.get("MONGODB_COL", "compilaciones")
COLUMNAS_REQUERIDAS = {"Tipo_Registro", "Nombre_Variable", "Valor_Asignacion"}

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Minicompilador de Inventario</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f6fa;color:#1a1a2e;font-size:14px;line-height:1.6}

/* ── NAV ── */
nav{background:#fff;border-bottom:1px solid #e8eaf0;padding:0 32px;display:flex;align-items:center;height:56px;position:sticky;top:0;z-index:100}
.nav-brand{font-weight:700;font-size:15px;color:#1a1a2e;margin-right:12px}
.nav-badge{background:#eef2ff;color:#3730a3;font-size:11px;font-weight:600;padding:2px 10px;border-radius:20px;margin-right:auto}
.nav-links{display:flex;gap:4px}
.nav-link{padding:6px 16px;border-radius:6px;font-size:13px;font-weight:500;color:#6b7280;cursor:pointer;border:none;background:none;text-decoration:none}
.nav-link.active{color:#2563eb;border-bottom:2px solid #2563eb;border-radius:0}
.nav-link:hover{color:#1a1a2e}
.nav-icon{width:32px;height:32px;border-radius:8px;background:#f3f4f6;border:1px solid #e5e7eb;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:16px;margin-left:8px}

/* ── PAGES ── */
.page{display:none;padding:28px 32px;max-width:1100px;margin:0 auto}
.page.active{display:block}

/* ── CARDS ── */
.card{background:#fff;border:1px solid #e8eaf0;border-radius:12px;padding:24px;margin-bottom:20px}
.card-sm{background:#fff;border:1px solid #e8eaf0;border-radius:10px;padding:16px}

/* ── SECTION HEADER ── */
.sec-head{display:flex;align-items:center;gap:10px;margin-bottom:18px}
.sec-num{width:28px;height:28px;background:#2563eb;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0}
.sec-title{font-size:17px;font-weight:700;color:#1a1a2e}

/* ── DESCRIPTION ── */
.desc-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.desc-block{border-left:3px solid #2563eb;padding:12px 14px;background:#f8faff;border-radius:0 8px 8px 0}
.desc-block.green{border-color:#059669}
.desc-label{font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px}
.desc-text{font-size:12px;color:#374151}
.pipeline{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:4px}
.pipe-step{display:flex;align-items:center;gap:5px;background:#eef2ff;color:#3730a3;padding:5px 12px;border-radius:6px;font-size:12px;font-weight:600}
.pipe-step.green{background:#ecfdf5;color:#065f46}
.pipe-arrow{color:#9ca3af;font-size:14px}

/* ── UPLOAD ── */
.upload-zone{border:2px dashed #c7d2fe;border-radius:12px;padding:40px 20px;text-align:center;cursor:pointer;background:#fafbff;transition:all .2s}
.upload-zone:hover,.upload-zone.drag{background:#eef2ff;border-color:#6366f1}
.upload-zone.selected{background:#ecfdf5;border-color:#059669}
.upload-icon{font-size:36px;margin-bottom:8px}
.upload-zone h3{font-size:14px;font-weight:600;color:#4338ca;margin-bottom:4px}
.upload-zone.selected h3{color:#065f46}
.upload-zone p{font-size:12px;color:#9ca3af}
#fileInput{display:none}

/* progress bar */
.prog-wrap{margin-top:14px;display:none}
.prog-bar{height:4px;background:#e5e7eb;border-radius:2px;overflow:hidden;margin-bottom:8px}
.prog-fill{height:100%;background:#2563eb;border-radius:2px;transition:width .5s ease}
.prog-steps{display:flex;gap:6px}
.ps{padding:3px 12px;border-radius:20px;border:1px solid #e5e7eb;font-size:11px;font-weight:600;color:#9ca3af}
.ps.active{background:#eef2ff;border-color:#6366f1;color:#3730a3}
.ps.done{background:#ecfdf5;border-color:#6ee7b7;color:#065f46}
.ps.error{background:#fef2f2;border-color:#fca5a5;color:#b91c1c}

.btn-compile{width:100%;margin-top:14px;padding:12px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:background .2s;display:flex;align-items:center;justify-content:center;gap:8px}
.btn-compile:hover{background:#1d4ed8}
.btn-compile:disabled{background:#9ca3af;cursor:not-allowed}
.spinner{width:18px;height:18px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite;display:none}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── ANALYSIS GRID ── */
.analysis-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
@media(max-width:860px){.analysis-grid{grid-template-columns:1fr}}
.a-card{border:1px solid #e8eaf0;border-radius:10px;padding:16px;background:#fff}
.a-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #f3f4f6}
.a-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#374151}
.a-badge{font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px}
.badge-live{background:#dcfce7;color:#15803d}
.badge-cfg{background:#dbeafe;color:#1e40af}
.badge-out{background:#fef3c7;color:#92400e}

/* tokens */
.tok{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:monospace;margin:2px}
.tok-kw{background:#ede9fe;color:#5b21b6}
.tok-id{background:#dbeafe;color:#1e40af}
.tok-num{background:#dcfce7;color:#166534}
.tok-op{background:#fef3c7;color:#92400e}
.tok-par{background:#fce7f3;color:#9d174d}
#tokens-live{min-height:28px;display:flex;flex-wrap:wrap;gap:2px}
.live-placeholder{font-size:11px;color:#9ca3af;font-style:italic}

/* tabla análisis */
table.atbl{width:100%;border-collapse:collapse;font-size:11px}
table.atbl th{background:#f8faff;padding:5px 7px;text-align:left;font-weight:600;color:#374151;border-bottom:1px solid #e8eaf0}
table.atbl td{padding:4px 7px;border-bottom:1px solid #f3f4f6;font-family:monospace}

/* AFD */
.afd-wrap{overflow-x:auto;margin:8px 0}
.state-c{cursor:pointer;transition:opacity .15s}
.state-c:hover{opacity:.8}
#state-info{background:#f8faff;border-radius:6px;padding:8px 10px;font-size:11px;color:#4b5563;margin-top:6px;border:1px solid #e8eaf0;min-height:36px}

/* sim */
.sim-wrap{margin-top:10px;border-top:1px solid #f3f4f6;padding-top:10px}
.sim-label{font-size:11px;font-weight:600;color:#374151;margin-bottom:5px}
#sim-input{width:100%;padding:7px 10px;border-radius:6px;border:1px solid #d1d5db;font-family:monospace;font-size:12px;color:#111;background:#fff}
.sim-btns{display:flex;gap:6px;margin-top:5px}
.sim-btns button{padding:5px 14px;border-radius:6px;border:1px solid #d1d5db;background:#f9fafb;cursor:pointer;font-size:12px;color:#374151}
.sim-btns button:first-child{background:#2563eb;color:#fff;border-color:#2563eb}
#sim-chars{margin-top:6px;min-height:24px;display:flex;flex-wrap:wrap;gap:2px}
#sim-chars span{display:inline-block;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:12px;border:1px solid #e5e7eb}
#sim-chars span.cur{background:#ede9fe;border-color:#7c3aed;color:#4f46e5;font-weight:700}
#sim-chars span.done{background:#f3f4f6;color:#9ca3af}
#sim-result{font-size:11px;margin-top:5px;min-height:16px}

/* tabla transiciones */
.trans-wrap{overflow-x:auto;margin-top:6px}
table.trans{border-collapse:collapse;font-size:10px;width:100%}
table.trans th{padding:5px 6px;border:1px solid #e8eaf0;text-align:center;font-weight:600;background:#f8faff}
table.trans td{padding:5px 6px;border:1px solid #e8eaf0;text-align:center;font-family:monospace}
code.st{padding:1px 5px;border-radius:3px;font-size:10px}

/* CFG */
.cfg-box{background:#f8faff;border-radius:8px;padding:14px;font-family:monospace;font-size:11px;line-height:2;color:#1e3a5f;overflow-x:auto;white-space:pre;border:1px solid #e8eaf0}
.cfg-kw{color:#2563eb;font-weight:700}
.cfg-arrow{color:#6366f1}
.cfg-sym{color:#0f766e}

/* instrucciones */
.inst-row{display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #f3f4f6;font-size:11px}
.inst-fila{color:#9ca3af;font-family:monospace;width:28px}
.inst-tipo{font-weight:600;color:#2563eb;width:88px}
.inst-nom{color:#374151;flex:1;font-family:monospace}
.inst-val{color:#059669;font-weight:600;font-family:monospace}

/* semántico */
table.sym-tbl td:first-child{font-weight:600}
.row-ins td:first-child{color:#4f46e5}
.row-cos td:first-child{color:#b45309}
.row-cal td:first-child{color:#059669}
.json-out{background:#1e1e2e;border-radius:8px;padding:12px;font-family:monospace;font-size:11px;color:#cdd6f4;white-space:pre-wrap;min-height:50px;overflow-x:auto;border:1px solid #2a2a3e}
.json-key{color:#89b4fa}
.json-str{color:#a6e3a1}
.json-num{color:#fab387}

/* stats */
.stats-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:8px}
.stat-box{background:#f8faff;border-radius:8px;padding:10px;text-align:center;border:1px solid #e8eaf0}
.stat-label{font-size:10px;color:#9ca3af;font-weight:600;text-transform:uppercase}
.stat-val{font-size:22px;font-weight:700}
.stat-val.ins{color:#4f46e5}
.stat-val.cos{color:#b45309}
.stat-val.cal{color:#059669}

/* sync btn */
.btn-sync{width:100%;margin-top:10px;padding:9px;background:#f8faff;border:1px solid #e8eaf0;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;color:#374151;display:flex;align-items:center;justify-content:center;gap:6px}
.btn-sync:hover{background:#eef2ff;border-color:#6366f1;color:#3730a3}
.sync-dot{width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block}

/* ── RESULTS PAGE ── */
.results-header{border-left:4px solid #2563eb;padding:8px 0 8px 16px;margin-bottom:24px}
.results-header h2{font-size:22px;font-weight:700;color:#1a1a2e}
.results-header p{font-size:13px;color:#6b7280;margin-top:3px}
.results-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:700px){.results-grid{grid-template-columns:1fr}}

/* CFG panel results */
.cfg-panel{background:#fff;border:1px solid #e8eaf0;border-radius:12px;padding:20px}
.panel-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.panel-title{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700;color:#1a1a2e}
.panel-badge{font-size:10px;font-weight:700;padding:3px 10px;border-radius:4px;background:#f3f4f6;color:#6b7280;letter-spacing:.5px}
.cfg-full{background:#f8faff;border:1px solid #e8eaf0;border-radius:8px;padding:16px;font-family:monospace;font-size:12px;line-height:2.1;color:#1e3a5f;overflow-x:auto;white-space:pre}

/* AST visual */
.ast-panel{background:#fff;border:1px solid #e8eaf0;border-radius:12px;padding:20px;margin-top:0}
.ast-controls{display:flex;gap:6px}
.ast-btn{padding:5px 10px;border-radius:6px;border:1px solid #e5e7eb;background:#f9fafb;cursor:pointer;font-size:12px}
#ast-canvas-wrap{background:#f8faff;border:1px solid #e8eaf0;border-radius:8px;overflow:auto;min-height:200px;position:relative;margin-top:10px}
#ast-canvas{display:block;margin:0 auto}

/* JSON panel results */
.json-panel{background:#1e1e2e;border-radius:12px;padding:20px;border:1px solid #2a2a3e}
.json-panel-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.json-panel-title{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:700;color:#cdd6f4}
.btn-export{background:#2563eb;color:#fff;border:none;border-radius:6px;padding:5px 14px;font-size:12px;font-weight:600;cursor:pointer}
.json-out-full{font-family:monospace;font-size:12px;color:#cdd6f4;white-space:pre-wrap;overflow-x:auto;line-height:1.7;max-height:300px;overflow-y:auto}

/* metrics */
.metrics-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.metric-card{background:#fff;border:1px solid #e8eaf0;border-radius:10px;padding:16px}
.metric-label{font-size:12px;color:#6b7280;margin-bottom:6px}
.metric-val{font-size:28px;font-weight:700;color:#2563eb}
.metric-bar{height:3px;background:#2563eb;border-radius:2px;margin-top:8px}

/* dist */
.dist-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.dist-label{font-size:12px;color:#374151;width:70px}
.dist-bar-wrap{flex:1;height:8px;background:#f3f4f6;border-radius:4px;overflow:hidden}
.dist-bar{height:100%;border-radius:4px;transition:width .8s ease}
.dist-pct{font-size:12px;font-weight:600;color:#374151;width:35px;text-align:right}

/* validation */
.val-row{display:flex;align-items:center;justify-content:space-between;padding:12px;border:1px solid #e8eaf0;border-radius:8px;margin-top:12px}
.val-ok{display:flex;align-items:center;gap:8px}
.val-dot{width:10px;height:10px;border-radius:50%;background:#22c55e}
.val-text h4{font-size:13px;font-weight:700;color:#15803d}
.val-text p{font-size:11px;color:#6b7280}
.val-icon{font-size:18px;cursor:pointer;color:#9ca3af}

/* error panel */
.err-panel{background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:16px}
.err-panel h3{color:#b91c1c;font-size:14px;margin-bottom:6px}
.err-fase{display:inline-block;background:#fee2e2;color:#b91c1c;border-radius:4px;padding:2px 8px;font-size:10px;font-weight:700;text-transform:uppercase;margin-right:6px}

/* result cards */
.res-cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:14px}
.res-card{background:#fff;border:1px solid #e8eaf0;border-radius:8px;padding:12px 14px}
.res-label{font-size:10px;color:#9ca3af;font-weight:600;text-transform:uppercase}
.res-val{font-size:18px;font-weight:700;color:#2563eb;margin-top:2px}

footer{background:#fff;border-top:1px solid #e8eaf0;padding:20px 32px;display:flex;align-items:center;justify-content:space-between;margin-top:32px}
.footer-brand{font-weight:700;color:#2563eb;font-size:13px}
.footer-sub{font-size:11px;color:#9ca3af;margin-top:2px}
.footer-links{display:flex;gap:20px}
.footer-links a{font-size:12px;color:#6b7280;text-decoration:none}
.footer-links a:hover{color:#2563eb}
</style>
</head>
<body>

<!-- NAV -->
<nav>
  <span class="nav-brand">Minicompilador de Inventario</span>
  <span class="nav-badge">USIL 2026</span>
  <div class="nav-links">
    <a class="nav-link active" id="nav-compiler" onclick="showPage('compiler')">Compiler</a>
    <a class="nav-link" id="nav-results" onclick="showPage('results')">Resultados</a>
    <a class="nav-link" id="nav-docs" onclick="showPage('docs')">Documentación</a>
  </div>
  <div class="nav-icon" title="Configuración">⚙</div>
</nav>

<!-- ══════════ PAGE: COMPILER ══════════ -->
<div class="page active" id="page-compiler">

  <!-- 1. Descripción -->
  <div class="card">
    <div class="sec-head">
      <div class="sec-num">1</div>
      <h2 class="sec-title">Descripción del compilador</h2>
    </div>
    <div class="desc-grid">
      <div class="desc-block">
        <div class="desc-label">Proceso de entrada</div>
        <div class="desc-text">El personal sube un Excel/CSV con columnas <code>Tipo_Registro</code>, <code>Nombre_Variable</code>, <code>Valor_Asignacion</code>. Cada fila es una instrucción de asignación.</div>
      </div>
      <div class="desc-block green">
        <div class="desc-label">Resultado generado</div>
        <div class="desc-text">Si el archivo es 100% válido → JSON con Tabla de Símbolos resuelta → MongoDB Atlas. Si hay error → fila y fase exacta del análisis.</div>
      </div>
    </div>
    <div class="pipeline">
      <div class="pipe-step">📄 Excel / CSV</div><span class="pipe-arrow">→</span>
      <div class="pipe-step">🔤 Léxico</div><span class="pipe-arrow">→</span>
      <div class="pipe-step">📐 Sintáctico</div><span class="pipe-arrow">→</span>
      <div class="pipe-step">🧠 Semántico</div><span class="pipe-arrow">→</span>
      <div class="pipe-step green">🍃 MongoDB Atlas</div>
    </div>
  </div>

  <!-- 2. Upload -->
  <div class="card">
    <div class="sec-head">
      <div class="sec-num">2</div>
      <h2 class="sec-title">Ingreso de datos — cargar archivo</h2>
    </div>
    <div class="upload-zone" id="uploadZone" onclick="document.getElementById('fileInput').click()"
         ondragover="doDrag(event,true)" ondragleave="doDrag(event,false)" ondrop="doDrop(event)">
      <div class="upload-icon">☁️</div>
      <h3>Haz clic o arrastra tu archivo aquí</h3>
      <p>Formatos: .xlsx · .xls · .csv — máximo 10 MB</p>
      <input type="file" id="fileInput" accept=".xlsx,.xls,.csv" onchange="pickFile(this.files[0])">
    </div>
    <div class="prog-wrap" id="progWrap">
      <div class="prog-bar"><div class="prog-fill" id="progFill" style="width:0%"></div></div>
      <div class="prog-steps">
        <span class="ps" id="ps-lex">Léxico</span>
        <span class="ps" id="ps-sin">Sintáctico</span>
        <span class="ps" id="ps-sem">Semántico</span>
        <span class="ps" id="ps-db">MongoDB</span>
      </div>
    </div>
    <button class="btn-compile" id="btnC" disabled onclick="compilar()">
      <span id="btnT">Selecciona un archivo para compilar</span>
      <div class="spinner" id="sp"></div>
    </button>
  </div>

  <!-- 3. Proceso interno -->
  <div class="card">
    <div class="sec-head">
      <div class="sec-num">3</div>
      <h2 class="sec-title">Proceso interno del compilador</h2>
    </div>
    <div class="analysis-grid">

      <!-- 3.1 LÉXICO -->
      <div class="a-card">
        <div class="a-head">
          <span class="a-title">3.1 Análisis Léxico</span>
          <span class="a-badge badge-live">LIVE</span>
        </div>
        <p style="font-size:11px;color:#6b7280;margin-bottom:5px">Tokens detectados</p>
        <div id="tokens-live"><span class="live-placeholder">Carga un archivo…</span></div>

        <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 5px">AFD — Autómata Finito Determinista</p>
        <div class="afd-wrap">
          <svg width="100%" viewBox="0 0 420 280" role="img">
            <title>AFD Lexer</title>
            <defs>
              <marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </marker>
            </defs>
            <line x1="20" y1="138" x2="48" y2="138" stroke="#9ca3af" stroke-width="1.5" marker-end="url(#ar)" fill="none"/>
            <polygon points="14,134 14,142 6,138" fill="#9ca3af"/>
            <!-- q0 -->
            <g class="state-c" onclick="qs('q0')">
              <circle cx="74" cy="138" r="24" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
              <circle cx="74" cy="138" r="18" fill="none" stroke="#2563eb" stroke-width="1" stroke-dasharray="3 2"/>
              <text x="74" y="138" text-anchor="middle" dominant-baseline="central" style="font-size:12px;font-weight:700;fill:#1e40af">q0</text>
            </g>
            <!-- q1 -->
            <g class="state-c" onclick="qs('q1')">
              <circle cx="200" cy="60" r="24" fill="#dcfce7" stroke="#15803d" stroke-width="1.5"/>
              <text x="200" y="60" text-anchor="middle" dominant-baseline="central" style="font-size:12px;font-weight:700;fill:#15803d">q1</text>
            </g>
            <text x="200" y="92" text-anchor="middle" style="font-size:9px;fill:#6b7280">ident/kw</text>
            <!-- q2 -->
            <g class="state-c" onclick="qs('q2')">
              <circle cx="200" cy="145" r="24" fill="#ede9fe" stroke="#7c3aed" stroke-width="1.5"/>
              <text x="200" y="145" text-anchor="middle" dominant-baseline="central" style="font-size:12px;font-weight:700;fill:#5b21b6">q2</text>
            </g>
            <text x="200" y="177" text-anchor="middle" style="font-size:9px;fill:#6b7280">int</text>
            <!-- q3 -->
            <g class="state-c" onclick="qs('q3')">
              <circle cx="200" cy="225" r="24" fill="#ede9fe" stroke="#7c3aed" stroke-width="1.5"/>
              <text x="200" y="225" text-anchor="middle" dominant-baseline="central" style="font-size:12px;font-weight:700;fill:#5b21b6">q3</text>
            </g>
            <text x="200" y="257" text-anchor="middle" style="font-size:9px;fill:#6b7280">float</text>
            <!-- q4 op -->
            <g class="state-c" onclick="qs('q4')">
              <circle cx="340" cy="80" r="24" fill="#fef3c7" stroke="#d97706" stroke-width="1.5"/>
              <circle cx="340" cy="80" r="18" fill="none" stroke="#d97706" stroke-width="1"/>
              <text x="340" y="80" text-anchor="middle" dominant-baseline="central" style="font-size:12px;font-weight:700;fill:#92400e">q4</text>
            </g>
            <text x="340" y="112" text-anchor="middle" style="font-size:9px;fill:#6b7280">op ✓</text>
            <!-- q5 accept -->
            <g class="state-c" onclick="qs('q5')">
              <circle cx="340" cy="190" r="24" fill="#dcfce7" stroke="#15803d" stroke-width="1.5"/>
              <circle cx="340" cy="190" r="18" fill="none" stroke="#15803d" stroke-width="1"/>
              <text x="340" y="190" text-anchor="middle" dominant-baseline="central" style="font-size:12px;font-weight:700;fill:#15803d">q5</text>
            </g>
            <text x="340" y="222" text-anchor="middle" style="font-size:9px;fill:#6b7280">token ✓</text>
            <!-- qERR -->
            <g class="state-c" onclick="qs('qe')">
              <circle cx="74" cy="240" r="20" fill="#fef2f2" stroke="#dc2626" stroke-width="1.5"/>
              <text x="74" y="240" text-anchor="middle" dominant-baseline="central" style="font-size:9px;font-weight:700;fill:#b91c1c">qERR</text>
            </g>
            <!-- arrows -->
            <path d="M94 126 Q144 88 176 68" fill="none" stroke="#15803d" stroke-width="1.2" marker-end="url(#ar)" opacity=".8"/>
            <text x="127" y="82" style="font-size:9px;fill:#15803d">letra/_</text>
            <line x1="98" y1="138" x2="176" y2="143" fill="none" stroke="#7c3aed" stroke-width="1.2" marker-end="url(#ar)" opacity=".8"/>
            <text x="136" y="133" style="font-size:9px;fill:#7c3aed">dígito</text>
            <path d="M90 150 Q130 200 176 220" fill="none" stroke="#7c3aed" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
            <path d="M92 124 Q200 50 316 74" fill="none" stroke="#d97706" stroke-width="1.2" marker-end="url(#ar)" opacity=".8"/>
            <text x="204" y="46" style="font-size:9px;fill:#d97706">+−*/( )</text>
            <line x1="74" y1="162" x2="74" y2="220" fill="none" stroke="#dc2626" stroke-width="1.2" marker-end="url(#ar)" opacity=".7" stroke-dasharray="3 2"/>
            <text x="58" y="196" style="font-size:9px;fill:#dc2626">otro</text>
            <path d="M188 36 Q196 16 210 28 Q220 40 212 54" fill="none" stroke="#15803d" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
            <text x="218" y="18" style="font-size:9px;fill:#15803d">letra/díg/_</text>
            <path d="M188 122 Q196 106 210 114 Q218 124 210 136" fill="none" stroke="#7c3aed" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
            <path d="M188 204 Q196 190 210 196 Q218 206 210 218" fill="none" stroke="#7c3aed" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
            <line x1="200" y1="169" x2="200" y2="201" fill="none" stroke="#7c3aed" stroke-width="1.2" marker-end="url(#ar)" opacity=".8"/>
            <text x="210" y="187" style="font-size:9px;fill:#7c3aed">.</text>
            <path d="M224 64 Q282 100 316 176" fill="none" stroke="#15803d" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
            <text x="290" y="110" style="font-size:9px;fill:#15803d">otro</text>
            <line x1="224" y1="148" x2="316" y2="185" fill="none" stroke="#7c3aed" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
            <path d="M224 224 Q278 224 316 198" fill="none" stroke="#7c3aed" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
          </svg>
        </div>
        <div id="state-info">Haz clic en un estado para ver su descripción.</div>

        <!-- simulador -->
        <div class="sim-wrap">
          <div class="sim-label">Simulador de cadena</div>
          <input id="sim-input" placeholder="Ej: hilos_lana  |  3.50  |  +">
          <div class="sim-btns">
            <button onclick="simular()">Simular</button>
            <button onclick="resetSim()">Reset</button>
          </div>
          <div id="sim-chars"></div>
          <div id="sim-result"></div>
        </div>

        <!-- tabla de transiciones -->
        <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">Tabla de Transiciones</p>
        <div class="trans-wrap">
          <table class="trans">
            <thead>
              <tr>
                <th>Estado</th>
                <th style="background:#f0fdf4;color:#15803d">Letra/_</th>
                <th style="background:#f5f3ff;color:#5b21b6">Dígito</th>
                <th style="background:#f5f3ff;color:#5b21b6">Punto</th>
                <th style="background:#fffbeb;color:#92400e">Op</th>
                <th style="background:#f3f4f6">Esp/Fin</th>
                <th style="background:#fef2f2;color:#b91c1c">Otro</th>
              </tr>
            </thead>
            <tbody>
              <tr><td><code class="st" style="background:#dbeafe;color:#1e40af">→q0</code></td><td><code class="st" style="background:#dcfce7;color:#15803d">q1</code></td><td><code class="st" style="background:#ede9fe;color:#5b21b6">q2</code></td><td>—</td><td><code class="st" style="background:#fef3c7;color:#92400e">q4</code></td><td>—</td><td><code class="st" style="background:#fef2f2;color:#b91c1c">qERR</code></td></tr>
              <tr style="background:#f9fafb"><td><code class="st" style="background:#dcfce7;color:#15803d">q1</code></td><td><code class="st" style="background:#dcfce7;color:#15803d">q1↻</code></td><td><code class="st" style="background:#dcfce7;color:#15803d">q1↻</code></td><td>—</td><td><code class="st" style="background:#dcfce7;color:#15803d">q5*</code></td><td><code class="st" style="background:#dcfce7;color:#15803d">q5*</code></td><td><code class="st" style="background:#dcfce7;color:#15803d">q5*</code></td></tr>
              <tr><td><code class="st" style="background:#ede9fe;color:#5b21b6">q2</code></td><td>—</td><td><code class="st" style="background:#ede9fe;color:#5b21b6">q2↻</code></td><td><code class="st" style="background:#ede9fe;color:#5b21b6">q3</code></td><td><code class="st" style="background:#ede9fe;color:#5b21b6">q5*</code></td><td><code class="st" style="background:#ede9fe;color:#5b21b6">q5*</code></td><td><code class="st" style="background:#fef2f2;color:#b91c1c">qERR</code></td></tr>
              <tr style="background:#f9fafb"><td><code class="st" style="background:#ede9fe;color:#5b21b6">q3</code></td><td>—</td><td><code class="st" style="background:#ede9fe;color:#5b21b6">q3↻</code></td><td>—</td><td><code class="st" style="background:#ede9fe;color:#5b21b6">q5*</code></td><td><code class="st" style="background:#ede9fe;color:#5b21b6">q5*</code></td><td><code class="st" style="background:#fef2f2;color:#b91c1c">qERR</code></td></tr>
              <tr><td><code class="st" style="background:#fef3c7;color:#92400e">q4✓</code></td><td colspan="6" style="color:#9ca3af;font-size:10px;font-style:italic">Aceptación inmediata → emite OP/PAREN → vuelve a q0</td></tr>
              <tr style="background:#f9fafb"><td><code class="st" style="background:#dcfce7;color:#15803d">q5✓</code></td><td colspan="6" style="color:#9ca3af;font-size:10px;font-style:italic">Aceptación → emite IDENTIFIER/KW/NUMBER → vuelve a q0</td></tr>
              <tr><td><code class="st" style="background:#fef2f2;color:#b91c1c">qERR</code></td><td colspan="6" style="color:#dc2626;font-size:10px;font-style:italic">Trampa — lanza ErrorLexico con posición exacta</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 3.2 SINTÁCTICO -->
      <div class="a-card">
        <div class="a-head">
          <span class="a-title">3.2 Análisis Sintáctico</span>
          <span class="a-badge badge-cfg">CFG</span>
        </div>
        <p style="font-size:11px;color:#6b7280;margin-bottom:6px">Gramática Libre de Contexto (CFG)</p>
        <div class="cfg-box"><span class="cfg-kw">programa</span>    → instruccion*
<span class="cfg-kw">instruccion</span> → tipo ID = expr
<span class="cfg-kw">tipo</span>        → insumo | costo | calculo

<span class="cfg-kw">expr</span>    <span class="cfg-arrow">→</span> <span class="cfg-sym">term</span> rest_E
<span class="cfg-kw">rest_E</span>  <span class="cfg-arrow">→</span> ('+' | '-') <span class="cfg-sym">term</span> rest_E | ε

<span class="cfg-kw">term</span>    <span class="cfg-arrow">→</span> <span class="cfg-sym">factor</span> rest_T
<span class="cfg-kw">rest_T</span>  <span class="cfg-arrow">→</span> ('*' | '/') <span class="cfg-sym">factor</span> rest_T | ε

<span class="cfg-kw">factor</span>  <span class="cfg-arrow">→</span> NUMBER
        | IDENTIFIER
        | '(' expr ')'</div>

        <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 5px">Árbol Sintáctico (AST en vivo)</p>
        <div id="ast-preview" style="background:#f8faff;border:1px solid #e8eaf0;border-radius:8px;padding:12px;min-height:80px;font-family:monospace;font-size:11px;white-space:pre;overflow-x:auto;color:#374151"><span class="live-placeholder">Carga un archivo para visualizar el AST generado por el parser</span></div>

        <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 5px">Instrucciones Analizadas</p>
        <div id="inst-live" style="min-height:40px"><span class="live-placeholder">Esperando archivo…</span></div>
      </div>

      <!-- 3.3 SEMÁNTICO -->
      <div class="a-card">
        <div class="a-head">
          <span class="a-title">3.3 Semántico · Traducción</span>
          <span class="a-badge badge-out">OUTPUT</span>
        </div>
        <p style="font-size:11px;color:#6b7280;margin-bottom:5px">Tabla de Símbolos (en vivo)</p>
        <div id="sym-live"><span class="live-placeholder">Sin variables registradas</span></div>

        <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 5px">Traducción JSON → MongoDB</p>
        <div class="json-out" id="json-out">{ "status": "waiting_upload" }</div>

        <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">Estadísticas de Compilación</p>
        <div class="stats-grid">
          <div class="stat-box"><div class="stat-label">Insumos</div><div class="stat-val ins" id="cnt-ins">--</div></div>
          <div class="stat-box"><div class="stat-label">Costos</div><div class="stat-val cos" id="cnt-cos">--</div></div>
          <div class="stat-box"><div class="stat-label">Cálculos</div><div class="stat-val cal" id="cnt-cal">--</div></div>
        </div>

        <button class="btn-sync" id="btnSync" onclick="showPage('results')">
          <span class="sync-dot" id="syncDot" style="background:#9ca3af"></span>
          Sincronizar con Atlas
        </button>
      </div>

    </div>
  </div>
</div><!-- /page-compiler -->

<!-- ══════════ PAGE: RESULTS ══════════ -->
<div class="page" id="page-results">
  <div class="results-header">
    <h2>Análisis Post-Compilación</h2>
    <p>Visualización detallada de la estructura gramatical, el árbol de sintaxis abstracta (AST) y la resolución semántica del inventario procesado.</p>
  </div>

  <div id="res-error-panel" style="display:none"></div>
  <div id="res-success" style="display:none">
    <div class="results-grid">
      <!-- izquierda -->
      <div>
        <div class="cfg-panel">
          <div class="panel-head">
            <div class="panel-title">📐 Gramática Libre de Contexto (CFG)</div>
            <span class="panel-badge">FORMAL LOGIC</span>
          </div>
          <div class="cfg-full"><span class="cfg-kw">programa</span>    → instruccion*
<span class="cfg-kw">instruccion</span> → tipo ID = expr
<span class="cfg-kw">tipo</span>        → insumo | costo_empaque | calculo

<span class="cfg-kw">expr</span>    <span class="cfg-arrow">→</span> <span class="cfg-sym">term</span> rest_E
<span class="cfg-kw">rest_E</span>  <span class="cfg-arrow">→</span> ('+' | '-') <span class="cfg-sym">term</span> rest_E | ε

<span class="cfg-kw">term</span>    <span class="cfg-arrow">→</span> <span class="cfg-sym">factor</span> rest_T
<span class="cfg-kw">rest_T</span>  <span class="cfg-arrow">→</span> ('*' | '/') <span class="cfg-sym">factor</span> rest_T | ε

<span class="cfg-kw">factor</span>  <span class="cfg-arrow">→</span> NUMBER | IDENTIFIER | '(' expr ')'</div>
        </div>

        <div class="ast-panel" style="margin-top:16px">
          <div class="panel-head">
            <div class="panel-title">🌿 Árbol de Sintaxis Abstracta (AST)</div>
            <div class="ast-controls">
              <button class="ast-btn" onclick="zoomAST(1.2)">🔍+</button>
              <button class="ast-btn" onclick="zoomAST(0.8)">🔍−</button>
              <button class="ast-btn" onclick="resetZoom()">⛶</button>
            </div>
          </div>
          <div id="ast-canvas-wrap">
            <canvas id="ast-canvas" width="580" height="220"></canvas>
          </div>
        </div>
      </div>

      <!-- derecha -->
      <div>
        <div class="json-panel">
          <div class="json-panel-head">
            <div class="json-panel-title">📤 Traducción JSON (Semántico)</div>
            <button class="btn-export" onclick="exportJSON()">Exportar</button>
          </div>
          <div class="json-out-full" id="json-full">{ }</div>
        </div>

        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">Tokens procesados</div>
            <div class="metric-val" id="m-tokens">0</div>
            <div class="metric-bar"></div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Tiempo estimado</div>
            <div class="metric-val" id="m-tiempo">0ms</div>
            <div class="metric-bar" style="background:#059669"></div>
          </div>
        </div>

        <div class="cfg-panel" style="margin-top:12px">
          <div class="panel-head">
            <div class="panel-title">📊 Distribución de Tipos</div>
            <span style="font-size:16px;cursor:pointer">⊕</span>
          </div>
          <div id="dist-bars"></div>
        </div>

        <div class="val-row" id="val-row" style="display:none">
          <div class="val-ok">
            <div class="val-dot" id="val-dot"></div>
            <div class="val-text">
              <h4 id="val-title">Validación Exitosa</h4>
              <p id="val-sub">Sincronizado con MongoDB Atlas</p>
            </div>
          </div>
          <span class="val-icon" onclick="showPage('compiler')">↺</span>
        </div>
      </div>
    </div>

    <!-- cards resumen -->
    <div class="card" id="res-cards-wrap" style="margin-top:16px;display:none">
      <div class="panel-head" style="margin-bottom:0">
        <div class="panel-title">📦 Valores resueltos</div>
      </div>
      <div class="res-cards-grid" id="res-cards-grid"></div>
    </div>
  </div>
</div><!-- /page-results -->

<!-- ══════════ PAGE: DOCS ══════════ -->
<div class="page" id="page-docs">
  <div class="results-header">
    <h2>Documentación</h2>
    <p>Referencia técnica del minicompilador USIL 2026.</p>
  </div>
  <div class="card">
    <div class="sec-head"><div class="sec-num">📄</div><h2 class="sec-title">Formato del archivo de entrada</h2></div>
    <p style="font-size:13px;color:#374151;margin-bottom:12px">El archivo debe tener exactamente tres columnas en este orden:</p>
    <table class="atbl">
      <tr><th>Columna</th><th>Tipo</th><th>Valores válidos</th><th>Ejemplo</th></tr>
      <tr><td>Tipo_Registro</td><td>Texto</td><td>insumo · costo_empaque · calculo</td><td>insumo</td></tr>
      <tr><td>Nombre_Variable</td><td>Identificador</td><td>[a-zA-Z_][a-zA-Z0-9_]*</td><td>hilos_lana</td></tr>
      <tr><td>Valor_Asignacion</td><td>Número o expresión</td><td>150 · 3.50 · var1 + var2 * 1.2</td><td>hilos_lana + ojos_seguridad</td></tr>
    </table>
  </div>
  <div class="card">
    <div class="sec-head"><div class="sec-num">⚠</div><h2 class="sec-title">Errores y cómo resolverlos</h2></div>
    <table class="atbl">
      <tr><th>Fase</th><th>Causa</th><th>Solución</th></tr>
      <tr><td><span class="tok tok-op">LÉXICO</span></td><td>Carácter inválido ($, @, #) en el valor</td><td>Use solo letras, números, _ y operadores +−*/</td></tr>
      <tr><td><span class="tok tok-id">SINTÁCTICO</span></td><td>Expresión malformada (ej: "150 + " sin operando)</td><td>Verifique que toda expresión tenga operandos completos</td></tr>
      <tr><td><span class="tok tok-kw">SEMÁNTICO</span></td><td>Variable usada en cálculo sin haber sido declarada</td><td>Declare primero como insumo o costo_empaque</td></tr>
    </table>
  </div>
</div>

<!-- FOOTER -->
<footer>
  <div>
    <div class="footer-brand">Inventory Compiler.</div>
    <div class="footer-sub">© 2026 Minicompilador USIL. Utilitarian System Architecture.</div>
  </div>
  <div class="footer-links">
    <a onclick="showPage('docs')">Documentation</a>
    <a onclick="showPage('results')">Process Specs</a>
    <a href="#">Support</a>
  </div>
</footer>

<script>
/* ── NAVEGACIÓN ── */
let currentPage='compiler';
function showPage(p){
  document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(x=>x.classList.remove('active'));
  document.getElementById('page-'+p)?.classList.add('active');
  document.getElementById('nav-'+p)?.classList.add('active');
  currentPage=p;
  if(p==='results') renderResultsPage();
}

/* ── ESTADO GLOBAL ── */
let lastData=null, archivo=null, startTime=0, astZoom=1;

/* ── UPLOAD ── */
function doDrag(e,on){e.preventDefault();document.getElementById('uploadZone').classList.toggle('drag',on)}
function doDrop(e){e.preventDefault();doDrag(e,false);pickFile(e.dataTransfer.files[0])}
function pickFile(f){
  if(!f)return; archivo=f;
  const z=document.getElementById('uploadZone');
  z.className='upload-zone selected';
  z.innerHTML=`<div class="upload-icon">✅</div><h3>${f.name}</h3><p>${(f.size/1024).toFixed(1)} KB · listo para compilar</p>`;
  document.getElementById('btnC').disabled=false;
  document.getElementById('btnT').textContent='⚙️ Compilar archivo';
}

/* ── PROGRESS ── */
function setPhase(ph){
  const order=['ps-lex','ps-sin','ps-sem','ps-db'];
  const pct={lex:25,sin:50,sem:75,db:100};
  const idxMap={lex:0,sin:1,sem:2,db:3};
  const cur=idxMap[ph]??0;
  order.forEach((id,i)=>{
    const el=document.getElementById(id);
    el.className='ps'+(i<cur?' done':i===cur?' active':'');
  });
  document.getElementById('progFill').style.width=(pct[ph]||10)+'%';
}
function setPhaseErr(fase){
  const map={lexico:'ps-lex',sintactico:'ps-sin',semantico:'ps-sem',base_de_datos:'ps-db'};
  const id=map[fase]; if(id) document.getElementById(id).className='ps error';
}

/* ── AFD ESTADOS ── */
const SD={
  q0:{l:'q0 — Inicio',d:'Primer carácter decide el camino: letra→q1, dígito→q2, op→q4, inválido→qERR'},
  q1:{l:'q1 — Identificador/KW',d:'Consume letras, dígitos y _. Al terminar emite IDENTIFIER, KW_INSUMO, KW_CALCULO, etc.'},
  q2:{l:'q2 — Número entero',d:'Consume dígitos. Un punto "." lleva a q3 (float). Otro carácter acepta como NUMBER_INT.'},
  q3:{l:'q3 — Parte decimal',d:'Consume dígitos tras el punto. Al terminar acepta como NUMBER_FLOAT.'},
  q4:{l:'q4 — Operador ✓',d:'Acepta inmediatamente: OP_PLUS, OP_MINUS, OP_MUL, OP_DIV, LPAREN, RPAREN.'},
  q5:{l:'q5 — Aceptación ✓',d:'Token completo emitido. Regresa a q0 para el siguiente token.'},
  qe:{l:'qERR — Error léxico',d:'Carácter inválido ($@#…). Lanza ErrorLexico con posición exacta.'},
};
function qs(id){
  const s=SD[id];if(!s)return;
  document.getElementById('state-info').innerHTML=`<strong style="color:#2563eb">${s.l}</strong><br>${s.d}`;
}

/* ── SIMULADOR ── */
function classify(t){
  const kw=['insumo','costo_empaque','calculo','costo_produccion','total'];
  if(kw.includes(t.toLowerCase()))return{tipo:'KEYWORD',c:'#5b21b6',bg:'#ede9fe'};
  if(/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(t))return{tipo:'IDENTIFIER',c:'#15803d',bg:'#dcfce7'};
  if(/^\d+$/.test(t))return{tipo:'NUMBER_INT',c:'#5b21b6',bg:'#ede9fe'};
  if(/^\d+\.\d+$/.test(t))return{tipo:'NUMBER_FLOAT',c:'#5b21b6',bg:'#ede9fe'};
  if(/^[+\-*\/()]$/.test(t))return{tipo:'OPERADOR',c:'#92400e',bg:'#fef3c7'};
  return{tipo:'ERROR',c:'#b91c1c',bg:'#fef2f2'};
}
function simular(){
  const raw=document.getElementById('sim-input').value.trim();if(!raw)return;
  const chars=raw.split('');
  document.getElementById('sim-chars').innerHTML=chars.map((c,i)=>`<span id="ch${i}">${c===' '?'␣':c}</span>`).join('');
  document.getElementById('sim-result').innerHTML='';
  let i=0;
  (function step(){
    if(i>0)document.getElementById('ch'+(i-1))?.classList.replace('cur','done');
    if(i<chars.length){document.getElementById('ch'+i)?.classList.add('cur');i++;setTimeout(step,180);}
    else{
      const r=classify(raw);
      document.getElementById('sim-result').innerHTML=r.tipo==='ERROR'
        ?`<span style="color:#b91c1c">qERR — carácter inválido: "<b>${raw}</b>"</span>`
        :`<span style="background:${r.bg};color:${r.c};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;font-family:monospace">${r.tipo}</span> → aceptado en q5`;
    }
  })();
}
function resetSim(){
  ['sim-chars','sim-result'].forEach(id=>document.getElementById(id).innerHTML='');
  document.getElementById('sim-input').value='';
  document.getElementById('state-info').textContent='Haz clic en un estado para ver su descripción.';
}

/* ── COMPILAR ── */
async function compilar(){
  if(!archivo)return;
  startTime=Date.now();
  document.getElementById('btnC').disabled=true;
  document.getElementById('btnT').style.display='none';
  document.getElementById('sp').style.display='block';
  document.getElementById('progWrap').style.display='block';
  setPhase('lex');
  setTimeout(()=>setPhase('sin'),350);
  setTimeout(()=>setPhase('sem'),700);
  const fd=new FormData(); fd.append('archivo',archivo);
  try{
    const res=await fetch('/compile',{method:'POST',body:fd});
    const data=await res.json();
    lastData=data;
    if(data.status==='ok'||data.status==='ok_sin_persistencia'){
      setPhase('db'); fillCompilerPanels(data);
    } else {
      setPhaseErr(data.fase||'lexico'); showCompilerError(data);
    }
  }catch(e){
    showCompilerError({status:'error',mensaje:'Error de red: '+e.message});
  }finally{
    document.getElementById('btnC').disabled=false;
    document.getElementById('btnT').style.display='inline';
    document.getElementById('sp').style.display='none';
  }
}

/* ── FILL PANELS (compiler page) ── */
function fillCompilerPanels(data){
  const tabla=data.tabla_de_simbolos||[];
  /* tokens */
  const tm={insumo:'tok-kw',costo_empaque:'tok-op',calculo:'tok-id'};
  document.getElementById('tokens-live').innerHTML=tabla.map(r=>
    `<span class="tok ${tm[r.tipo]||'tok-id'}">${r.tipo.toUpperCase()}</span>`+
    `<span class="tok tok-id">${r.nombre}</span>`+
    `<span class="tok tok-num">${r.valor}</span>`
  ).join('');
  /* AST preview */
  let ast='';
  tabla.forEach(r=>{
    if(r.tipo==='calculo'){
      ast+=`ASIGNACION\n  ├─ ID: ${r.nombre}\n  └─ EXPR: ${r.expresion}\n       └─ eval = ${r.valor}\n\n`;
    }
  });
  document.getElementById('ast-preview').innerHTML=ast||'(sin expresiones de cálculo)';
  /* instrucciones */
  document.getElementById('inst-live').innerHTML=tabla.map(r=>
    `<div class="inst-row"><span class="inst-fila">F${r.fila}</span><span class="inst-tipo">${r.tipo}</span><span class="inst-nom">${r.nombre}</span><span class="inst-val">${r.valor}</span></div>`
  ).join('');
  /* tabla simbolos */
  document.getElementById('sym-live').innerHTML=
    `<table class="atbl sym-tbl">
      <tr><th>Nombre</th><th>Tipo</th><th>Expresión</th><th>Valor</th></tr>
      ${tabla.map(r=>{
        const cls='row-'+(r.tipo==='insumo'?'ins':r.tipo==='costo_empaque'?'cos':'cal');
        return `<tr class="${cls}"><td>${r.nombre}</td><td>${r.tipo}</td><td>${r.expresion}</td><td><b>${r.valor}</b></td></tr>`;
      }).join('')}
    </table>`;
  /* JSON out */
  document.getElementById('json-out').textContent=JSON.stringify(data.resumen||{},null,2);
  /* stats */
  document.getElementById('cnt-ins').textContent=tabla.filter(r=>r.tipo==='insumo').length;
  document.getElementById('cnt-cos').textContent=tabla.filter(r=>r.tipo==='costo_empaque').length;
  document.getElementById('cnt-cal').textContent=tabla.filter(r=>r.tipo==='calculo').length;
  /* sync dot */
  document.getElementById('syncDot').style.background=data.id_documento?'#22c55e':'#f59e0b';
}

function showCompilerError(data){
  document.getElementById('tokens-live').innerHTML=`<span style="color:#b91c1c;font-size:11px">❌ ${data.mensaje||'Error'}</span>`;
}

/* ── RESULTS PAGE ── */
let astZoomFactor=1;
function renderResultsPage(){
  if(!lastData){
    document.getElementById('res-error-panel').style.display='block';
    document.getElementById('res-error-panel').innerHTML='<div class="err-panel"><h3>Sin datos</h3><p>Primero compila un archivo en la sección Compiler.</p></div>';
    document.getElementById('res-success').style.display='none';
    return;
  }
  const data=lastData;
  if(data.status!=='ok'&&data.status!=='ok_sin_persistencia'){
    document.getElementById('res-error-panel').style.display='block';
    document.getElementById('res-error-panel').innerHTML=
      `<div class="err-panel"><h3>❌ Compilación fallida</h3><p><span class="err-fase">${data.fase||''}</span>${data.mensaje||''}</p></div>`;
    document.getElementById('res-success').style.display='none';
    return;
  }
  document.getElementById('res-error-panel').style.display='none';
  document.getElementById('res-success').style.display='block';

  const tabla=data.tabla_de_simbolos||[];
  const elapsed=Date.now()-startTime;

  /* JSON full */
  document.getElementById('json-full').innerHTML=syntaxHL(JSON.stringify({
    status:'SUCCESS',
    timestamp:new Date().toISOString(),
    id:data.id_documento||'sin_persistencia',
    inventory_compilation:tabla.map(r=>({type:r.tipo,id:r.nombre,value:r.valor,expr:r.expresion}))
  },null,2));

  /* metrics */
  document.getElementById('m-tokens').textContent=tabla.length*3;
  document.getElementById('m-tiempo').textContent=elapsed+'ms';

  /* distribución */
  const ins=tabla.filter(r=>r.tipo==='insumo').length;
  const cos=tabla.filter(r=>r.tipo==='costo_empaque').length;
  const cal=tabla.filter(r=>r.tipo==='calculo').length;
  const tot=tabla.length||1;
  document.getElementById('dist-bars').innerHTML=
    distRow('Insumos',ins,tot,'#2563eb')+
    distRow('Costos',cos,tot,'#6b7280')+
    distRow('Cálculos',cal,tot,'#374151');

  /* validación */
  document.getElementById('val-row').style.display='flex';
  if(data.id_documento){
    document.getElementById('val-dot').style.background='#22c55e';
    document.getElementById('val-title').textContent='Validación Exitosa';
    document.getElementById('val-sub').textContent='Sincronizado con MongoDB Atlas · Clúster Prod-01';
  } else {
    document.getElementById('val-dot').style.background='#f59e0b';
    document.getElementById('val-title').textContent='Compilado sin persistencia';
    document.getElementById('val-sub').textContent='Configura MONGODB_URI para sincronizar';
  }

  /* cards resumen */
  const res=data.resumen||{};
  const keys=Object.keys(res);
  if(keys.length){
    document.getElementById('res-cards-wrap').style.display='block';
    document.getElementById('res-cards-grid').innerHTML=keys.map(k=>
      `<div class="res-card"><div class="res-label">${k}</div><div class="res-val">${Number(res[k]).toLocaleString('es-PE',{minimumFractionDigits:2,maximumFractionDigits:2})}</div></div>`
    ).join('');
  }

  /* AST canvas */
  setTimeout(()=>drawAST(tabla),100);
}

function distRow(label,n,tot,color){
  const pct=tot>0?Math.round(n/tot*100):0;
  return `<div class="dist-row">
    <span class="dist-label">${label}</span>
    <div class="dist-bar-wrap"><div class="dist-bar" style="width:${pct}%;background:${color}"></div></div>
    <span class="dist-pct">${pct}%</span>
  </div>`;
}

function syntaxHL(json){
  return json
    .replace(/("[\w]+")\s*:/g,'<span style="color:#89b4fa">$1</span>:')
    .replace(/:\s*(".*?")/g,': <span style="color:#a6e3a1">$1</span>')
    .replace(/:\s*(\d+\.?\d*)/g,': <span style="color:#fab387">$1</span>');
}

/* ── AST CANVAS ── */
function drawAST(tabla){
  const canvas=document.getElementById('ast-canvas');
  const ctx=canvas.getContext('2d');
  const calcRows=tabla.filter(r=>r.tipo==='calculo');
  if(!calcRows.length){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle='#9ca3af'; ctx.font='12px sans-serif'; ctx.textAlign='center';
    ctx.fillText('Sin expresiones de cálculo',canvas.width/2,canvas.height/2);
    return;
  }
  const W=580, nodeW=90, nodeH=30, gapX=110, gapY=60;
  const totalH=60+calcRows.length*(gapY+nodeH)+60;
  canvas.width=W; canvas.height=Math.max(220,totalH);
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.scale(astZoomFactor,astZoomFactor);

  /* root PROGRAMA */
  const rootX=W/2, rootY=30;
  drawNode(ctx,rootX,rootY,nodeW+20,nodeH,'PROGRAMA','#1e40af','#dbeafe');
  calcRows.forEach((r,i)=>{
    const cx=W/2+(i-(calcRows.length-1)/2)*gapX;
    const cy=rootY+gapY;
    /* línea root→asign */
    line(ctx,rootX,rootY+nodeH/2,cx,cy-nodeH/2,'#9ca3af');
    /* nodo ASIGN */
    drawNode(ctx,cx,cy,nodeW,nodeH,`ASIGN_${i+1}`,'#374151','#f3f4f6');
    /* hijos */
    const lx=cx-gapX*0.45, rx=cx+gapX*0.45, cy2=cy+gapY;
    line(ctx,cx,cy+nodeH/2,lx,cy2-nodeH/2,'#9ca3af');
    line(ctx,cx,cy+nodeH/2,rx,cy2-nodeH/2,'#9ca3af');
    drawNode(ctx,lx,cy2,nodeW-10,nodeH,r.tipo==='calculo'?'calculo':'insumo','#374151','#f3f4f6');
    const op=r.expresion.match(/[+\-*/]/)?.[0]||'=';
    drawNode(ctx,rx,cy2,nodeW-10,nodeH,`expr (${op})`,'#1d4ed8','#dbeafe');
  });
}
function drawNode(ctx,cx,cy,w,h,label,fg,bg){
  const x=cx-w/2, y=cy-h/2;
  ctx.fillStyle=bg; ctx.strokeStyle='#d1d5db'; ctx.lineWidth=1;
  roundRect(ctx,x,y,w,h,4);
  ctx.fillStyle=fg; ctx.font='600 10px -apple-system,sans-serif'; ctx.textAlign='center';
  ctx.fillText(label,cx,cy+4);
}
function line(ctx,x1,y1,x2,y2,color){
  ctx.beginPath(); ctx.strokeStyle=color; ctx.lineWidth=1;
  ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
}
function roundRect(ctx,x,y,w,h,r){
  ctx.beginPath();
  ctx.moveTo(x+r,y); ctx.lineTo(x+w-r,y); ctx.quadraticCurveTo(x+w,y,x+w,y+r);
  ctx.lineTo(x+w,y+h-r); ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
  ctx.lineTo(x+r,y+h); ctx.quadraticCurveTo(x,y+h,x,y+h-r);
  ctx.lineTo(x,y+r); ctx.quadraticCurveTo(x,y,x+r,y);
  ctx.closePath(); ctx.fill(); ctx.stroke();
}
function zoomAST(f){astZoomFactor*=f; if(lastData) drawAST(lastData.tabla_de_simbolos||[])}
function resetZoom(){astZoomFactor=1; if(lastData) drawAST(lastData.tabla_de_simbolos||[])}

/* ── EXPORT ── */
function exportJSON(){
  if(!lastData)return;
  const blob=new Blob([JSON.stringify(lastData,null,2)],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='compilacion_usil.json'; a.click();
}
</script>
</body>
</html>"""


def _get_mongo_collection():
    if not MONGO_AVAILABLE:
        raise RuntimeError("pymongo no instalado.")
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI no configurada en Vercel → Settings → Environment Variables.")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return client[MONGODB_DB][MONGODB_COL]

def _leer_archivo(archivo):
    nombre = archivo.filename.lower()
    contenido = archivo.read()
    try:
        if nombre.endswith(".csv"):
            df = pd.read_csv(BytesIO(contenido), dtype=str)
        elif nombre.endswith((".xlsx", ".xls")):
            df = pd.read_excel(BytesIO(contenido), dtype=str)
        else:
            raise ValueError(f"Formato no soportado: '{archivo.filename}'.")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"No se pudo leer: {e}")
    df.columns = [c.strip() for c in df.columns]
    faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(f"Columnas faltantes: {sorted(faltantes)}. Encontradas: {list(df.columns)}")
    return df

def _compilar_fila(fila_num, tipo_raw, nombre_raw, valor_raw, tabla):
    try:
        tipo = validar_tipo_registro(str(tipo_raw).strip())
    except Exception as e:
        raise ErrorLexico(f"Fila {fila_num} [Tipo_Registro]: {e}")
    try:
        nombre = validar_nombre_variable(str(nombre_raw).strip())
    except Exception as e:
        raise ErrorLexico(f"Fila {fila_num} [Nombre_Variable]: {e}")
    valor_str = str(valor_raw).strip()
    try:
        tokens_valor = tokenizar(valor_str)
    except ErrorLexico as e:
        raise ErrorLexico(f"Fila {fila_num} [Valor_Asignacion]: {e}")
    if tipo in ("insumo", "costo_empaque"):
        if len(tokens_valor) != 1 or tokens_valor[0].tipo not in ("NUMBER_INT", "NUMBER_FLOAT"):
            raise ErrorSintactico(f"Fila {fila_num}: '{tipo}' requiere número literal. Se encontró: '{valor_str}'")
        ast = None
    else:
        try:
            ast = parsear_valor(tokens_valor)
        except ErrorSintactico as e:
            raise ErrorSintactico(f"Fila {fila_num} [Valor_Asignacion]: {e}")
    if tipo == "insumo":
        valor_num = tabla.registrar_insumo(nombre, valor_str, fila_num)
    elif tipo == "costo_empaque":
        valor_num = tabla.registrar_costo_empaque(nombre, valor_str, fila_num)
    else:
        valor_num = tabla.registrar_calculo(nombre, valor_str, ast, fila_num)
    return {"fila": fila_num, "tipo": tipo, "nombre": nombre, "expresion": valor_str, "valor": round(valor_num, 6)}

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE)

@app.route("/compile", methods=["POST"])
def compilar():
    if "archivo" not in request.files:
        return jsonify({"status":"error","fase":"entrada","mensaje":"No se encontró el campo 'archivo'."}), 400
    archivo = request.files["archivo"]
    if not archivo.filename:
        return jsonify({"status":"error","fase":"entrada","mensaje":"Archivo sin nombre."}), 400
    try:
        df = _leer_archivo(archivo)
    except ValueError as e:
        return jsonify({"status":"error","fase":"lectura_archivo","mensaje":str(e)}), 400
    if df.empty:
        return jsonify({"status":"error","fase":"lectura_archivo","mensaje":"El archivo está vacío."}), 400
    tabla = TablaSimbolos()
    filas_procesadas = []
    for idx, row in df.iterrows():
        fila_num = idx + 2
        tipo_raw   = row.get("Tipo_Registro","")
        nombre_raw = row.get("Nombre_Variable","")
        valor_raw  = row.get("Valor_Asignacion","")
        if pd.isna(tipo_raw) or str(tipo_raw).strip() == "":
            continue
        try:
            filas_procesadas.append(_compilar_fila(fila_num, tipo_raw, nombre_raw, valor_raw, tabla))
        except ErrorLexico as e:
            return jsonify({"status":"error","fase":"lexico","fila":fila_num,"mensaje":str(e),"filas_procesadas":len(filas_procesadas)}), 400
        except ErrorSintactico as e:
            return jsonify({"status":"error","fase":"sintactico","fila":fila_num,"mensaje":str(e),"filas_procesadas":len(filas_procesadas)}), 400
        except ErrorSemantico as e:
            return jsonify({"status":"error","fase":"semantico","fila":fila_num,"mensaje":str(e),"filas_procesadas":len(filas_procesadas)}), 400
    tabla_final = tabla.como_lista()
    resumen = {e["nombre"]: e["valor"] for e in tabla_final}
    documento = {
        "metadata": {"archivo_origen":archivo.filename,"total_filas":len(df),"filas_validas":len(filas_procesadas),"compilado_en":datetime.now(timezone.utc).isoformat()},
        "tabla_de_simbolos": tabla_final, "resumen": resumen,
    }
    try:
        col = _get_mongo_collection()
        result = col.insert_one(documento)
        id_insertado = str(result.inserted_id)
    except RuntimeError as e:
        return jsonify({"status":"ok_sin_persistencia","advertencia":str(e),"tabla_de_simbolos":tabla_final,"resumen":resumen,"metadata":documento["metadata"],"mensaje":f"{len(filas_procesadas)} instrucción(es) compiladas."}), 200
    except Exception as e:
        return jsonify({"status":"error","fase":"base_de_datos","mensaje":f"Error MongoDB: {str(e)}"}), 500
    return jsonify({"status":"ok","mensaje":f"{len(filas_procesadas)} instrucción(es) compiladas exitosamente.","id_documento":id_insertado,"tabla_de_simbolos":tabla_final,"resumen":resumen,"metadata":documento["metadata"]}), 200

@app.route("/historial", methods=["GET"])
def historial():
    try:
        col = _get_mongo_collection()
        docs = list(col.find({},{"_id":1,"metadata":1,"resumen":1}).sort("metadata.compilado_en",-1).limit(20))
        for d in docs: d["_id"]=str(d["_id"])
        return jsonify({"status":"ok","total":len(docs),"compilaciones":docs}), 200
    except Exception as e:
        return jsonify({"status":"error","mensaje":str(e)}), 500

@app.errorhandler(404)
def not_found(e): return jsonify({"status":"error","mensaje":f"Ruta no encontrada: {request.path}"}), 404
@app.errorhandler(405)
def method_not_allowed(e): return jsonify({"status":"error","mensaje":f"Método no permitido."}), 405
@app.errorhandler(413)
def too_large(e): return jsonify({"status":"error","mensaje":"Archivo supera 10 MB."}), 413

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
