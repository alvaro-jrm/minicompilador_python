import os
import sys

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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Minicompilador USIL 2026</title>
<style>
  :root {
    --purple: #7c3aed; --purple-light: #ede9fe; --purple-mid: #a78bfa;
    --teal: #0f766e; --teal-light: #ccfbf1;
    --amber: #b45309; --amber-light: #fef3c7;
    --red: #dc2626; --red-light: #fee2e2;
    --green: #15803d; --green-light: #dcfce7;
    --gray: #374151; --gray-light: #f3f4f6; --gray-mid: #d1d5db;
    --border: #e5e7eb;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f9fafb; color: #111827; font-size: 14px; line-height: 1.6; }

  header { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
           color: #fff; padding: 28px 32px; }
  header h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
  header p  { font-size: 13px; opacity: .85; }
  header .badge { display:inline-block; background:rgba(255,255,255,.2);
                  border-radius:20px; padding:2px 12px; font-size:11px; margin-top:8px; }

  .container { max-width: 1100px; margin: 0 auto; padding: 24px 20px; }

  /* ---- Sección 1: Descripción ---- */
  .section-card { background:#fff; border:1px solid var(--border); border-radius:12px;
                  padding:24px; margin-bottom:20px; }
  .section-title { font-size:15px; font-weight:700; color:var(--purple);
                   border-bottom:2px solid var(--purple-light); padding-bottom:8px; margin-bottom:16px; }
  .section-num { display:inline-block; background:var(--purple); color:#fff;
                 border-radius:50%; width:24px; height:24px; text-align:center;
                 line-height:24px; font-size:12px; font-weight:700; margin-right:8px; }

  .process-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:12px; }
  .process-box { background:var(--gray-light); border-radius:8px; padding:16px;
                 border-left:4px solid var(--purple); }
  .process-box h4 { font-size:12px; font-weight:700; color:var(--gray); margin-bottom:8px;
                    text-transform:uppercase; letter-spacing:.5px; }
  .process-box p { font-size:13px; color:#4b5563; }

  .pipeline { display:flex; align-items:center; gap:8px; margin:16px 0; flex-wrap:wrap; }
  .pipe-step { background:var(--purple-light); color:var(--purple); border-radius:8px;
               padding:8px 16px; font-size:13px; font-weight:600; }
  .pipe-arrow { color:var(--purple-mid); font-size:18px; font-weight:700; }
  .pipe-step.success { background:var(--green-light); color:var(--green); }
  .pipe-step.error   { background:var(--red-light);   color:var(--red);   }

  /* ---- Sección 2: Upload ---- */
  .upload-area { border:2px dashed var(--purple-mid); border-radius:12px;
                 padding:32px; text-align:center; cursor:pointer;
                 transition:background .2s; background:var(--purple-light); }
  .upload-area:hover { background:#ddd6fe; }
  .upload-area.dragover { background:#c4b5fd; border-color:var(--purple); }
  .upload-icon { font-size:40px; margin-bottom:8px; }
  .upload-area h3 { font-size:15px; font-weight:600; color:var(--purple); }
  .upload-area p  { font-size:12px; color:#6b7280; margin-top:4px; }
  #fileInput { display:none; }
  .file-selected { background:var(--green-light); border-color:var(--green);
                   color:var(--green); font-weight:600; }
  .btn { display:inline-block; padding:10px 28px; border-radius:8px; font-size:14px;
         font-weight:600; cursor:pointer; border:none; transition:all .2s; }
  .btn-primary { background:var(--purple); color:#fff; width:100%; margin-top:16px;
                 padding:12px; font-size:15px; }
  .btn-primary:hover { background:#6d28d9; }
  .btn-primary:disabled { background:var(--gray-mid); cursor:not-allowed; }

  /* ---- Sección 3: Análisis ---- */
  .analysis-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }
  @media(max-width:800px){ .analysis-grid { grid-template-columns:1fr; } }

  .analysis-card { background:#fff; border:1px solid var(--border); border-radius:12px;
                   padding:20px; }
  .analysis-card h3 { font-size:13px; font-weight:700; text-transform:uppercase;
                      letter-spacing:.5px; margin-bottom:14px; padding-bottom:8px;
                      border-bottom:2px solid; }
  .card-lexico   h3 { color:var(--purple); border-color:var(--purple-light); }
  .card-sintactico h3 { color:var(--teal);   border-color:var(--teal-light); }
  .card-semantico h3 { color:var(--amber);  border-color:var(--amber-light); }

  table.analysis-table { width:100%; border-collapse:collapse; font-size:12px; }
  table.analysis-table th { background:var(--gray-light); padding:6px 8px;
                             text-align:left; font-weight:600; color:var(--gray); }
  table.analysis-table td { padding:5px 8px; border-bottom:1px solid var(--border); }
  table.analysis-table tr:last-child td { border-bottom:none; }

  .token-badge { display:inline-block; padding:2px 8px; border-radius:4px;
                 font-size:10px; font-weight:700; font-family:monospace; }
  .tok-kw  { background:#ede9fe; color:#5b21b6; }
  .tok-id  { background:#dbeafe; color:#1e40af; }
  .tok-num { background:#dcfce7; color:#166534; }
  .tok-op  { background:#fef3c7; color:#92400e; }
  .tok-par { background:#fce7f3; color:#9d174d; }

  /* árbol AST */
  .ast-tree { font-family:monospace; font-size:12px; line-height:1.8;
              background:var(--gray-light); border-radius:8px; padding:12px;
              overflow-x:auto; white-space:pre; }
  .ast-node-op   { color:var(--teal);   font-weight:700; }
  .ast-node-id   { color:var(--purple); }
  .ast-node-num  { color:var(--green);  }

  /* tabla de símbolos */
  .sym-row-insumo  td:first-child { color:var(--purple); font-weight:600; }
  .sym-row-costo   td:first-child { color:var(--amber);  font-weight:600; }
  .sym-row-calculo td:first-child { color:var(--teal);   font-weight:600; }

  /* ---- Resultado ---- */
  #resultado { display:none; }
  .result-ok    { background:var(--green-light); border:1px solid #86efac;
                  border-radius:10px; padding:16px; margin-bottom:16px; }
  .result-error { background:var(--red-light); border:1px solid #fca5a5;
                  border-radius:10px; padding:16px; margin-bottom:16px; }
  .result-ok h3    { color:var(--green); font-size:15px; margin-bottom:4px; }
  .result-error h3 { color:var(--red);   font-size:15px; margin-bottom:4px; }
  .error-fase { display:inline-block; background:#fee2e2; color:#b91c1c;
                border-radius:4px; padding:1px 8px; font-size:11px;
                font-weight:700; text-transform:uppercase; margin-right:6px; }

  .resumen-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
                  gap:12px; margin-top:16px; }
  .resumen-card { background:#fff; border:1px solid var(--border); border-radius:8px;
                  padding:12px 16px; }
  .resumen-card .label { font-size:11px; color:#6b7280; font-weight:600;
                         text-transform:uppercase; }
  .resumen-card .valor { font-size:20px; font-weight:700; color:var(--purple); }

  /* spinner */
  .spinner { display:none; width:24px; height:24px; border:3px solid rgba(255,255,255,.3);
             border-top-color:#fff; border-radius:50%; animation:spin .8s linear infinite;
             margin:0 auto; }
  @keyframes spin { to { transform:rotate(360deg); } }

  .regex-table { width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }
  .regex-table th { background:var(--purple-light); color:var(--purple);
                    padding:5px 8px; text-align:left; }
  .regex-table td { padding:5px 8px; border-bottom:1px solid var(--border);
                    font-family:monospace; }

  .cfg-box { background:var(--teal-light); border-radius:8px; padding:12px;
             font-family:monospace; font-size:12px; line-height:2;
             color:var(--teal); margin-top:8px; }

  .afnd-box { background:var(--amber-light); border-radius:8px; padding:12px;
              font-size:12px; color:var(--amber); margin-top:8px; }
  .afnd-box p { margin-bottom:4px; }

  footer { text-align:center; padding:24px; color:#9ca3af; font-size:12px; }
</style>
</head>
<body>

<header>
  <h1>⚙️ Minicompilador de Inventario</h1>
  <p>Taller de Manufactura — Validación y traducción de variables de producción</p>
  <span class="badge">USIL 2026 · Teoría de la Computación</span>
</header>

<div class="container">

  <!-- SECCIÓN 1: DESCRIPCIÓN DEL COMPILADOR -->
  <div class="section-card">
    <div class="section-title">
      <span class="section-num">1</span>
      Descripción del proceso compilador
    </div>

    <div class="process-grid">
      <div class="process-box">
        <h4>🏭 Proceso de entrada</h4>
        <p>El personal operativo del taller registra insumos, costos y cálculos de producción en un archivo Excel o CSV estructurado. El compilador lee cada fila como una instrucción de asignación.</p>
      </div>
      <div class="process-box">
        <h4>📤 Resultado generado</h4>
        <p>Si el archivo es 100% válido, genera un documento JSON con la Tabla de Símbolos resuelta y lo persiste en MongoDB Atlas. Si hay un error, reporta la fila y la fase exacta (léxico, sintáctico o semántico).</p>
      </div>
    </div>

    <p style="margin-top:16px; font-size:13px; color:#4b5563; font-weight:600;">Pipeline de compilación:</p>
    <div class="pipeline">
      <div class="pipe-step">📄 Archivo Excel/CSV</div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-step">🔤 Análisis Léxico</div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-step">📐 Análisis Sintáctico</div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-step">🧠 Análisis Semántico</div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-step success">✅ MongoDB Atlas</div>
    </div>

    <p style="font-size:13px; color:#4b5563; margin-top:12px;">
      <strong>Formato del archivo:</strong> tres columnas —
      <code style="background:#f3f4f6;padding:1px 6px;border-radius:4px;">Tipo_Registro</code>
      <code style="background:#f3f4f6;padding:1px 6px;border-radius:4px;">Nombre_Variable</code>
      <code style="background:#f3f4f6;padding:1px 6px;border-radius:4px;">Valor_Asignacion</code>
    </p>
  </div>

  <!-- SECCIÓN 2: CARGA DE ARCHIVO -->
  <div class="section-card">
    <div class="section-title">
      <span class="section-num">2</span>
      Ingreso de datos — cargar archivo
    </div>

    <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
      <div class="upload-icon">📂</div>
      <h3>Haz clic o arrastra tu archivo aquí</h3>
      <p>Formatos aceptados: .xlsx, .xls, .csv · Máximo 10 MB</p>
      <input type="file" id="fileInput" accept=".xlsx,.xls,.csv">
    </div>

    <button class="btn btn-primary" id="btnCompilar" disabled onclick="compilar()">
      <span id="btnText">Selecciona un archivo para compilar</span>
      <div class="spinner" id="spinner"></div>
    </button>
  </div>

  <!-- SECCIÓN 3: PROCESO INTERNO -->
  <div class="section-card">
    <div class="section-title">
      <span class="section-num">3</span>
      Proceso interno del compilador
    </div>

    <div class="analysis-grid">

      <!-- 3.1 LÉXICO -->
      <div class="analysis-card card-lexico">
        <h3>3.1 Análisis léxico</h3>

        <p style="font-size:12px;color:#4b5563;margin-bottom:10px;font-weight:600;">REGLAS — Tokens (agrupadores)</p>
        <table class="analysis-table">
          <tr><th>Token</th><th>Lexemas</th></tr>
          <tr><td><span class="token-badge tok-kw">KW_TIPO</span></td><td>insumo, costo_empaque, calculo</td></tr>
          <tr><td><span class="token-badge tok-id">IDENTIFIER</span></td><td>hilos_lana, ojos_seguridad, caja_entrega…</td></tr>
          <tr><td><span class="token-badge tok-num">NUMBER_INT</span></td><td>150, 300, 1, 0…</td></tr>
          <tr><td><span class="token-badge tok-num">NUMBER_FLOAT</span></td><td>3.50, 1.20, 0.75…</td></tr>
          <tr><td><span class="token-badge tok-op">OP_PLUS</span></td><td>+</td></tr>
          <tr><td><span class="token-badge tok-op">OP_MINUS</span></td><td>-</td></tr>
          <tr><td><span class="token-badge tok-op">OP_MUL</span></td><td>*</td></tr>
          <tr><td><span class="token-badge tok-op">OP_DIV</span></td><td>/</td></tr>
          <tr><td><span class="token-badge tok-par">LPAREN</span></td><td>(</td></tr>
          <tr><td><span class="token-badge tok-par">RPAREN</span></td><td>)</td></tr>
        </table>

        <p style="font-size:12px;color:#4b5563;margin:12px 0 6px;font-weight:600;">EXPRESIONES REGULARES</p>
        <table class="regex-table">
          <tr><th>Token</th><th>Patrón RE</th></tr>
          <tr><td>IDENTIFIER</td><td>[a-zA-Z_][a-zA-Z0-9_]*</td></tr>
          <tr><td>NUMBER_FLOAT</td><td>\d+\.\d+</td></tr>
          <tr><td>NUMBER_INT</td><td>\d+</td></tr>
          <tr><td>OP_PLUS</td><td>\+</td></tr>
          <tr><td>OP_MUL</td><td>\*</td></tr>
          <tr><td>KW_INSUMO</td><td>\binsumo\b</td></tr>
          <tr><td>KW_CALCULO</td><td>\bcalculo\b</td></tr>
        </table>

        <p style="font-size:12px;color:#4b5563;margin:12px 0 6px;font-weight:600;">AUTÓMATA (AFD resumen)</p>
        <div class="afnd-box">
          <p>• Estado q0 (inicial): espera letra/_ → IDENTIFIER</p>
          <p>• Estado q1: espera dígito → NUMBER_INT</p>
          <p>• Estado q2: tras punto → NUMBER_FLOAT</p>
          <p>• Estado q3: operador → OP_*</p>
          <p>• Estado q4 (aceptación): token completo</p>
        </div>

        <!-- tokens en vivo -->
        <p style="font-size:12px;color:#4b5563;margin:12px 0 6px;font-weight:600;">TOKENS DETECTADOS (última compilación)</p>
        <div id="tokensVivos" style="font-size:11px;color:#6b7280;font-style:italic;">
          Sube un archivo para ver los tokens...
        </div>
      </div>

      <!-- 3.2 SINTÁCTICO -->
      <div class="analysis-card card-sintactico">
        <h3>3.2 Análisis sintáctico</h3>

        <p style="font-size:12px;color:#4b5563;margin-bottom:8px;font-weight:600;">GRAMÁTICA LIBRE DE CONTEXTO (CFG)</p>
        <div class="cfg-box">programa   → instruccion*
instruccion→ tipo ID = expr
tipo       → insumo
           | costo_empaque
           | calculo

expr  → term rest_expr
rest_expr→ ('+' | '-') term rest_expr
         | ε

term  → factor rest_term
rest_term→ ('*' | '/') factor rest_term
         | ε

factor→ NUMBER
      | IDENTIFIER
      | '(' expr ')'</div>

        <p style="font-size:12px;color:#4b5563;margin:12px 0 6px;font-weight:600;">ÁRBOL SINTÁCTICO (última compilación)</p>
        <div class="ast-tree" id="astVivo">Sube un archivo para ver el árbol AST...</div>
      </div>

      <!-- 3.3 SEMÁNTICO / TRADUCCIÓN -->
      <div class="analysis-card card-semantico">
        <h3>3.3 Semántico · Traducción</h3>

        <p style="font-size:12px;color:#4b5563;margin-bottom:8px;font-weight:600;">TABLA DE SÍMBOLOS</p>
        <div id="tablaSimbolosViva" style="font-size:12px;color:#6b7280;font-style:italic;">
          Sube un archivo para ver la tabla de símbolos...
        </div>

        <p style="font-size:12px;color:#4b5563;margin:12px 0 6px;font-weight:600;">TRADUCCIONES GENERADAS</p>
        <div style="background:var(--amber-light);border-radius:8px;padding:10px;font-size:12px;">
          <div style="margin-bottom:4px;font-weight:600;color:var(--amber);">→ JSON (MongoDB)</div>
          <div id="jsonOutput" style="font-family:monospace;font-size:11px;color:#374151;white-space:pre-wrap;">
{ esperando compilación... }</div>
        </div>
      </div>

    </div>
  </div>

  <!-- RESULTADO -->
  <div id="resultado">
    <div id="resultadoInner"></div>

    <div class="section-card" id="resumenCards" style="display:none;">
      <div class="section-title">📊 Resumen de valores calculados</div>
      <div class="resumen-grid" id="resumenGrid"></div>
    </div>
  </div>

</div>

<footer>Minicompilador USIL 2026 · Teoría de la Computación · Taller de Manufactura</footer>

<script>
const uploadArea = document.getElementById('uploadArea');
const fileInput  = document.getElementById('fileInput');
const btnCompilar = document.getElementById('btnCompilar');
const btnText    = document.getElementById('btnText');
const spinner    = document.getElementById('spinner');
let archivoSeleccionado = null;

fileInput.addEventListener('change', e => {
  const f = e.target.files[0];
  if (f) seleccionarArchivo(f);
});

uploadArea.addEventListener('dragover', e => {
  e.preventDefault(); uploadArea.classList.add('dragover');
});
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', e => {
  e.preventDefault(); uploadArea.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) seleccionarArchivo(f);
});

function seleccionarArchivo(f) {
  archivoSeleccionado = f;
  uploadArea.classList.add('file-selected');
  uploadArea.innerHTML = `<div class="upload-icon">✅</div>
    <h3>${f.name}</h3>
    <p>${(f.size/1024).toFixed(1)} KB · Listo para compilar</p>`;
  btnCompilar.disabled = false;
  btnText.textContent = '⚙️ Compilar archivo';
}

async function compilar() {
  if (!archivoSeleccionado) return;

  btnCompilar.disabled = true;
  btnText.style.display = 'none';
  spinner.style.display = 'block';
  document.getElementById('resultado').style.display = 'none';

  const fd = new FormData();
  fd.append('archivo', archivoSeleccionado);

  try {
    const res  = await fetch('/compile', { method:'POST', body: fd });
    const data = await res.json();
    mostrarResultado(data, res.ok);
  } catch(err) {
    mostrarResultado({ status:'error', mensaje: 'Error de red: ' + err.message }, false);
  } finally {
    btnCompilar.disabled = false;
    btnText.style.display = 'inline';
    spinner.style.display = 'none';
  }
}

function mostrarResultado(data, ok) {
  const el = document.getElementById('resultadoInner');
  document.getElementById('resultado').style.display = 'block';

  if (data.status === 'ok' || data.status === 'ok_sin_persistencia') {
    const tabla = data.tabla_de_simbolos || [];
    const meta  = data.metadata || {};

    el.innerHTML = `
      <div class="result-ok">
        <h3>✅ Compilación exitosa</h3>
        <p>${data.mensaje || ''}</p>
        ${data.id_documento ? `<p style="font-size:12px;margin-top:4px;color:#166534;">ID MongoDB: <code>${data.id_documento}</code></p>` : ''}
        ${data.status==='ok_sin_persistencia' ? `<p style="font-size:12px;color:#92400e;margin-top:4px;">⚠️ ${data.advertencia}</p>`:''}
        <p style="font-size:12px;margin-top:4px;color:#166534;">
          Archivo: ${meta.archivo_origen || ''} · ${meta.filas_validas || 0} instrucciones procesadas
        </p>
      </div>`;

    // Tokens vivos
    let tokensHTML = '<div style="display:flex;flex-wrap:wrap;gap:4px;">';
    tabla.forEach(row => {
      const tipoColor = row.tipo==='insumo'?'tok-kw': row.tipo==='costo_empaque'?'tok-op':'tok-id';
      tokensHTML += `<span class="token-badge ${tipoColor}">${row.tipo.toUpperCase()}</span>`;
      tokensHTML += `<span class="token-badge tok-id">${row.nombre}</span>`;
      tokensHTML += `<span class="token-badge tok-num">${row.valor}</span>`;
    });
    tokensHTML += '</div>';
    document.getElementById('tokensVivos').innerHTML = tokensHTML;

    // AST vivo
    let astHTML = '';
    tabla.forEach(row => {
      if (row.tipo === 'calculo') {
        astHTML += `<span class="ast-node-op">ASIGNACION</span>\n`;
        astHTML += `  ├─ <span class="ast-node-id">ID</span>: ${row.nombre}\n`;
        astHTML += `  └─ <span class="ast-node-op">EXPR</span>: ${row.expresion}\n`;
        astHTML += `       └─ <span class="ast-node-num">val = ${row.valor}</span>\n\n`;
      }
    });
    document.getElementById('astVivo').innerHTML = astHTML || 'No hay expresiones de cálculo.';

    // Tabla de símbolos
    let symHTML = '<table class="analysis-table"><tr><th>Nombre</th><th>Tipo</th><th>Expresión</th><th>Valor</th></tr>';
    tabla.forEach(row => {
      const cls = row.tipo==='insumo'?'sym-row-insumo': row.tipo==='costo_empaque'?'sym-row-costo':'sym-row-calculo';
      symHTML += `<tr class="${cls}">
        <td><code>${row.nombre}</code></td>
        <td>${row.tipo}</td>
        <td style="font-family:monospace;font-size:11px;">${row.expresion}</td>
        <td><strong>${row.valor}</strong></td>
      </tr>`;
    });
    symHTML += '</table>';
    document.getElementById('tablaSimbolosViva').innerHTML = symHTML;

    // JSON output
    document.getElementById('jsonOutput').textContent =
      JSON.stringify(data.resumen || {}, null, 2);

    // Resumen cards
    const resumen = data.resumen || {};
    const keys = Object.keys(resumen);
    if (keys.length) {
      document.getElementById('resumenCards').style.display = 'block';
      let cardsHTML = '';
      keys.forEach(k => {
        cardsHTML += `<div class="resumen-card">
          <div class="label">${k}</div>
          <div class="valor">${Number(resumen[k]).toLocaleString('es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</div>
        </div>`;
      });
      document.getElementById('resumenGrid').innerHTML = cardsHTML;
    }

  } else {
    const fase = data.fase || 'error';
    const fila = data.fila ? ` · Fila ${data.fila}` : '';
    el.innerHTML = `
      <div class="result-error">
        <h3>❌ Error de compilación</h3>
        <p><span class="error-fase">${fase}${fila}</span>${data.mensaje || 'Error desconocido'}</p>
        ${data.filas_procesadas !== undefined
          ? `<p style="font-size:12px;margin-top:8px;color:#991b1b;">
              Filas procesadas antes del error: ${data.filas_procesadas}</p>` : ''}
        <p style="font-size:12px;margin-top:6px;color:#6b7280;">
          Corrija el archivo y vuelva a compilar.
        </p>
      </div>`;
    document.getElementById('resumenCards').style.display = 'none';
  }

  document.getElementById('resultado').scrollIntoView({ behavior:'smooth', block:'start' });
}
</script>
</body>
</html>"""


def _get_mongo_collection():
    if not MONGO_AVAILABLE:
        raise RuntimeError("pymongo no esta instalado.")
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI no configurada en Vercel Environment Variables.")
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
        raise ValueError(f"No se pudo leer el archivo: {e}")
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
            raise ErrorSintactico(
                f"Fila {fila_num}: '{tipo}' requiere un numero literal. Se encontro: '{valor_str}'"
            )
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
    return {
        "fila":      fila_num,
        "tipo":      tipo,
        "nombre":    nombre,
        "expresion": valor_str,
        "valor":     round(valor_num, 6),
    }


@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE)


@app.route("/compile", methods=["POST"])
def compilar():
    if "archivo" not in request.files:
        return jsonify({"status":"error","fase":"entrada",
                        "mensaje":"No se encontro el campo 'archivo'."}), 400
    archivo = request.files["archivo"]
    if not archivo.filename:
        return jsonify({"status":"error","fase":"entrada","mensaje":"Archivo sin nombre."}), 400
    try:
        df = _leer_archivo(archivo)
    except ValueError as e:
        return jsonify({"status":"error","fase":"lectura_archivo","mensaje":str(e)}), 400
    if df.empty:
        return jsonify({"status":"error","fase":"lectura_archivo","mensaje":"El archivo esta vacio."}), 400

    tabla = TablaSimbolos()
    filas_procesadas = []

    for idx, row in df.iterrows():
        fila_num   = idx + 2
        tipo_raw   = row.get("Tipo_Registro",    "")
        nombre_raw = row.get("Nombre_Variable",  "")
        valor_raw  = row.get("Valor_Asignacion", "")
        if pd.isna(tipo_raw) or str(tipo_raw).strip() == "":
            continue
        try:
            filas_procesadas.append(
                _compilar_fila(fila_num, tipo_raw, nombre_raw, valor_raw, tabla)
            )
        except ErrorLexico as e:
            return jsonify({"status":"error","fase":"lexico","fila":fila_num,
                            "mensaje":str(e),"filas_procesadas":len(filas_procesadas)}), 400
        except ErrorSintactico as e:
            return jsonify({"status":"error","fase":"sintactico","fila":fila_num,
                            "mensaje":str(e),"filas_procesadas":len(filas_procesadas)}), 400
        except ErrorSemantico as e:
            return jsonify({"status":"error","fase":"semantico","fila":fila_num,
                            "mensaje":str(e),"filas_procesadas":len(filas_procesadas)}), 400

    tabla_final = tabla.como_lista()
    resumen     = {e["nombre"]: e["valor"] for e in tabla_final}
    documento   = {
        "metadata": {
            "archivo_origen": archivo.filename,
            "total_filas":    len(df),
            "filas_validas":  len(filas_procesadas),
            "compilado_en":   datetime.now(timezone.utc).isoformat(),
        },
        "tabla_de_simbolos": tabla_final,
        "resumen": resumen,
    }

    try:
        col = _get_mongo_collection()
        result = col.insert_one(documento)
        id_insertado = str(result.inserted_id)
    except RuntimeError as e:
        return jsonify({"status":"ok_sin_persistencia","advertencia":str(e),
                        "tabla_de_simbolos":tabla_final,"resumen":resumen,
                        "metadata":documento["metadata"],
                        "mensaje":f"{len(filas_procesadas)} instruccion(es) compiladas."}), 200
    except Exception as e:
        return jsonify({"status":"error","fase":"base_de_datos",
                        "mensaje":f"Error MongoDB: {str(e)}"}), 500

    return jsonify({"status":"ok",
                    "mensaje":f"{len(filas_procesadas)} instruccion(es) compiladas exitosamente.",
                    "id_documento":id_insertado,
                    "tabla_de_simbolos":tabla_final,
                    "resumen":resumen,
                    "metadata":documento["metadata"]}), 200


@app.route("/historial", methods=["GET"])
def historial():
    try:
        col  = _get_mongo_collection()
        docs = list(col.find({},{"_id":1,"metadata":1,"resumen":1})
                       .sort("metadata.compilado_en",-1).limit(20))
        for d in docs:
            d["_id"] = str(d["_id"])
        return jsonify({"status":"ok","total":len(docs),"compilaciones":docs}), 200
    except Exception as e:
        return jsonify({"status":"error","mensaje":str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"status":"error","mensaje":f"Ruta no encontrada: {request.path}"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"status":"error","mensaje":f"Metodo no permitido en '{request.path}'."}), 405

@app.errorhandler(413)
def too_large(e):
    return jsonify({"status":"error","mensaje":"Archivo supera el limite de 10 MB."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
