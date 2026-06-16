import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from datetime import datetime, timezone
from io import BytesIO
import pandas as pd
from flask import Flask, request, jsonify, Response

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

HTML_PAGE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Minicompilador de Inventario</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f6fa;color:#1a1a2e;font-size:14px;line-height:1.6}
nav{background:#fff;border-bottom:1px solid #e8eaf0;padding:0 32px;display:flex;align-items:center;height:56px;position:sticky;top:0;z-index:100;gap:12px}
.nav-brand{font-weight:700;font-size:15px;color:#1a1a2e}
.nav-badge{background:#eef2ff;color:#3730a3;font-size:11px;font-weight:600;padding:2px 10px;border-radius:20px;margin-right:auto}
.nav-links{display:flex;gap:2px}
.nav-link{padding:6px 16px;font-size:13px;font-weight:500;color:#6b7280;cursor:pointer;border:none;background:none;text-decoration:none;border-bottom:2px solid transparent}
.nav-link.active{color:#2563eb;border-bottom-color:#2563eb}
.nav-link:hover{color:#1a1a2e}
.page{display:none;padding:24px 28px;max-width:1100px;margin:0 auto}
.page.active{display:block}
.card{background:#fff;border:1px solid #e8eaf0;border-radius:12px;padding:22px;margin-bottom:18px}
.sec-head{display:flex;align-items:center;gap:10px;margin-bottom:16px}
.sec-num{width:28px;height:28px;background:#2563eb;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0}
.sec-title{font-size:16px;font-weight:700}
.desc-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.desc-block{border-left:3px solid #2563eb;padding:11px 13px;background:#f8faff;border-radius:0 8px 8px 0}
.desc-block.green{border-color:#059669}
.desc-label{font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.desc-text{font-size:12px;color:#374151}
.pipeline{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.pipe-step{background:#eef2ff;color:#3730a3;padding:5px 12px;border-radius:6px;font-size:12px;font-weight:600}
.pipe-step.green{background:#ecfdf5;color:#065f46}
.pipe-arrow{color:#9ca3af}
/* upload */
.upload-zone{border:2px dashed #c7d2fe;border-radius:12px;padding:36px 20px;text-align:center;cursor:pointer;background:#fafbff;transition:all .2s;user-select:none}
.upload-zone:hover{background:#eef2ff;border-color:#6366f1}
.upload-zone.drag{background:#eef2ff;border-color:#6366f1}
.upload-zone.selected{background:#ecfdf5;border-color:#059669}
.u-icon{font-size:34px;margin-bottom:6px}
.u-title{font-size:14px;font-weight:600;color:#4338ca;margin-bottom:3px}
.upload-zone.selected .u-title{color:#065f46}
.u-sub{font-size:12px;color:#9ca3af}
.prog-wrap{margin-top:12px;display:none}
.prog-bar{height:4px;background:#e5e7eb;border-radius:2px;overflow:hidden;margin-bottom:7px}
.prog-fill{height:100%;background:#2563eb;border-radius:2px;transition:width .5s}
.prog-steps{display:flex;gap:6px}
.ps{padding:3px 12px;border-radius:20px;border:1px solid #e5e7eb;font-size:11px;font-weight:600;color:#9ca3af}
.ps.active{background:#eef2ff;border-color:#6366f1;color:#3730a3}
.ps.done{background:#ecfdf5;border-color:#6ee7b7;color:#065f46}
.ps.error{background:#fef2f2;border-color:#fca5a5;color:#b91c1c}
.btn-compile{width:100%;margin-top:12px;padding:11px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px}
.btn-compile:hover{background:#1d4ed8}
.btn-compile:disabled{background:#9ca3af;cursor:not-allowed}
.spinner{width:18px;height:18px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite;display:none}
@keyframes spin{to{transform:rotate(360deg)}}
/* analysis grid */
.analysis-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1fr);gap:14px}
@media(max-width:860px){.analysis-grid{grid-template-columns:1fr}}
.a-card{border:1px solid #e8eaf0;border-radius:10px;padding:14px;background:#fff;min-width:0;overflow:hidden}
.a-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #f3f4f6}
.a-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#374151}
.a-badge{font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px}
.badge-live{background:#dcfce7;color:#15803d}
.badge-cfg{background:#dbeafe;color:#1e40af}
.badge-out{background:#fef3c7;color:#92400e}
.lbl{font-size:11px;color:#6b7280;margin-bottom:4px}
.tok{display:inline-block;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;font-family:monospace;margin:2px}
.tok-kw{background:#ede9fe;color:#5b21b6}
.tok-id{background:#dbeafe;color:#1e40af}
.tok-num{background:#dcfce7;color:#166534}
.tok-op{background:#fef3c7;color:#92400e}
.tok-par{background:#fce7f3;color:#9d174d}
table.atbl{width:100%;border-collapse:collapse;font-size:11px}
table.atbl th{background:#f8faff;padding:5px 6px;text-align:left;font-weight:600;color:#374151;border-bottom:1px solid #e8eaf0}
table.atbl td{padding:4px 6px;border-bottom:1px solid #f3f4f6;font-family:monospace;overflow:hidden;text-overflow:ellipsis;max-width:120px}
.afd-wrap{overflow:hidden;margin:6px 0}
#state-info{background:#f8faff;border-radius:6px;padding:7px 9px;font-size:11px;color:#4b5563;margin-top:6px;border:1px solid #e8eaf0;min-height:34px}
.sim-wrap{margin-top:8px;border-top:1px solid #f3f4f6;padding-top:8px}
.sim-lbl{font-size:11px;font-weight:600;color:#374151;margin-bottom:4px}
.sim-input{width:100%;padding:6px 9px;border-radius:6px;border:1px solid #d1d5db;font-family:monospace;font-size:12px;color:#111;background:#fff}
.sim-btns{display:flex;gap:5px;margin-top:4px}
.sim-btns button{padding:5px 12px;border-radius:6px;border:1px solid #d1d5db;background:#f9fafb;cursor:pointer;font-size:12px;color:#374151}
.sim-btns button:first-child{background:#2563eb;color:#fff;border-color:#2563eb}
#sim-chars{margin-top:5px;min-height:22px;display:flex;flex-wrap:wrap;gap:2px}
#sim-chars span{display:inline-block;padding:2px 5px;border-radius:4px;font-family:monospace;font-size:11px;border:1px solid #e5e7eb}
#sim-chars span.cur{background:#ede9fe;border-color:#7c3aed;color:#4f46e5;font-weight:700}
#sim-chars span.done{background:#f3f4f6;color:#9ca3af}
#sim-result{font-size:11px;margin-top:4px;min-height:16px}
.trans-wrap{overflow-x:auto;margin-top:6px}
table.trans{border-collapse:collapse;font-size:10px;width:100%}
table.trans th{padding:4px 5px;border:1px solid #e8eaf0;text-align:center;font-weight:600;background:#f8faff;white-space:nowrap}
table.trans td{padding:4px 5px;border:1px solid #e8eaf0;text-align:center;font-family:monospace}
code.st{padding:1px 4px;border-radius:3px;font-size:10px}
.cfg-box{background:#f8faff;border-radius:7px;padding:11px;font-family:monospace;font-size:11px;line-height:1.9;overflow-x:auto;white-space:pre;border:1px solid #e8eaf0}
.cfg-kw{color:#2563eb;font-weight:700}
.inst-row{display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-bottom:1px solid #f3f4f6;font-size:11px;gap:4px}
.inst-fila{color:#9ca3af;font-family:monospace;min-width:26px}
.inst-tipo{font-weight:600;color:#2563eb;min-width:80px}
.inst-nom{color:#374151;flex:1;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.inst-val{color:#059669;font-weight:600;font-family:monospace}
table.sym-tbl{table-layout:auto;width:100%}
table.sym-tbl td{white-space:nowrap;padding:5px 8px;border-bottom:1px solid #f3f4f6;font-family:monospace;font-size:11px}
table.sym-tbl th{white-space:nowrap;background:#f8faff;padding:5px 8px;text-align:left;font-weight:600;color:#374151;border-bottom:1px solid #e8eaf0}
table.sym-tbl td:first-child{font-weight:600;color:#4f46e5}
table.sym-tbl tr.row-cos td:first-child{color:#b45309}
table.sym-tbl tr.row-cal td:first-child{color:#059669}
.sym-scroll{overflow-x:auto;width:100%}
.json-out{background:#1e1e2e;border-radius:7px;padding:10px;font-family:monospace;font-size:11px;color:#cdd6f4;white-space:pre-wrap;min-height:48px;overflow-x:auto;border:1px solid #2a2a3e}
.stats-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-top:7px}
.stat-box{background:#f8faff;border-radius:7px;padding:9px;text-align:center;border:1px solid #e8eaf0}
.stat-lbl{font-size:10px;color:#9ca3af;font-weight:600;text-transform:uppercase}
.stat-val{font-size:20px;font-weight:700}
.btn-sync{width:100%;margin-top:9px;padding:8px;background:#f8faff;border:1px solid #e8eaf0;border-radius:7px;font-size:12px;font-weight:600;cursor:pointer;color:#374151;display:flex;align-items:center;justify-content:center;gap:6px}
.btn-sync:hover{background:#eef2ff;border-color:#6366f1;color:#3730a3}
.sdot{width:8px;height:8px;border-radius:50%;background:#9ca3af;display:inline-block}
/* results page */
.res-header{border-left:4px solid #2563eb;padding:7px 0 7px 14px;margin-bottom:22px}
.res-header h2{font-size:20px;font-weight:700}
.res-header p{font-size:13px;color:#6b7280;margin-top:2px}
.res-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:700px){.res-grid{grid-template-columns:1fr}}
.panel{background:#fff;border:1px solid #e8eaf0;border-radius:12px;padding:18px}
.panel-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.panel-title{display:flex;align-items:center;gap:7px;font-size:14px;font-weight:700}
.panel-badge{font-size:10px;font-weight:700;padding:3px 9px;border-radius:4px;background:#f3f4f6;color:#6b7280;letter-spacing:.4px}
.cfg-full{background:#f8faff;border:1px solid #e8eaf0;border-radius:8px;padding:14px;font-family:monospace;font-size:12px;line-height:2;overflow-x:auto;white-space:pre}
#ast-wrap{background:#f8faff;border:1px solid #e8eaf0;border-radius:8px;overflow:auto;height:320px;max-height:320px;padding:8px;margin-top:8px;cursor:grab}
.ast-controls{display:flex;gap:5px}
.ast-btn{padding:4px 9px;border-radius:6px;border:1px solid #e5e7eb;background:#f9fafb;cursor:pointer;font-size:11px}
.json-dark{background:#1e1e2e;border-radius:12px;padding:18px;border:1px solid #2a2a3e}
.json-dark-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.json-dark-title{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:700;color:#cdd6f4}
.btn-export{background:#2563eb;color:#fff;border:none;border-radius:6px;padding:5px 13px;font-size:12px;font-weight:600;cursor:pointer}
.json-scroll{font-family:monospace;font-size:11px;color:#cdd6f4;white-space:pre-wrap;overflow-x:auto;line-height:1.7;max-height:260px;overflow-y:auto}
.metrics-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.metric-card{background:#fff;border:1px solid #e8eaf0;border-radius:10px;padding:14px}
.metric-lbl{font-size:12px;color:#6b7280;margin-bottom:4px}
.metric-val{font-size:26px;font-weight:700;color:#2563eb}
.metric-bar{height:3px;background:#2563eb;border-radius:2px;margin-top:7px}
.dist-row{display:flex;align-items:center;gap:9px;margin-bottom:7px}
.dist-lbl{font-size:12px;color:#374151;width:65px}
.dist-bw{flex:1;height:8px;background:#f3f4f6;border-radius:4px;overflow:hidden}
.dist-bf{height:100%;border-radius:4px}
.dist-pct{font-size:12px;font-weight:600;color:#374151;width:32px;text-align:right}
.val-row{display:flex;align-items:center;justify-content:space-between;padding:11px;border:1px solid #e8eaf0;border-radius:8px;margin-top:10px}
.val-ok{display:flex;align-items:center;gap:8px}
.val-dot{width:10px;height:10px;border-radius:50%;background:#22c55e}
.val-h{font-size:13px;font-weight:700;color:#15803d}
.val-p{font-size:11px;color:#6b7280}
.res-cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:9px;margin-top:12px}
.rc{background:#fff;border:1px solid #e8eaf0;border-radius:8px;padding:11px 13px}
.rc-lbl{font-size:10px;color:#9ca3af;font-weight:600;text-transform:uppercase}
.rc-val{font-size:17px;font-weight:700;color:#2563eb;margin-top:2px}
.err-panel{background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:14px}
.err-panel h3{color:#b91c1c;font-size:14px;margin-bottom:5px}
.efase{display:inline-block;background:#fee2e2;color:#b91c1c;border-radius:4px;padding:2px 7px;font-size:10px;font-weight:700;text-transform:uppercase;margin-right:5px}
footer{background:#fff;border-top:1px solid #e8eaf0;padding:18px 28px;display:flex;align-items:center;justify-content:space-between;margin-top:28px}
.ft-brand{font-weight:700;color:#2563eb;font-size:13px}
.ft-sub{font-size:11px;color:#9ca3af;margin-top:1px}
.ft-links{display:flex;gap:18px}
.ft-links button{font-size:12px;color:#6b7280;border:none;background:none;cursor:pointer}
.ft-links button:hover{color:#2563eb}
.ph{font-size:11px;color:#9ca3af;font-style:italic}
</style>
</head>
<body>

<nav>
  <span class="nav-brand">Minicompilador de Inventario</span>
  <span class="nav-badge">USIL 2026</span>
  <div class="nav-links">
    <button class="nav-link active" id="nav-compiler" onclick="showPage('compiler')">Compiler</button>
    <button class="nav-link" id="nav-results" onclick="showPage('results')">Resultados</button>
    <button class="nav-link" id="nav-docs" onclick="showPage('docs')">Documentación</button>
  </div>
  <span style="font-size:18px;cursor:pointer">⚙</span>
</nav>

<!-- COMPILER -->
<div class="page active" id="page-compiler">
  <div class="card">
    <div class="sec-head"><div class="sec-num">1</div><h2 class="sec-title">Descripción del compilador</h2></div>
    <div class="desc-grid">
      <div class="desc-block"><div class="desc-label">Proceso de entrada</div><div class="desc-text">El personal sube un Excel/CSV con columnas <code>Tipo_Registro</code>, <code>Nombre_Variable</code>, <code>Valor_Asignacion</code>. Cada fila es una instrucción de asignación.</div></div>
      <div class="desc-block green"><div class="desc-label">Resultado generado</div><div class="desc-text">Si el archivo es 100% válido → JSON con Tabla de Símbolos resuelta → MongoDB Atlas. Si hay error → fila y fase exacta del análisis.</div></div>
    </div>
    <div class="pipeline">
      <span class="pipe-step">📄 Excel/CSV</span><span class="pipe-arrow">→</span>
      <span class="pipe-step">🔤 Léxico</span><span class="pipe-arrow">→</span>
      <span class="pipe-step">📐 Sintáctico</span><span class="pipe-arrow">→</span>
      <span class="pipe-step">🧠 Semántico</span><span class="pipe-arrow">→</span>
      <span class="pipe-step green">🍃 MongoDB Atlas</span>
    </div>
  </div>

  <div class="card">
    <div class="sec-head"><div class="sec-num">2</div><h2 class="sec-title">Ingreso de datos — cargar archivo</h2></div>
    <input type="file" id="fileInput" accept=".xlsx,.xls,.csv" style="display:none">
    <div class="upload-zone" id="uploadZone">
      <div class="u-icon" id="u-icon">☁️</div>
      <div class="u-title" id="u-title">Haz clic o arrastra tu archivo aquí</div>
      <div class="u-sub" id="u-sub">Formatos: .xlsx · .xls · .csv — máximo 10 MB</div>
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

  <div class="card">
    <div class="sec-head"><div class="sec-num">3</div><h2 class="sec-title">Proceso interno del compilador</h2></div>
    <div class="analysis-grid">

      <!-- 3.1 LÉXICO -->
      <div class="a-card">
        <div class="a-head"><span class="a-title">3.1 Análisis Léxico</span><span class="a-badge badge-live">LIVE</span></div>
        <p class="lbl">Tokens detectados</p>
        <div id="tokens-live"><span class="ph">Carga un archivo…</span></div>

        <p class="lbl" style="margin-top:10px">AFD — estados activos según el archivo</p>
        <div class="afd-wrap" id="afd-wrap">
          <svg id="afd-svg" width="100%" viewBox="0 0 420 290"></svg>
        </div>
        <div id="state-info">Haz clic en un estado para ver su descripción.</div>

        <div class="sim-wrap">
          <div class="sim-lbl">Simulador de cadena</div>
          <input class="sim-input" id="sim-input" placeholder="Ej: hilos_lana  |  3.50  |  +">
          <div class="sim-btns">
            <button onclick="simular()">Simular</button>
            <button onclick="resetSim()">Reset</button>
          </div>
          <div id="sim-chars"></div>
          <div id="sim-result"></div>
        </div>

        <p class="lbl" style="margin-top:10px;font-weight:600">Tabla de Transiciones</p>
        <div class="trans-wrap">
          <table class="trans">
            <thead><tr>
              <th>Estado</th>
              <th style="background:#f0fdf4;color:#15803d">letra/_</th>
              <th style="background:#f5f3ff;color:#5b21b6">dígito</th>
              <th style="background:#f5f3ff;color:#5b21b6">punto</th>
              <th style="background:#fffbeb;color:#92400e">op</th>
              <th>esp/fin</th>
              <th style="background:#fef2f2;color:#b91c1c">otro</th>
            </tr></thead>
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
        <div class="a-head"><span class="a-title">3.2 Análisis Sintáctico</span><span class="a-badge badge-cfg">CFG</span></div>
        <p class="lbl">Gramática Libre de Contexto (CFG)</p>
        <div class="cfg-box"><span class="cfg-kw">programa</span>    → instruccion*
<span class="cfg-kw">instruccion</span> → tipo ID = expr
<span class="cfg-kw">tipo</span>        → insumo | costo | calculo

<span class="cfg-kw">expr</span>    → term rest_E
<span class="cfg-kw">rest_E</span>  → ('+' | '-') term rest_E | ε

<span class="cfg-kw">term</span>    → factor rest_T
<span class="cfg-kw">rest_T</span>  → ('*' | '/') factor rest_T | ε

<span class="cfg-kw">factor</span>  → NUMBER | IDENTIFIER | '(' expr ')'</div>

        <p class="lbl" style="margin-top:10px">Árbol Sintáctico (AST en vivo)</p>
        <div id="ast-preview" style="background:#f8faff;border:1px solid #e8eaf0;border-radius:7px;padding:10px;min-height:70px;font-family:monospace;font-size:11px;white-space:pre;overflow-x:auto"><span class="ph">Carga un archivo para visualizar el AST…</span></div>

        <p class="lbl" style="margin-top:10px">Instrucciones Analizadas</p>
        <div id="inst-live"><span class="ph">Esperando archivo…</span></div>
      </div>

      <!-- 3.3 SEMÁNTICO -->
      <div class="a-card">
        <div class="a-head"><span class="a-title">3.3 Semántico · Traducción</span><span class="a-badge badge-out">OUTPUT</span></div>
        <p class="lbl">Tabla de Símbolos (en vivo)</p>
        <div id="sym-live"><span class="ph">Sin variables registradas</span></div>

        <p class="lbl" style="margin-top:10px">Traducción JSON → MongoDB</p>
        <div class="json-out" id="json-out">{ "status": "waiting_upload" }</div>

        <p class="lbl" style="margin-top:10px">Estadísticas de Compilación</p>
        <div class="stats-grid">
          <div class="stat-box"><div class="stat-lbl">Insumos</div><div class="stat-val" style="color:#4f46e5" id="cnt-ins">--</div></div>
          <div class="stat-box"><div class="stat-lbl">Costos</div><div class="stat-val" style="color:#b45309" id="cnt-cos">--</div></div>
          <div class="stat-box"><div class="stat-lbl">Cálculos</div><div class="stat-val" style="color:#059669" id="cnt-cal">--</div></div>
        </div>
        <button class="btn-sync" onclick="showPage('results')">
          <span class="sdot" id="syncDot"></span>Sincronizar con Atlas
        </button>
      </div>

    </div>
  </div>
</div>

<!-- RESULTS -->
<div class="page" id="page-results">
  <div class="res-header"><h2>Análisis Post-Compilación</h2><p>Visualización detallada de la estructura gramatical, el árbol AST y la resolución semántica.</p></div>
  <div id="res-err-panel"></div>
  <div id="res-ok" style="display:none">
    <div class="res-grid">
      <div>
        <div class="panel">
          <div class="panel-head"><div class="panel-title">📐 Gramática Libre de Contexto</div><span class="panel-badge">FORMAL LOGIC</span></div>
          <div class="cfg-full"><span class="cfg-kw">programa</span>    → instruccion*
<span class="cfg-kw">instruccion</span> → tipo ID = expr
<span class="cfg-kw">tipo</span>        → insumo | costo_empaque | calculo

<span class="cfg-kw">expr</span>    → term rest_E
<span class="cfg-kw">rest_E</span>  → ('+' | '-') term rest_E | ε

<span class="cfg-kw">term</span>    → factor rest_T
<span class="cfg-kw">rest_T</span>  → ('*' | '/') factor rest_T | ε

<span class="cfg-kw">factor</span>  → NUMBER | IDENTIFIER | '(' expr ')'</div>
        </div>
        <div class="panel" style="margin-top:14px">
          <div class="panel-head">
            <div class="panel-title">🌿 Árbol de Sintaxis Abstracta (AST)</div>
            <div class="ast-controls">
              <button class="ast-btn" onclick="zoomAST(1.2)">🔍+</button>
              <button class="ast-btn" onclick="zoomAST(0.8)">🔍−</button>
              <button class="ast-btn" onclick="resetZoom()">⛶</button>
            </div>
          </div>
          <div id="ast-wrap"><p class="ph" style="text-align:center;padding:40px 0">Compila un archivo para ver el AST</p></div>
        </div>
      </div>
      <div>
        <div class="json-dark">
          <div class="json-dark-head"><div class="json-dark-title">📤 Traducción JSON (Semántico)</div><button class="btn-export" onclick="exportJSON()">Exportar</button></div>
          <div class="json-scroll" id="json-full"></div>
        </div>
        <div class="metrics-grid">
          <div class="metric-card"><div class="metric-lbl">Tokens procesados</div><div class="metric-val" id="m-tokens">0</div><div class="metric-bar"></div></div>
          <div class="metric-card"><div class="metric-lbl">Tiempo de compilación</div><div class="metric-val" id="m-tiempo">0ms</div><div class="metric-bar" style="background:#059669"></div></div>
        </div>
        <div class="panel" style="margin-top:12px">
          <div class="panel-head"><div class="panel-title">📊 Distribución de Tipos</div></div>
          <div id="dist-bars"></div>
        </div>
        <div class="val-row" id="val-row" style="display:none">
          <div class="val-ok"><div class="val-dot" id="val-dot"></div><div><div class="val-h" id="val-h">Validación Exitosa</div><div class="val-p" id="val-p">Sincronizado con MongoDB Atlas</div></div></div>
          <button onclick="showPage('compiler')" style="border:none;background:none;cursor:pointer;font-size:18px;color:#9ca3af">↺</button>
        </div>
      </div>
    </div>
    <div class="panel" id="res-cards-wrap" style="display:none;margin-top:14px">
      <div class="panel-head"><div class="panel-title">📦 Valores resueltos</div></div>
      <div class="res-cards-grid" id="res-cards-grid"></div>
    </div>
  </div>
</div>

<!-- DOCS -->
<div class="page" id="page-docs">
  <div class="res-header"><h2>Documentación</h2><p>Referencia técnica del minicompilador USIL 2026.</p></div>
  <div class="card">
    <div class="sec-head"><div class="sec-num">📄</div><h2 class="sec-title">Formato del archivo</h2></div>
    <table class="atbl">
      <tr><th>Columna</th><th>Tipo</th><th>Valores válidos</th><th>Ejemplo</th></tr>
      <tr><td>Tipo_Registro</td><td>Texto</td><td>insumo · costo_empaque · calculo</td><td>insumo</td></tr>
      <tr><td>Nombre_Variable</td><td>Identificador</td><td>[a-zA-Z_][a-zA-Z0-9_]*</td><td>hilos_lana</td></tr>
      <tr><td>Valor_Asignacion</td><td>Número o expresión</td><td>150 · 3.50 · var1 + var2</td><td>hilos_lana + ojos_seguridad</td></tr>
    </table>
  </div>
  <div class="card">
    <div class="sec-head"><div class="sec-num">⚠</div><h2 class="sec-title">Errores y cómo resolverlos</h2></div>
    <table class="atbl">
      <tr><th>Fase</th><th>Causa</th><th>Solución</th></tr>
      <tr><td><span class="tok tok-op">LÉXICO</span></td><td>Carácter inválido ($,@,#) en el valor</td><td>Use solo letras, números, _ y operadores +−*/</td></tr>
      <tr><td><span class="tok tok-id">SINTÁCTICO</span></td><td>Expresión malformada (ej: "150 +")</td><td>Toda expresión debe tener operandos completos</td></tr>
      <tr><td><span class="tok tok-kw">SEMÁNTICO</span></td><td>Variable usada sin haber sido declarada</td><td>Declare primero como insumo o costo_empaque</td></tr>
    </table>
  </div>
</div>

<footer>
  <div><div class="ft-brand">Inventory Compiler.</div><div class="ft-sub">© 2026 Minicompilador USIL. Utilitarian System Architecture.</div></div>
  <div class="ft-links">
    <button onclick="showPage('docs')">Documentation</button>
    <button onclick="showPage('results')">Process Specs</button>
  </div>
</footer>

<script>
// ── NAVEGACIÓN ──
let currentPage = 'compiler';
function showPage(p) {
  document.querySelectorAll('.page').forEach(function(x){ x.classList.remove('active'); });
  document.querySelectorAll('.nav-link').forEach(function(x){ x.classList.remove('active'); });
  var pg = document.getElementById('page-' + p);
  var nl = document.getElementById('nav-' + p);
  if (pg) pg.classList.add('active');
  if (nl) nl.classList.add('active');
  currentPage = p;
  if (p === 'results') renderResultsPage();
}

// ── ESTADO GLOBAL ──
var lastData = null;
var archivoFile = null;
var compilElapsed = 0;
var astZoomFactor = 1;

// ── UPLOAD ──
var zone = document.getElementById('uploadZone');
var inp  = document.getElementById('fileInput');

zone.addEventListener('click', function() { inp.click(); });
zone.addEventListener('dragover', function(e) { e.preventDefault(); zone.classList.add('drag'); });
zone.addEventListener('dragleave', function() { zone.classList.remove('drag'); });
zone.addEventListener('drop', function(e) {
  e.preventDefault(); zone.classList.remove('drag');
  if (e.dataTransfer.files[0]) pickFile(e.dataTransfer.files[0]);
});
inp.addEventListener('change', function() {
  if (inp.files[0]) pickFile(inp.files[0]);
});

function pickFile(f) {
  archivoFile = f;
  zone.className = 'upload-zone selected';
  document.getElementById('u-icon').textContent  = '✅';
  document.getElementById('u-title').textContent = f.name;
  document.getElementById('u-sub').textContent   = (f.size/1024).toFixed(1) + ' KB · listo para compilar';
  document.getElementById('btnC').disabled = false;
  document.getElementById('btnT').textContent = '⚙️ Compilar archivo';
}

// ── PROGRESS ──
function setPhase(ph) {
  var order = ['ps-lex','ps-sin','ps-sem','ps-db'];
  var pct   = {lex:25, sin:50, sem:75, db:100};
  var idx   = {lex:0,  sin:1,  sem:2,  db:3};
  var cur   = idx[ph] !== undefined ? idx[ph] : 0;
  order.forEach(function(id, i) {
    var el = document.getElementById(id);
    el.className = 'ps' + (i < cur ? ' done' : i === cur ? ' active' : '');
  });
  document.getElementById('progFill').style.width = (pct[ph] || 10) + '%';
}
function setPhaseErr(fase) {
  var map = {lexico:'ps-lex', sintactico:'ps-sin', semantico:'ps-sem', base_de_datos:'ps-db'};
  var id = map[fase]; if (id) document.getElementById(id).className = 'ps error';
}

// ── AFD ──
var SD = {
  q0:{l:'q0 — Inicio', d:'Primer carácter decide el camino: letra→q1, dígito→q2, op→q4, inválido→qERR'},
  q1:{l:'q1 — Identificador/KW', d:'Consume letras, dígitos y _. Al terminar emite IDENTIFIER, KW_INSUMO, KW_CALCULO, etc.'},
  q2:{l:'q2 — Número entero', d:'Consume dígitos. Un punto "." lleva a q3 (float). Otro carácter acepta como NUMBER_INT.'},
  q3:{l:'q3 — Parte decimal', d:'Consume dígitos tras el punto. Al terminar acepta como NUMBER_FLOAT.'},
  q4:{l:'q4 — Operador (aceptación)', d:'Acepta inmediatamente: OP_PLUS, OP_MINUS, OP_MUL, OP_DIV, LPAREN, RPAREN.'},
  q5:{l:'q5 — Aceptación general', d:'Token completo emitido. Regresa a q0 para el siguiente token.'},
  qe:{l:'qERR — Error léxico', d:'Carácter inválido ($@#…). Lanza ErrorLexico con posición exacta.'}
};
function qs(id) {
  var s = SD[id]; if (!s) return;
  document.getElementById('state-info').innerHTML =
    '<strong style="color:#2563eb">' + s.l + '</strong><br>' + s.d;
}

function drawAFD(tabla) {
  var used = {q0:true, q5:true};
  if (tabla && tabla.length) {
    used.q1 = true;
    tabla.forEach(function(r) {
      var expr = String(r.expresion || '');
      if (/[a-zA-Z_]/.test(expr)) used.q1 = true;
      if (/\d+\.\d+/.test(expr))  { used.q2 = true; used.q3 = true; }
      else if (/\d/.test(expr))    used.q2 = true;
      if (/[+\-*\/()]/.test(expr)) used.q4 = true;
    });
  }
  function sc(id) { return used[id] ? '#2563eb' : '#9ca3af'; }
  function sf(id) { return used[id] ? '#dbeafe' : '#f3f4f6'; }
  function st(id) { return used[id] ? '#1e40af' : '#6b7280'; }
  function sw(id) { return used[id] ? 2 : 1; }
  function lc(a,b) { return (used[a] || used[b]) ? '#2563eb' : '#e5e7eb'; }
  function lo(a,b) { return (used[a] || used[b]) ? 1 : 0.35; }
  function lw(a,b) { return (used[a] || used[b]) ? 1.8 : 1; }

  var mk = '<defs><marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>';

  function circ(cx,cy,r,id,lbl,dbl){
    var s = '<g data-state="'+id+'" style="cursor:pointer">';
    s += '<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="'+sf(id)+'" stroke="'+sc(id)+'" stroke-width="'+sw(id)+'"/>';
    if (dbl) s += '<circle cx="'+cx+'" cy="'+cy+'" r="'+(r-6)+'" fill="none" stroke="'+sc(id)+'" stroke-width="1"/>';
    s += '<text x="'+cx+'" y="'+cy+'" text-anchor="middle" dominant-baseline="central" font-size="12" font-weight="700" fill="'+st(id)+'">'+lbl+'</text></g>';
    return s;
  }
  function path(d,a,b,col,op,w) { return '<path d="'+d+'" fill="none" stroke="'+(col||lc(a,b))+'" stroke-width="'+(w||lw(a,b))+'" marker-end="url(#ar)" opacity="'+(op||lo(a,b))+'"/>'; }
  function line(x1,y1,x2,y2,a,b) { return '<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" stroke="'+lc(a,b)+'" stroke-width="'+lw(a,b)+'" marker-end="url(#ar)" opacity="'+lo(a,b)+'"/>'; }
  function txt(x,y,t,c) { return '<text x="'+x+'" y="'+y+'" text-anchor="middle" font-size="9" fill="'+(c||'#6b7280')+'">'+t+'</text>'; }

  var svg = mk;
  // entrada
  svg += '<line x1="20" y1="143" x2="48" y2="143" stroke="#9ca3af" stroke-width="1.5" marker-end="url(#ar)"/>';
  svg += '<polygon points="14,139 14,147 6,143" fill="#9ca3af"/>';
  // estados
  svg += circ(74,143,24,'q0','q0',true) + txt(74,175,'inicio');
  svg += circ(200,65,24,'q1','q1',false) + txt(200,97,'ident/kw' + (used.q1?' ✓':''));
  svg += circ(200,150,24,'q2','q2',false) + txt(200,182,'int' + (used.q2?' ✓':''));
  svg += circ(200,232,24,'q3','q3',false) + txt(200,264,'float' + (used.q3?' ✓':''));
  svg += circ(340,85,24,'q4','q4',true)  + txt(340,117,'op' + (used.q4?' ✓':''));
  svg += circ(340,195,24,'q5','q5',true) + txt(340,227,'token ✓');
  // qERR siempre rojo
  svg += '<g data-state="qe" style="cursor:pointer">';
  svg += '<circle cx="74" cy="248" r="20" fill="#fef2f2" stroke="#dc2626" stroke-width="1.5"/>';
  svg += '<text x="74" y="248" text-anchor="middle" dominant-baseline="central" font-size="9" font-weight="700" fill="#b91c1c">qERR</text></g>';
  // transiciones
  svg += path('M94 130 Q144 92 176 72','q0','q1') + txt(126,86,'letra/_',used.q1?'#1d4ed8':'#9ca3af');
  svg += line(98,143,176,148,'q0','q2') + txt(136,136,'dígito',used.q2?'#5b21b6':'#9ca3af');
  svg += path('M92 128 Q200 54 316 78','q0','q4') + txt(200,48,'+−*/( )',used.q4?'#92400e':'#9ca3af');
  svg += '<line x1="74" y1="167" x2="74" y2="228" stroke="#dc2626" stroke-width="1.2" marker-end="url(#ar)" stroke-dasharray="3 2" opacity=".5"/>';
  svg += txt(56,198,'otro','#dc2626');
  svg += path('M188 40 Q196 20 212 32 Q222 44 212 58','q1','q1');
  svg += txt(220,18,'letra/díg/_',used.q1?'#1d4ed8':'#9ca3af');
  svg += path('M188 126 Q196 110 210 118 Q220 128 210 140','q2','q2');
  svg += line(200,174,200,208,'q2','q3') + txt(213,192,'.',used.q3?'#5b21b6':'#9ca3af');
  svg += path('M188 210 Q196 194 210 202 Q220 212 210 226','q3','q3');
  svg += path('M224 68 Q284 104 316 180','q1','q5') + txt(290,112,'otro',used.q1?'#1d4ed8':'#9ca3af');
  svg += line(224,152,316,188,'q2','q5');
  svg += path('M224 228 Q278 228 316 202','q3','q5');
  // leyenda
  svg += '<rect x="4" y="2" width="138" height="24" rx="4" fill="#f8faff" stroke="#e8eaf0" stroke-width="0.5"/>';
  svg += '<circle cx="16" cy="14" r="5" fill="#dbeafe" stroke="#2563eb" stroke-width="1.5"/>';
  svg += '<text x="25" y="18" font-size="9" fill="#374151">estado activo (compilación)</text>';

  document.getElementById('afd-svg').innerHTML = svg;
  // Event delegation para los estados del AFD
  document.getElementById('afd-svg').querySelectorAll('[data-state]').forEach(function(el){
    el.addEventListener('click', function(){ qs(el.getAttribute('data-state')); });
  });
}

// Dibujar AFD inicial (todos inactivos)
drawAFD(null);

// ── SIMULADOR ──
function classify(t) {
  var kw = ['insumo','costo_empaque','calculo','costo_produccion','total'];
  if (kw.indexOf(t.toLowerCase()) >= 0) return {tipo:'KEYWORD', c:'#5b21b6', bg:'#ede9fe'};
  if (/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(t)) return {tipo:'IDENTIFIER', c:'#15803d', bg:'#dcfce7'};
  if (/^\d+$/.test(t))       return {tipo:'NUMBER_INT',   c:'#5b21b6', bg:'#ede9fe'};
  if (/^\d+\.\d+$/.test(t))  return {tipo:'NUMBER_FLOAT', c:'#5b21b6', bg:'#ede9fe'};
  if (/^[+\-*\/()]$/.test(t)) return {tipo:'OPERADOR',    c:'#92400e', bg:'#fef3c7'};
  return {tipo:'ERROR', c:'#b91c1c', bg:'#fef2f2'};
}
function simular() {
  var raw = document.getElementById('sim-input').value.trim(); if (!raw) return;
  var chars = raw.split('');
  var cc = document.getElementById('sim-chars');
  var rc = document.getElementById('sim-result');
  cc.innerHTML = chars.map(function(c,i){ return '<span id="ch'+i+'">'+(c===' '?'␣':c)+'</span>'; }).join('');
  rc.innerHTML = '';
  var i = 0;
  function step(){
    if (i > 0) { var prev = document.getElementById('ch'+(i-1)); if(prev) prev.classList.replace('cur','done'); }
    if (i < chars.length) { var el = document.getElementById('ch'+i); if(el) el.classList.add('cur'); i++; setTimeout(step,180); }
    else {
      var r = classify(raw);
      rc.innerHTML = r.tipo === 'ERROR'
        ? '<span style="color:#b91c1c">qERR — carácter inválido: <b>' + raw + '</b></span>'
        : '<span style="background:'+r.bg+';color:'+r.c+';padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;font-family:monospace">'+r.tipo+'</span> → aceptado en q5';
    }
  }
  step();
}
function resetSim() {
  document.getElementById('sim-chars').innerHTML = '';
  document.getElementById('sim-result').innerHTML = '';
  document.getElementById('sim-input').value = '';
  document.getElementById('state-info').textContent = 'Haz clic en un estado para ver su descripción.';
}

// ── COMPILAR ──
async function compilar() {
  if (!archivoFile) return;
  var t0 = Date.now();
  document.getElementById('btnC').disabled = true;
  document.getElementById('btnT').style.display = 'none';
  document.getElementById('sp').style.display = 'block';
  document.getElementById('progWrap').style.display = 'block';
  setPhase('lex');
  setTimeout(function(){ setPhase('sin'); }, 350);
  setTimeout(function(){ setPhase('sem'); }, 700);
  var fd = new FormData();
  fd.append('archivo', archivoFile);
  try {
    var res  = await fetch('/compile', {method:'POST', body:fd});
    var data = await res.json();
    compilElapsed = Date.now() - t0;
    lastData = data;
    if (data.status === 'ok' || data.status === 'ok_sin_persistencia') {
      setPhase('db');
      fillPanels(data);
    } else {
      setPhaseErr(data.fase || 'lexico');
      document.getElementById('tokens-live').innerHTML =
        '<span style="color:#b91c1c;font-size:11px">❌ ' + (data.mensaje||'Error') + '</span>';
    }
  } catch(e) {
    document.getElementById('tokens-live').innerHTML =
      '<span style="color:#b91c1c;font-size:11px">❌ Error de red: ' + e.message + '</span>';
  } finally {
    document.getElementById('btnC').disabled = false;
    document.getElementById('btnT').style.display = 'inline';
    document.getElementById('sp').style.display = 'none';
  }
}

// ── FILL PANELS ──
function fillPanels(data) {
  var tabla = data.tabla_de_simbolos || [];
  // tokens
  var tm = {insumo:'tok-kw', costo_empaque:'tok-op', calculo:'tok-id'};
  document.getElementById('tokens-live').innerHTML = tabla.map(function(r){
    return '<span class="tok '+(tm[r.tipo]||'tok-id')+'">'+r.tipo.toUpperCase()+'</span>'
         + '<span class="tok tok-id">'+r.nombre+'</span>'
         + '<span class="tok tok-num">'+r.valor+'</span>';
  }).join('');
  // AFD dinámico
  drawAFD(tabla);
  // AST preview
  var ast = '';
  tabla.forEach(function(r){
    if (r.tipo === 'calculo') {
      var nl = String.fromCharCode(10); ast += 'ASIGNACION' + nl + '  ID: ' + r.nombre + nl + '  EXPR: ' + r.expresion + nl + '  eval = ' + r.valor + nl + nl;
    }
  });
  document.getElementById('ast-preview').innerHTML = ast || '(sin expresiones de cálculo)';
  // instrucciones
  document.getElementById('inst-live').innerHTML = tabla.map(function(r){
    return '<div class="inst-row"><span class="inst-fila">F'+r.fila+'</span>'
         + '<span class="inst-tipo">'+r.tipo+'</span>'
         + '<span class="inst-nom">'+r.nombre+'</span>'
         + '<span class="inst-val">'+r.valor+'</span></div>';
  }).join('');
  // tabla símbolos
  var symRows = tabla.map(function(r){
    var cls = r.tipo==='insumo' ? '' : (r.tipo==='costo_empaque' ? 'row-cos' : 'row-cal');
    return '<tr class="'+cls+'"><td>'+r.nombre+'</td><td>'+r.tipo+'</td><td>'+r.expresion+'</td><td><b>'+r.valor+'</b></td></tr>';
  }).join('');
  document.getElementById('sym-live').innerHTML =
    '<div class="sym-scroll"><table class="sym-tbl"><tr><th>Nombre</th><th>Tipo</th><th>Expresión</th><th>Valor</th></tr>' + symRows + '</table></div>';
  // JSON out
  document.getElementById('json-out').textContent = JSON.stringify(data.resumen||{}, null, 2);
  // stats
  document.getElementById('cnt-ins').textContent = tabla.filter(function(r){ return r.tipo==='insumo'; }).length;
  document.getElementById('cnt-cos').textContent = tabla.filter(function(r){ return r.tipo==='costo_empaque'; }).length;
  document.getElementById('cnt-cal').textContent = tabla.filter(function(r){ return r.tipo==='calculo'; }).length;
  // sync dot
  document.getElementById('syncDot').style.background = data.id_documento ? '#22c55e' : '#f59e0b';
}

// ── RESULTS PAGE ──
function renderResultsPage() {
  var errEl = document.getElementById('res-err-panel');
  var okEl  = document.getElementById('res-ok');
  if (!lastData) {
    errEl.innerHTML = '<div class="err-panel"><h3>Sin datos</h3><p>Primero compila un archivo en la sección Compiler.</p></div>';
    okEl.style.display = 'none'; return;
  }
  var data = lastData;
  if (data.status !== 'ok' && data.status !== 'ok_sin_persistencia') {
    errEl.innerHTML = '<div class="err-panel"><h3>❌ Compilación fallida</h3><p><span class="efase">'+(data.fase||'')+'</span>'+(data.mensaje||'')+'</p></div>';
    okEl.style.display = 'none'; return;
  }
  errEl.innerHTML = '';
  okEl.style.display = 'block';
  var tabla = data.tabla_de_simbolos || [];
  var elapsed = compilElapsed;
  // JSON
  var jsonObj = {
    status: 'SUCCESS',
    timestamp: new Date().toISOString(),
    id: data.id_documento || 'sin_persistencia',
    inventory_compilation: tabla.map(function(r){ return {type:r.tipo, id:r.nombre, value:r.valor, expr:r.expresion}; })
  };
  document.getElementById('json-full').innerHTML = syntaxHL(JSON.stringify(jsonObj, null, 2));
  // métricas (fijas, no aumentan)
  document.getElementById('m-tokens').textContent = tabla.length * 3;
  document.getElementById('m-tiempo').textContent = elapsed + 'ms';
  // distribución
  var ins = tabla.filter(function(r){ return r.tipo==='insumo'; }).length;
  var cos = tabla.filter(function(r){ return r.tipo==='costo_empaque'; }).length;
  var cal = tabla.filter(function(r){ return r.tipo==='calculo'; }).length;
  var tot = tabla.length || 1;
  document.getElementById('dist-bars').innerHTML =
    distRow('Insumos', ins, tot, '#2563eb') +
    distRow('Costos',  cos, tot, '#6b7280') +
    distRow('Cálculos',cal, tot, '#374151');
  // validación
  document.getElementById('val-row').style.display = 'flex';
  document.getElementById('val-dot').style.background = data.id_documento ? '#22c55e' : '#f59e0b';
  document.getElementById('val-h').textContent = data.id_documento ? 'Validación Exitosa' : 'Sin persistencia';
  document.getElementById('val-p').textContent = data.id_documento
    ? 'Sincronizado con MongoDB Atlas · Clúster Prod-01'
    : 'Configura MONGODB_URI para sincronizar';
  // cards
  var res = data.resumen || {};
  var keys = Object.keys(res);
  if (keys.length) {
    document.getElementById('res-cards-wrap').style.display = 'block';
    document.getElementById('res-cards-grid').innerHTML = keys.map(function(k){
      return '<div class="rc"><div class="rc-lbl">'+k+'</div><div class="rc-val">'+Number(res[k]).toLocaleString('es-PE',{minimumFractionDigits:2,maximumFractionDigits:2})+'</div></div>';
    }).join('');
  }
  // AST
  setTimeout(function(){ drawASTsvg(tabla); }, 80);
}

function distRow(label, n, tot, color) {
  var pct = tot > 0 ? Math.round(n/tot*100) : 0;
  return '<div class="dist-row"><span class="dist-lbl">'+label+'</span>'
       + '<div class="dist-bw"><div class="dist-bf" style="width:'+pct+'%;background:'+color+'"></div></div>'
       + '<span class="dist-pct">'+pct+'%</span></div>';
}

function syntaxHL(json) {
  return json
    .replace(/("[\w]+")\s*:/g, '<span style="color:#89b4fa">$1</span>:')
    .replace(/:\s*(".*?")/g,   ': <span style="color:#a6e3a1">$1</span>')
    .replace(/:\s*(\d+\.?\d*)/g, ': <span style="color:#fab387">$1</span>');
}

// ── AST SVG DINÁMICO ──
function drawASTsvg(tabla) {
  var wrap = document.getElementById('ast-wrap');
  if (!tabla || !tabla.length) {
    wrap.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:40px 0;font-size:12px">Sin datos para mostrar</p>';
    return;
  }

  // Constantes de layout
  var NW = 120, NH = 32, VGAP = 56;
  // Cada instrucción ocupa un "slot" fijo en X.
  // El slot debe contener: [tipo] [gap] [valor/expr] con margen entre instrucciones.
  // Para cálculos también hay operandos debajo de expr, cada uno de NW.
  // Slot mínimo = NW*2 + 3 gaps de 20px + 30px margen entre instrucciones
  var SLOT = NW * 2 + 20 * 3 + 30;
  var n = tabla.length;
  var PAD = 40;
  var W = Math.max(800, n * SLOT + PAD * 2);

  // Filas Y (centros)
  var Y0 = 30 + NH/2;                  // PROGRAMA
  var Y1 = Y0 + NH + VGAP;             // nombre_variable
  var Y2 = Y1 + NH + VGAP;             // tipo  |  valor/expr(op)
  var Y3 = Y2 + NH + VGAP;             // operando_izq | operando_der  (solo calculos)
  var hasCalc = tabla.some(function(r){ return r.tipo === 'calculo'; });
  var H = (hasCalc ? Y3 + NH/2 + 30 : Y2 + NH/2 + 30);

  // ── helpers SVG ──
  function rect(cx, cy, w, h, fg, bg, radius) {
    radius = radius || 6;
    return '<rect x="'+(cx-w/2)+'" y="'+(cy-h/2)+'" width="'+w+'" height="'+h
         + '" rx="'+radius+'" fill="'+bg+'" stroke="#d1d5db" stroke-width="1.2"/>';
  }
  function txt(cx, cy, lbl, fg, fs, fw) {
    fs = fs || 11; fw = fw || 600;
    // Calcular cuántos chars caben (aprox 6.2px por char a 11px)
    var maxCh = Math.floor((NW - 12) / (fs * 0.62));
    var s = String(lbl);
    if (s.length > maxCh) s = s.substring(0, maxCh - 1) + '…';
    return '<text x="'+cx+'" y="'+cy+'" text-anchor="middle" dominant-baseline="central"'
         + ' font-size="'+fs+'" font-weight="'+fw+'" fill="'+fg+'"'
         + ' font-family="-apple-system,BlinkMacSystemFont,sans-serif">'+s+'</text>';
  }
  function node(cx, cy, w, lbl, fg, bg) {
    return rect(cx, cy, w, NH, fg, bg) + txt(cx, cy, lbl, fg);
  }
  function edge(x1, y1, x2, y2) {
    return '<line x1="'+Math.round(x1)+'" y1="'+Math.round(y1)
         + '" x2="'+Math.round(x2)+'" y2="'+Math.round(y2)
         + '" stroke="#cbd5e1" stroke-width="1.2"/>';
  }

  var rootX = W / 2;
  var svg = '<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'"'
          + ' xmlns="http://www.w3.org/2000/svg"'
          + ' style="display:block;font-family:-apple-system,sans-serif">';

  // ── Nodo raíz PROGRAMA ──
  svg += node(rootX, Y0, NW + 40, 'PROGRAMA', '#1e40af', '#dbeafe');

  tabla.forEach(function(r, i) {
    // Centro X del slot de esta instrucción
    var cx = PAD + i * SLOT + SLOT / 2;

    // Dentro del slot: tipo a la izquierda, valor/expr a la derecha
    // Cada uno centrado en su mitad del slot (con gap en medio)
    var GAP = 20;
    var lx = cx - GAP/2 - NW/2;   // centro del nodo izquierdo (tipo)
    var rx = cx + GAP/2 + NW/2;   // centro del nodo derecho (valor/expr)

    // ── Fila 1: nombre_variable ──
    svg += edge(rootX, Y0 + NH/2, cx, Y1 - NH/2);
    svg += node(cx, Y1, NW, r.nombre, '#1e293b', '#f1f5f9');

    // ── Fila 2: tipo | valor ──
    var tipoBg = r.tipo==='insumo' ? '#ede9fe' : r.tipo==='costo_empaque' ? '#fef3c7' : '#dcfce7';
    var tipoFg = r.tipo==='insumo' ? '#5b21b6' : r.tipo==='costo_empaque' ? '#92400e' : '#15803d';

    svg += edge(cx, Y1 + NH/2, lx, Y2 - NH/2);
    svg += node(lx, Y2, NW, r.tipo, tipoFg, tipoBg);

    svg += edge(cx, Y1 + NH/2, rx, Y2 - NH/2);

    if (r.tipo === 'calculo') {
      var opM = r.expresion.match(/([+\-*\/])/);
      var op  = opM ? opM[1] : '?';
      svg += node(rx, Y2, NW, 'expr(' + op + ')', '#1d4ed8', '#dbeafe');

      // ── Fila 3: operandos ──
      var parts = r.expresion.split(/[+\-*\/]/).map(function(s){ return s.trim(); }).filter(Boolean);
      // Los operandos se colocan debajo de rx, separados
      var SEP = NW + 16;
      var ox1 = rx - SEP/2;
      var ox2 = rx + SEP/2;
      if (parts.length >= 1) {
        svg += edge(rx, Y2 + NH/2, ox1, Y3 - NH/2);
        svg += node(ox1, Y3, NW, parts[0], '#334155', '#f8fafc');
      }
      if (parts.length >= 2) {
        svg += edge(rx, Y2 + NH/2, ox2, Y3 - NH/2);
        svg += node(ox2, Y3, NW, parts[1], '#334155', '#f8fafc');
      }
    } else {
      // insumo/costo: valor numérico directamente
      svg += node(rx, Y2, NW, String(r.valor), '#334155', '#f8fafc');
    }
  });

  svg += '</svg>';

  // El wrapper tiene altura fija + scroll horizontal
  wrap.style.overflowX = 'auto';
  wrap.style.overflowY = 'auto';
  wrap.style.maxHeight = '320px';
  wrap.innerHTML = svg;
}

function zoomAST(f) {
  astZoomFactor = Math.max(0.3, Math.min(2, astZoomFactor * f));
  if (lastData) drawASTsvg(lastData.tabla_de_simbolos || []);
}
function resetZoom() { astZoomFactor = 1; if (lastData) drawASTsvg(lastData.tabla_de_simbolos || []); }

function exportJSON() {
  if (!lastData) return;
  var blob = new Blob([JSON.stringify(lastData, null, 2)], {type:'application/json'});
  var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'compilacion_usil.json'; a.click();
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
    return Response(HTML_PAGE, mimetype='text/html')

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
