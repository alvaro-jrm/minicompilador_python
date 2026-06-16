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
<title>Minicompilador USIL 2026</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;color:#111827;font-size:14px;line-height:1.6}
header{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;padding:24px 32px}
header h1{font-size:20px;font-weight:700;margin-bottom:2px}
header p{font-size:12px;opacity:.85}
.badge{display:inline-block;background:rgba(255,255,255,.2);border-radius:20px;padding:2px 12px;font-size:11px;margin-top:6px}
.container{max-width:1140px;margin:0 auto;padding:20px 16px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:18px}
.sec-title{font-size:14px;font-weight:700;color:#4f46e5;border-bottom:2px solid #ede9fe;padding-bottom:6px;margin-bottom:14px}
.sec-num{display:inline-block;background:#4f46e5;color:#fff;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:11px;font-weight:700;margin-right:6px}
.pipeline{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:12px 0}
.pipe-step{background:#ede9fe;color:#4f46e5;border-radius:8px;padding:6px 14px;font-size:12px;font-weight:600}
.pipe-arrow{color:#a78bfa;font-weight:700}
.pipe-step.ok{background:#dcfce7;color:#15803d}

/* upload */
.upload-area{border:2px dashed #a78bfa;border-radius:10px;padding:28px;text-align:center;cursor:pointer;background:#ede9fe;transition:background .2s}
.upload-area:hover,.upload-area.drag{background:#ddd6fe}
.upload-area.selected{background:#dcfce7;border-color:#15803d}
.upload-icon{font-size:36px;margin-bottom:6px}
.upload-area h3{font-size:14px;font-weight:600;color:#4f46e5}
.upload-area p{font-size:12px;color:#6b7280}
.upload-area.selected h3{color:#15803d}
#fileInput{display:none}
.btn-compile{width:100%;margin-top:14px;padding:11px;background:#4f46e5;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:background .2s}
.btn-compile:hover{background:#4338ca}
.btn-compile:disabled{background:#9ca3af;cursor:not-allowed}
.spinner{display:none;width:20px;height:20px;border:3px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto}
@keyframes spin{to{transform:rotate(360deg)}}

/* 3 columnas análisis */
.analysis-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
@media(max-width:800px){.analysis-grid{grid-template-columns:1fr}}
.a-card{border:1px solid #e5e7eb;border-radius:10px;padding:16px;background:#fff}
.a-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding-bottom:6px;border-bottom:2px solid;margin-bottom:12px}
.lexico .a-title{color:#4f46e5;border-color:#ede9fe}
.sint   .a-title{color:#0f766e;border-color:#ccfbf1}
.sem    .a-title{color:#b45309;border-color:#fef3c7}

/* tablas análisis */
table.atbl{width:100%;border-collapse:collapse;font-size:11px}
table.atbl th{background:#f3f4f6;padding:5px 6px;text-align:left;font-weight:600;color:#374151}
table.atbl td{padding:4px 6px;border-bottom:1px solid #f3f4f6;font-family:monospace}
table.atbl tr:last-child td{border:none}
.tok{display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700;font-family:monospace}
.tok-kw{background:#ede9fe;color:#5b21b6}
.tok-id{background:#dbeafe;color:#1e40af}
.tok-num{background:#dcfce7;color:#166534}
.tok-op{background:#fef3c7;color:#92400e}
.tok-par{background:#fce7f3;color:#9d174d}

/* AFD */
.afd-wrap{width:100%;overflow-x:auto}
.state-c{cursor:pointer;transition:opacity .15s}
.state-c:hover{opacity:.8}
#state-info{background:#f9fafb;border-radius:6px;padding:8px 10px;font-size:11px;color:#4b5563;margin-top:8px;min-height:36px;border:1px solid #e5e7eb}

/* sim */
.sim-wrap{margin-top:10px;border-top:1px solid #e5e7eb;padding-top:10px}
#sim-input{width:100%;padding:7px 10px;border-radius:6px;border:1px solid #d1d5db;font-family:monospace;font-size:13px;background:#fff;color:#111827}
.sim-btns{display:flex;gap:6px;margin-top:6px}
.sim-btns button{padding:6px 14px;border-radius:6px;border:1px solid #d1d5db;background:#f9fafb;cursor:pointer;font-size:12px;color:#374151}
.sim-btns button:first-child{background:#4f46e5;color:#fff;border-color:#4f46e5}
#sim-chars{margin-top:8px;min-height:26px;display:flex;flex-wrap:wrap;gap:3px}
#sim-chars span{display:inline-block;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:12px;border:1px solid #e5e7eb}
#sim-chars span.cur{background:#ede9fe;border-color:#7c3aed;color:#4f46e5;font-weight:700}
#sim-chars span.done{background:#f3f4f6;color:#9ca3af}
#sim-result{font-size:12px;margin-top:6px;min-height:18px}

/* tabla transiciones */
.trans-wrap{overflow-x:auto;margin-top:8px}
table.trans{border-collapse:collapse;font-size:11px;width:100%}
table.trans th{padding:6px 8px;border:1px solid #e5e7eb;text-align:center;font-weight:600}
table.trans td{padding:6px 8px;border:1px solid #e5e7eb;text-align:center;font-family:monospace}
table.trans .th-inp{background:#f3f4f6;color:#374151}
table.trans .st-active{background:#ede9fe}
code.st{padding:1px 6px;border-radius:4px;font-size:11px}

/* cfg box */
.cfg-box{background:#f0fdf4;border-radius:6px;padding:10px;font-family:monospace;font-size:11px;line-height:1.9;color:#065f46;overflow-x:auto;white-space:pre}
/* ast */
.ast-box{background:#f0fdf4;border-radius:6px;padding:10px;font-family:monospace;font-size:11px;line-height:1.8;overflow-x:auto;white-space:pre;min-height:60px;color:#374151}
.ast-op{color:#0f766e;font-weight:700}
.ast-id{color:#4f46e5}
.ast-num{color:#15803d}

/* semántico */
.sym-tbl td:first-child{color:#4f46e5;font-weight:600}
.sym-tbl .row-cost td:first-child{color:#b45309}
.sym-tbl .row-calc td:first-child{color:#0f766e}
.json-out{background:#fef3c7;border-radius:6px;padding:10px;font-family:monospace;font-size:11px;white-space:pre-wrap;color:#374151;min-height:40px;overflow-x:auto}

/* tokens en vivo */
#tokens-live{min-height:28px;display:flex;flex-wrap:wrap;gap:3px;margin-top:4px}

/* resultado */
#resultado{display:none}
.res-ok{background:#dcfce7;border:1px solid #86efac;border-radius:8px;padding:14px;margin-bottom:14px}
.res-ok h3{color:#15803d;font-size:14px;margin-bottom:3px}
.res-err{background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:14px;margin-bottom:14px}
.res-err h3{color:#dc2626;font-size:14px;margin-bottom:3px}
.efase{display:inline-block;background:#fee2e2;color:#b91c1c;border-radius:4px;padding:1px 7px;font-size:10px;font-weight:700;text-transform:uppercase;margin-right:5px}
.resumen-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin-top:14px}
.res-card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px 14px}
.res-card .lbl{font-size:10px;color:#6b7280;font-weight:600;text-transform:uppercase}
.res-card .val{font-size:20px;font-weight:700;color:#4f46e5}

/* progress bar */
.prog-wrap{margin-top:10px}
.prog-bar{height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden;margin-bottom:4px}
.prog-fill{height:100%;background:#4f46e5;border-radius:3px;transition:width .4s}
.prog-steps{display:flex;gap:4px;font-size:11px}
.prog-step{padding:3px 10px;border-radius:12px;border:1px solid #e5e7eb;color:#6b7280;font-weight:500}
.prog-step.active{background:#ede9fe;border-color:#7c3aed;color:#4f46e5}
.prog-step.done{background:#dcfce7;border-color:#86efac;color:#15803d}
.prog-step.error{background:#fee2e2;border-color:#fca5a5;color:#dc2626}

footer{text-align:center;padding:20px;color:#9ca3af;font-size:11px}
</style>
</head>
<body>

<header>
  <h1>⚙️ Minicompilador de Inventario</h1>
  <p>Taller de Manufactura — Validación léxica, sintáctica y semántica de variables</p>
  <span class="badge">USIL 2026 · Teoría de la Computación</span>
</header>

<div class="container">

<!-- ══ SECCIÓN 1 ══ -->
<div class="card">
  <div class="sec-title"><span class="sec-num">1</span>Descripción del compilador</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
    <div style="background:#f9fafb;border-left:3px solid #7c3aed;padding:12px;border-radius:0 6px 6px 0">
      <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;margin-bottom:6px">Proceso de entrada</div>
      <p style="font-size:12px;color:#4b5563">El personal sube un Excel/CSV con columnas <code>Tipo_Registro</code>, <code>Nombre_Variable</code>, <code>Valor_Asignacion</code>. Cada fila es una instrucción de asignación.</p>
    </div>
    <div style="background:#f9fafb;border-left:3px solid #0f766e;padding:12px;border-radius:0 6px 6px 0">
      <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;margin-bottom:6px">Resultado generado</div>
      <p style="font-size:12px;color:#4b5563">Si el archivo es 100% válido → JSON con Tabla de Símbolos resuelta → MongoDB Atlas. Si hay error → fila y fase exacta.</p>
    </div>
  </div>
  <div class="pipeline">
    <div class="pipe-step">📄 Excel / CSV</div><div class="pipe-arrow">→</div>
    <div class="pipe-step">🔤 Léxico</div><div class="pipe-arrow">→</div>
    <div class="pipe-step">📐 Sintáctico</div><div class="pipe-arrow">→</div>
    <div class="pipe-step">🧠 Semántico</div><div class="pipe-arrow">→</div>
    <div class="pipe-step ok">✅ MongoDB Atlas</div>
  </div>
</div>

<!-- ══ SECCIÓN 2 ══ -->
<div class="card">
  <div class="sec-title"><span class="sec-num">2</span>Ingreso de datos — cargar archivo</div>
  <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()"
       ondragover="ev(event,'drag')" ondragleave="ev(event,'')" ondrop="drop(event)">
    <div class="upload-icon">📂</div>
    <h3>Haz clic o arrastra tu archivo aquí</h3>
    <p>Formatos: .xlsx · .xls · .csv — máximo 10 MB</p>
    <input type="file" id="fileInput" accept=".xlsx,.xls,.csv" onchange="pick(this.files[0])">
  </div>

  <!-- barra de progreso de fases -->
  <div class="prog-wrap" id="progWrap" style="display:none">
    <div class="prog-bar"><div class="prog-fill" id="progFill" style="width:0%"></div></div>
    <div class="prog-steps">
      <span class="prog-step" id="ps-lex">Léxico</span>
      <span class="prog-step" id="ps-sin">Sintáctico</span>
      <span class="prog-step" id="ps-sem">Semántico</span>
      <span class="prog-step" id="ps-db">MongoDB</span>
    </div>
  </div>

  <button class="btn-compile" id="btnC" disabled onclick="compilar()">
    <span id="btnT">Selecciona un archivo para compilar</span>
    <div class="spinner" id="sp"></div>
  </button>
</div>

<!-- ══ SECCIÓN 3 ══ -->
<div class="card">
  <div class="sec-title"><span class="sec-num">3</span>Proceso interno del compilador</div>
  <div class="analysis-grid">

    <!-- 3.1 LÉXICO -->
    <div class="a-card lexico">
      <div class="a-title">3.1 Análisis léxico</div>

      <p style="font-size:11px;font-weight:600;color:#374151;margin-bottom:6px">Tokens detectados (en vivo)</p>
      <div id="tokens-live"><span style="font-size:11px;color:#9ca3af;font-style:italic">Carga un archivo…</span></div>

      <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">Tabla de tokens</p>
      <table class="atbl">
        <tr><th>Token</th><th>Lexemas de ejemplo</th><th>RE</th></tr>
        <tr><td><span class="tok tok-kw">KW_TIPO</span></td><td>insumo, calculo…</td><td>\b(insumo|calculo|costo_empaque)\b</td></tr>
        <tr><td><span class="tok tok-id">IDENTIFIER</span></td><td>hilos_lana, total…</td><td>[a-zA-Z_][a-zA-Z0-9_]*</td></tr>
        <tr><td><span class="tok tok-num">NUMBER_INT</span></td><td>150, 300…</td><td>\d+</td></tr>
        <tr><td><span class="tok tok-num">NUMBER_FLOAT</span></td><td>3.50, 1.20…</td><td>\d+\.\d+</td></tr>
        <tr><td><span class="tok tok-op">OP_PLUS</span></td><td>+</td><td>\+</td></tr>
        <tr><td><span class="tok tok-op">OP_MINUS</span></td><td>-</td><td>-</td></tr>
        <tr><td><span class="tok tok-op">OP_MUL</span></td><td>*</td><td>\*</td></tr>
        <tr><td><span class="tok tok-op">OP_DIV</span></td><td>/</td><td>\/</td></tr>
        <tr><td><span class="tok tok-par">LPAREN</span></td><td>(</td><td>\(</td></tr>
        <tr><td><span class="tok tok-par">RPAREN</span></td><td>)</td><td>\)</td></tr>
      </table>

      <!-- AFD visual -->
      <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">AFD — Autómata Finito Determinista</p>
      <div class="afd-wrap">
        <svg width="100%" viewBox="0 0 460 300" role="img">
          <title>AFD del lexer</title>
          <defs>
            <marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </marker>
          </defs>
          <!-- flecha inicio -->
          <line x1="22" y1="150" x2="52" y2="150" stroke="#888" stroke-width="1.5" marker-end="url(#ar)" fill="none"/>
          <polygon points="16,146 16,154 8,150" fill="#888"/>
          <!-- q0 inicial doble -->
          <g class="state-c" id="sq0" onclick="qs('q0')">
            <circle cx="80" cy="150" r="26" fill="#E1F5EE" stroke="#0f766e" stroke-width="2"/>
            <circle cx="80" cy="150" r="20" fill="none" stroke="#0f766e" stroke-width="1" stroke-dasharray="3 2"/>
            <text x="80" y="150" text-anchor="middle" dominant-baseline="central" style="font-size:13px;font-weight:700;fill:#085041">q0</text>
          </g>
          <text x="80" y="184" text-anchor="middle" style="font-size:10px;fill:#6b7280">inicio</text>
          <!-- q1 IDENT/KW -->
          <g class="state-c" id="sq1" onclick="qs('q1')">
            <circle cx="220" cy="70" r="26" fill="#E1F5EE" stroke="#0f766e" stroke-width="1.5"/>
            <text x="220" y="70" text-anchor="middle" dominant-baseline="central" style="font-size:13px;font-weight:700;fill:#085041">q1</text>
          </g>
          <text x="220" y="104" text-anchor="middle" style="font-size:10px;fill:#6b7280">ident/kw</text>
          <!-- q2 INT -->
          <g class="state-c" id="sq2" onclick="qs('q2')">
            <circle cx="220" cy="155" r="26" fill="#EEEDFE" stroke="#534AB7" stroke-width="1.5"/>
            <text x="220" y="155" text-anchor="middle" dominant-baseline="central" style="font-size:13px;font-weight:700;fill:#3C3489">q2</text>
          </g>
          <text x="220" y="189" text-anchor="middle" style="font-size:10px;fill:#6b7280">int</text>
          <!-- q3 FLOAT -->
          <g class="state-c" id="sq3" onclick="qs('q3')">
            <circle cx="220" cy="240" r="26" fill="#EEEDFE" stroke="#534AB7" stroke-width="1.5"/>
            <text x="220" y="240" text-anchor="middle" dominant-baseline="central" style="font-size:13px;font-weight:700;fill:#3C3489">q3</text>
          </g>
          <text x="220" y="274" text-anchor="middle" style="font-size:10px;fill:#6b7280">float</text>
          <!-- q4 OP aceptacion -->
          <g class="state-c" id="sq4" onclick="qs('q4')">
            <circle cx="370" cy="90" r="26" fill="#FAEEDA" stroke="#854F0B" stroke-width="1.5"/>
            <circle cx="370" cy="90" r="20" fill="none" stroke="#854F0B" stroke-width="1"/>
            <text x="370" y="90" text-anchor="middle" dominant-baseline="central" style="font-size:13px;font-weight:700;fill:#633806">q4</text>
          </g>
          <text x="370" y="124" text-anchor="middle" style="font-size:10px;fill:#6b7280">op ✓</text>
          <!-- q5 aceptacion general -->
          <g class="state-c" id="sq5" onclick="qs('q5')">
            <circle cx="370" cy="205" r="26" fill="#E1F5EE" stroke="#0f766e" stroke-width="1.5"/>
            <circle cx="370" cy="205" r="20" fill="none" stroke="#0f766e" stroke-width="1"/>
            <text x="370" y="205" text-anchor="middle" dominant-baseline="central" style="font-size:13px;font-weight:700;fill:#085041">q5</text>
          </g>
          <text x="370" y="239" text-anchor="middle" style="font-size:10px;fill:#6b7280">token ✓</text>
          <!-- qERR -->
          <g class="state-c" id="sqe" onclick="qs('qe')">
            <circle cx="80" cy="260" r="22" fill="#FAECE7" stroke="#993C1D" stroke-width="1.5"/>
            <text x="80" y="260" text-anchor="middle" dominant-baseline="central" style="font-size:10px;font-weight:700;fill:#712B13">qERR</text>
          </g>

          <!-- transiciones -->
          <path d="M100 137 Q155 95 194 78" fill="none" stroke="#0f766e" stroke-width="1.2" marker-end="url(#ar)" opacity=".75"/>
          <text x="140" y="96" text-anchor="middle" style="font-size:9px;fill:#085041">letra/_</text>

          <line x1="106" y1="150" x2="194" y2="152" fill="none" stroke="#534AB7" stroke-width="1.2" marker-end="url(#ar)" opacity=".75"/>
          <text x="150" y="144" text-anchor="middle" style="font-size:9px;fill:#3C3489">dígito</text>

          <path d="M102 160 Q155 205 194 234" fill="none" stroke="#534AB7" stroke-width="1.2" marker-end="url(#ar)" opacity=".75"/>
          <text x="140" y="210" text-anchor="middle" style="font-size:9px;fill:#3C3489">   </text>

          <path d="M98 132 Q210 60 344 82" fill="none" stroke="#854F0B" stroke-width="1.2" marker-end="url(#ar)" opacity=".75"/>
          <text x="226" y="62" text-anchor="middle" style="font-size:9px;fill:#854F0B">+−*/( )</text>

          <line x1="80" y1="176" x2="80" y2="238" fill="none" stroke="#993C1D" stroke-width="1.2" marker-end="url(#ar)" opacity=".7" stroke-dasharray="3 2"/>
          <text x="64" y="210" text-anchor="middle" style="font-size:9px;fill:#993C1D">otro</text>

          <!-- loops q1,q2,q3 -->
          <path d="M208 44 Q218 22 232 36 Q242 50 234 62" fill="none" stroke="#0f766e" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
          <text x="232" y="26" text-anchor="middle" style="font-size:9px;fill:#085041">letra/díg/_</text>

          <path d="M210 130 Q220 112 232 122 Q240 132 232 142" fill="none" stroke="#534AB7" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
          <text x="244" y="118" text-anchor="middle" style="font-size:9px;fill:#3C3489">díg</text>

          <path d="M210 218 Q220 202 232 210 Q240 220 232 232" fill="none" stroke="#534AB7" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
          <text x="244" y="202" text-anchor="middle" style="font-size:9px;fill:#3C3489">díg</text>

          <!-- q2→q3 punto -->
          <line x1="220" y1="181" x2="220" y2="214" fill="none" stroke="#534AB7" stroke-width="1.2" marker-end="url(#ar)" opacity=".75"/>
          <text x="232" y="200" style="font-size:9px;fill:#3C3489">.</text>

          <!-- q1,q2,q3 → q5 -->
          <path d="M246 72 Q310 100 344 192" fill="none" stroke="#0f766e" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
          <text x="316" y="130" style="font-size:9px;fill:#085041">otro</text>
          <path d="M246 155 L344 200" fill="none" stroke="#534AB7" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
          <path d="M246 240 Q300 248 344 214" fill="none" stroke="#534AB7" stroke-width="1.2" marker-end="url(#ar)" opacity=".7"/>
        </svg>
      </div>
      <div id="state-info">Haz clic en un estado para ver su descripción.</div>

      <!-- simulador -->
      <div class="sim-wrap">
        <p style="font-size:11px;font-weight:600;color:#374151;margin-bottom:6px">Simulador de cadena</p>
        <input id="sim-input" placeholder="Ej: hilos_lana  |  3.50  |  +">
        <div class="sim-btns">
          <button onclick="simular()">Simular</button>
          <button onclick="resetSim()">Reset</button>
        </div>
        <div id="sim-chars"></div>
        <div id="sim-result"></div>
      </div>

      <!-- tabla de transiciones -->
      <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">Tabla de transiciones del AFD</p>
      <div class="trans-wrap">
        <table class="trans">
          <thead>
            <tr>
              <th class="th-inp">Estado</th>
              <th class="th-inp" style="background:#E1F5EE;color:#085041">letra/_</th>
              <th class="th-inp" style="background:#EEEDFE;color:#3C3489">dígito</th>
              <th class="th-inp" style="background:#EEEDFE;color:#3C3489">punto (.)</th>
              <th class="th-inp" style="background:#FAEEDA;color:#633806">+−*/( )</th>
              <th class="th-inp" style="background:#f3f4f6">esp/fin</th>
              <th class="th-inp" style="background:#FAECE7;color:#712B13">otro</th>
            </tr>
          </thead>
          <tbody>
            <tr><td><code class="st" style="background:#E1F5EE;color:#085041">→q0</code></td><td><code class="st" style="background:#E1F5EE;color:#085041">q1</code></td><td><code class="st" style="background:#EEEDFE;color:#3C3489">q2</code></td><td>—</td><td><code class="st" style="background:#FAEEDA;color:#633806">q4</code></td><td>—</td><td><code class="st" style="background:#FAECE7;color:#712B13">qERR</code></td></tr>
            <tr style="background:#f9fafb"><td><code class="st" style="background:#E1F5EE;color:#085041">q1</code></td><td><code class="st" style="background:#E1F5EE;color:#085041">q1↻</code></td><td><code class="st" style="background:#E1F5EE;color:#085041">q1↻</code></td><td>—</td><td><code class="st" style="background:#E1F5EE;color:#085041">q5*</code></td><td><code class="st" style="background:#E1F5EE;color:#085041">q5*</code></td><td><code class="st" style="background:#E1F5EE;color:#085041">q5*</code></td></tr>
            <tr><td><code class="st" style="background:#EEEDFE;color:#3C3489">q2</code></td><td>—</td><td><code class="st" style="background:#EEEDFE;color:#3C3489">q2↻</code></td><td><code class="st" style="background:#EEEDFE;color:#3C3489">q3</code></td><td><code class="st" style="background:#EEEDFE;color:#3C3489">q5*</code></td><td><code class="st" style="background:#EEEDFE;color:#3C3489">q5*</code></td><td><code class="st" style="background:#FAECE7;color:#712B13">qERR</code></td></tr>
            <tr style="background:#f9fafb"><td><code class="st" style="background:#EEEDFE;color:#3C3489">q3</code></td><td>—</td><td><code class="st" style="background:#EEEDFE;color:#3C3489">q3↻</code></td><td>—</td><td><code class="st" style="background:#EEEDFE;color:#3C3489">q5*</code></td><td><code class="st" style="background:#EEEDFE;color:#3C3489">q5*</code></td><td><code class="st" style="background:#FAECE7;color:#712B13">qERR</code></td></tr>
            <tr><td><code class="st" style="background:#FAEEDA;color:#633806">q4✓</code></td><td colspan="6" style="color:#9ca3af;font-style:italic;font-size:10px">Aceptación inmediata → emite OP / PAREN → regresa a q0</td></tr>
            <tr style="background:#f9fafb"><td><code class="st" style="background:#E1F5EE;color:#085041">q5✓</code></td><td colspan="6" style="color:#9ca3af;font-style:italic;font-size:10px">Aceptación → emite IDENTIFIER / KW / NUMBER → regresa a q0</td></tr>
            <tr><td><code class="st" style="background:#FAECE7;color:#712B13">qERR</code></td><td colspan="6" style="color:#dc2626;font-style:italic;font-size:10px">Trampa — lanza ErrorLexico con posición exacta</td></tr>
          </tbody>
        </table>
        <p style="font-size:10px;color:#9ca3af;margin-top:4px">↻ bucle self-loop · q5* devuelve carácter al buffer · → estado inicial · ✓ estado final (doble círculo)</p>
      </div>
    </div>

    <!-- 3.2 SINTÁCTICO -->
    <div class="a-card sint">
      <div class="a-title">3.2 Análisis sintáctico</div>
      <p style="font-size:11px;font-weight:600;color:#374151;margin-bottom:4px">Gramática Libre de Contexto (CFG)</p>
      <div class="cfg-box">programa   → instruccion*
instruccion→ tipo ID = expr
tipo       → insumo
           | costo_empaque
           | calculo

expr    → term rest_E
rest_E  → ('+' | '-') term rest_E | ε

term    → factor rest_T
rest_T  → ('*' | '/') factor rest_T | ε

factor  → NUMBER
        | IDENTIFIER
        | '(' expr ')'</div>

      <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">Árbol sintáctico (AST en vivo)</p>
      <div class="ast-box" id="ast-live">Carga un archivo para ver el AST…</div>

      <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">Instrucciones analizadas (en vivo)</p>
      <div id="inst-live" style="font-size:11px;color:#9ca3af;font-style:italic">Carga un archivo…</div>
    </div>

    <!-- 3.3 SEMÁNTICO -->
    <div class="a-card sem">
      <div class="a-title">3.3 Semántico · Traducción</div>
      <p style="font-size:11px;font-weight:600;color:#374151;margin-bottom:4px">Tabla de Símbolos (en vivo)</p>
      <div id="sym-live" style="font-size:11px;color:#9ca3af;font-style:italic">Carga un archivo…</div>

      <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">Traducción JSON → MongoDB</p>
      <div class="json-out" id="json-out">{ esperando compilación… }</div>

      <p style="font-size:11px;font-weight:600;color:#374151;margin:10px 0 4px">Estadísticas</p>
      <div id="stats-live" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px">
        <div style="background:#f9fafb;border-radius:6px;padding:8px;text-align:center"><div style="font-size:10px;color:#9ca3af">Insumos</div><div style="font-size:18px;font-weight:700;color:#4f46e5" id="cnt-ins">—</div></div>
        <div style="background:#f9fafb;border-radius:6px;padding:8px;text-align:center"><div style="font-size:10px;color:#9ca3af">Costos</div><div style="font-size:18px;font-weight:700;color:#b45309" id="cnt-cos">—</div></div>
        <div style="background:#f9fafb;border-radius:6px;padding:8px;text-align:center"><div style="font-size:10px;color:#9ca3af">Cálculos</div><div style="font-size:18px;font-weight:700;color:#0f766e" id="cnt-cal">—</div></div>
      </div>
    </div>

  </div>
</div>

<!-- ══ RESULTADO ══ -->
<div id="resultado">
  <div id="res-inner"></div>
  <div class="card" id="res-cards" style="display:none">
    <div class="sec-title">📊 Resumen de valores</div>
    <div class="resumen-grid" id="res-grid"></div>
  </div>
</div>

</div><!-- /container -->
<footer>Minicompilador USIL 2026 · Teoría de la Computación · Taller de Manufactura</footer>

<script>
/* ── upload ── */
let archivo = null;
function ev(e,cls){e.preventDefault();document.getElementById('uploadArea').className='upload-area '+(cls?'drag':'')}
function drop(e){e.preventDefault();pick(e.dataTransfer.files[0])}
function pick(f){
  if(!f)return;
  archivo=f;
  const ua=document.getElementById('uploadArea');
  ua.className='upload-area selected';
  ua.innerHTML=`<div class="upload-icon">✅</div><h3>${f.name}</h3><p>${(f.size/1024).toFixed(1)} KB</p>`;
  document.getElementById('btnC').disabled=false;
  document.getElementById('btnT').textContent='⚙️ Compilar archivo';
}

/* ── progreso ── */
function setPhase(phase){
  const map={lex:['ps-lex',25],sin:['ps-sin',50],sem:['ps-sem',75],db:['ps-db',100]};
  const phases=['ps-lex','ps-sin','ps-sem','ps-db'];
  const [activeId,pct]=map[phase]||['ps-lex',10];
  const idx=phases.indexOf(activeId);
  phases.forEach((id,i)=>{
    const el=document.getElementById(id);
    el.className='prog-step'+(i<idx?' done':i===idx?' active':'');
  });
  document.getElementById('progFill').style.width=pct+'%';
}
function setPhaseError(phase){
  const map={lexico:'ps-lex',sintactico:'ps-sin',semantico:'ps-sem',base_de_datos:'ps-db'};
  const id=map[phase];
  if(id) document.getElementById(id).className='prog-step error';
}

/* ── estado del AFD ── */
const SD={
  q0:{l:'q0 — Estado inicial',d:'Espera el primer carácter. Decide el camino según el símbolo leído.',c:'#085041'},
  q1:{l:'q1 — Identificador / palabra clave',d:'Consume letras, dígitos y _. Al terminar clasifica como KW_INSUMO, KW_CALCULO, KW_COSTO_EMPAQUE o IDENTIFIER.',c:'#085041'},
  q2:{l:'q2 — Número entero',d:'Consume dígitos. Si ve un punto "." pasa a q3. Con otro carácter acepta como NUMBER_INT.',c:'#3C3489'},
  q3:{l:'q3 — Parte decimal (float)',d:'Consume dígitos tras el punto. Al terminar acepta como NUMBER_FLOAT.',c:'#3C3489'},
  q4:{l:'q4 — Operador (aceptación inmediata)',d:'Lee un único operador (+−*/) o paréntesis. Emite OP_* o PAREN de inmediato.',c:'#633806'},
  q5:{l:'q5 — Aceptación general',d:'Estado final. Emite el token acumulado (IDENTIFIER/KW/NUMBER) y regresa a q0.',c:'#085041'},
  qe:{l:'qERR — Error léxico',d:'Carácter inválido ($, @, #…). El compilador frena y reporta la posición exacta.',c:'#712B13'},
};
function qs(id){
  const s=SD[id];if(!s)return;
  document.getElementById('state-info').innerHTML=`<strong style="color:${s.c}">${s.l}</strong><br>${s.d}`;
}

/* ── simulador ── */
function classify(t){
  const kw=['insumo','costo_empaque','calculo','costo_produccion','total'];
  if(kw.includes(t.toLowerCase()))return{tipo:'KEYWORD',c:'#5b21b6',bg:'#ede9fe'};
  if(/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(t))return{tipo:'IDENTIFIER',c:'#085041',bg:'#E1F5EE'};
  if(/^\d+$/.test(t))return{tipo:'NUMBER_INT',c:'#3C3489',bg:'#EEEDFE'};
  if(/^\d+\.\d+$/.test(t))return{tipo:'NUMBER_FLOAT',c:'#3C3489',bg:'#EEEDFE'};
  if(/^[+\-*\/]$/.test(t)||t==='('||t===')')return{tipo:'OPERADOR/PAREN',c:'#633806',bg:'#FAEEDA'};
  return{tipo:'ERROR',c:'#712B13',bg:'#FAECE7'};
}
function simular(){
  const raw=document.getElementById('sim-input').value.trim();if(!raw)return;
  const chars=raw.split('');
  const cc=document.getElementById('sim-chars');
  const rc=document.getElementById('sim-result');
  cc.innerHTML=chars.map((c,i)=>`<span id="ch${i}">${c===' '?'␣':c}</span>`).join('');
  rc.innerHTML='';
  let i=0;
  function step(){
    if(i>0)document.getElementById('ch'+(i-1))?.classList.replace('cur','done');
    if(i<chars.length){document.getElementById('ch'+i)?.classList.add('cur');i++;setTimeout(step,200);}
    else{
      const r=classify(raw);
      rc.innerHTML=r.tipo==='ERROR'
        ?`<span style="color:#993C1D">qERR — Error léxico: carácter inválido en "<b>${raw}</b>"</span>`
        :`<span style="background:${r.bg};color:${r.c};padding:2px 8px;border-radius:4px;font-weight:700;font-family:monospace;font-size:11px">${r.tipo}</span> → <code style="font-size:11px">"${raw}"</code> aceptado en q5`;
    }
  }
  step();
}
function resetSim(){
  document.getElementById('sim-chars').innerHTML='';
  document.getElementById('sim-result').innerHTML='';
  document.getElementById('sim-input').value='';
  document.getElementById('state-info').textContent='Haz clic en un estado para ver su descripción.';
}

/* ── compilar ── */
async function compilar(){
  if(!archivo)return;
  document.getElementById('btnC').disabled=true;
  document.getElementById('btnT').style.display='none';
  document.getElementById('sp').style.display='block';
  document.getElementById('resultado').style.display='none';
  document.getElementById('progWrap').style.display='block';
  setPhase('lex');

  const fd=new FormData();fd.append('archivo',archivo);
  try{
    setTimeout(()=>setPhase('sin'),400);
    setTimeout(()=>setPhase('sem'),800);
    const res=await fetch('/compile',{method:'POST',body:fd});
    const data=await res.json();
    if(data.status==='ok'||data.status==='ok_sin_persistencia'){
      setPhase('db');
      renderOk(data);
    } else {
      setPhaseError(data.fase||'lexico');
      renderErr(data);
    }
  }catch(e){
    renderErr({status:'error',mensaje:'Error de red: '+e.message});
  }finally{
    document.getElementById('btnC').disabled=false;
    document.getElementById('btnT').style.display='inline';
    document.getElementById('sp').style.display='none';
  }
}

/* ── render OK ── */
function renderOk(data){
  const tabla=data.tabla_de_simbolos||[];
  const meta=data.metadata||{};

  /* tokens en vivo */
  const tokMap={insumo:'tok-kw',costo_empaque:'tok-op',calculo:'tok-id'};
  document.getElementById('tokens-live').innerHTML=tabla.map(r=>{
    const cls=tokMap[r.tipo]||'tok-id';
    return `<span class="tok ${cls}">${r.tipo.toUpperCase()}</span>
            <span class="tok tok-id">${r.nombre}</span>
            <span class="tok tok-num">${r.valor}</span>`;
  }).join('');

  /* AST en vivo */
  let ast='';
  tabla.forEach(r=>{
    if(r.tipo==='calculo'){
      ast+=`<span class="ast-op">ASIGNACION</span>\n`;
      ast+=`  ├─ <span class="ast-id">ID</span>: ${r.nombre}\n`;
      ast+=`  └─ <span class="ast-op">EXPR</span>: ${r.expresion}\n`;
      ast+=`       └─ <span class="ast-num">eval = ${r.valor}</span>\n\n`;
    }
  });
  document.getElementById('ast-live').innerHTML=ast||'(sin expresiones de cálculo)';

  /* instrucciones analizadas */
  document.getElementById('inst-live').innerHTML=tabla.map((r,i)=>
    `<div style="font-family:monospace;font-size:11px;padding:2px 0;border-bottom:1px solid #f3f4f6">
      <span style="color:#9ca3af">F${r.fila}</span>
      <span style="color:#4f46e5;font-weight:600"> ${r.tipo}</span>
      <span style="color:#374151"> ${r.nombre}</span>
      <span style="color:#9ca3af"> = </span>
      <span style="color:#0f766e">${r.expresion}</span>
      <span style="color:#15803d;float:right">${r.valor}</span>
    </div>`
  ).join('');

  /* tabla de símbolos */
  document.getElementById('sym-live').innerHTML=
    `<table class="atbl sym-tbl">
      <tr><th>Nombre</th><th>Tipo</th><th>Expresión</th><th>Valor</th></tr>
      ${tabla.map(r=>{
        const cls=r.tipo==='insumo'?'':'row-'+(r.tipo==='costo_empaque'?'cost':'calc');
        return `<tr class="${cls}"><td>${r.nombre}</td><td>${r.tipo}</td><td>${r.expresion}</td><td><b>${r.valor}</b></td></tr>`;
      }).join('')}
    </table>`;

  /* JSON output */
  document.getElementById('json-out').textContent=JSON.stringify(data.resumen||{},null,2);

  /* estadísticas */
  document.getElementById('cnt-ins').textContent=tabla.filter(r=>r.tipo==='insumo').length;
  document.getElementById('cnt-cos').textContent=tabla.filter(r=>r.tipo==='costo_empaque').length;
  document.getElementById('cnt-cal').textContent=tabla.filter(r=>r.tipo==='calculo').length;

  /* resultado */
  document.getElementById('res-inner').innerHTML=
    `<div class="res-ok">
      <h3>✅ Compilación exitosa</h3>
      <p>${data.mensaje||''}</p>
      ${data.id_documento?`<p style="font-size:11px;margin-top:3px;color:#166534">ID MongoDB: <code>${data.id_documento}</code></p>`:''}
      ${data.status==='ok_sin_persistencia'?`<p style="font-size:11px;color:#92400e;margin-top:3px">⚠️ ${data.advertencia}</p>`:''}
      <p style="font-size:11px;margin-top:3px;color:#166534">Archivo: ${meta.archivo_origen||''} · ${meta.filas_validas||0} instrucciones</p>
    </div>`;

  /* cards de resumen */
  const resumen=data.resumen||{};
  const keys=Object.keys(resumen);
  if(keys.length){
    document.getElementById('res-cards').style.display='block';
    document.getElementById('res-grid').innerHTML=keys.map(k=>
      `<div class="res-card">
        <div class="lbl">${k}</div>
        <div class="val">${Number(resumen[k]).toLocaleString('es-PE',{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
      </div>`
    ).join('');
  }

  document.getElementById('resultado').style.display='block';
  document.getElementById('resultado').scrollIntoView({behavior:'smooth',block:'start'});
}

/* ── render ERROR ── */
function renderErr(data){
  const fase=data.fase||'error';
  const fila=data.fila?` · Fila ${data.fila}`:'';
  document.getElementById('res-inner').innerHTML=
    `<div class="res-err">
      <h3>❌ Error de compilación</h3>
      <p><span class="efase">${fase}${fila}</span>${data.mensaje||'Error desconocido'}</p>
      ${data.filas_procesadas!==undefined?`<p style="font-size:11px;margin-top:6px;color:#6b7280">Filas procesadas antes del error: ${data.filas_procesadas}</p>`:''}
    </div>`;
  document.getElementById('res-cards').style.display='none';
  document.getElementById('resultado').style.display='block';
  document.getElementById('resultado').scrollIntoView({behavior:'smooth',block:'start'});
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
        fila_num   = idx + 2
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
    resumen     = {e["nombre"]: e["valor"] for e in tabla_final}
    documento   = {
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
def method_not_allowed(e): return jsonify({"status":"error","mensaje":f"Método no permitido en '{request.path}'."}), 405
@app.errorhandler(413)
def too_large(e): return jsonify({"status":"error","mensaje":"Archivo supera 10 MB."}), 413

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
