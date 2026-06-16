"""
api/index.py
============
Servidor Flask — Minicompilador USIL 2026
Desplegado como Serverless Function en Vercel.

Rutas expuestas:
  GET  /          → health check
  POST /compile   → procesa el archivo Excel/CSV y ejecuta el pipeline
                    léxico → sintáctico → semántico; si pasa, inserta en MongoDB.
  GET  /historial → lista los últimos 20 documentos compilados exitosamente.

Variables de entorno requeridas (configurar en Vercel Dashboard):
  MONGODB_URI     → Connection string de MongoDB Atlas
  MONGODB_DB      → Nombre de la base de datos (default: 'compilador_usil')
  MONGODB_COL     → Nombre de la colección (default: 'compilaciones')
"""

import os
import sys
import json
import traceback
from datetime import datetime, timezone
from io import BytesIO

# ---------------------------------------------------------------------------
# Ajuste de path para importar el paquete /compiler cuando corre en Vercel
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pandas as pd
from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from compiler.lexer import tokenizar, tokenizar_nombre_variable, ErrorLexico
from compiler.parser import parsear_valor, validar_tipo_registro, validar_nombre_variable, ErrorSintactico
from compiler.semantic import TablaSimbolos, ErrorSemantico

# ---------------------------------------------------------------------------
# Configuración de la aplicación
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB máximo por archivo

MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB  = os.environ.get("MONGODB_DB", "compilador_usil")
MONGODB_COL = os.environ.get("MONGODB_COL", "compilaciones")

COLUMNAS_REQUERIDAS = {"Tipo_Registro", "Nombre_Variable", "Valor_Asignacion"}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _get_mongo_collection():
    """
    Crea y retorna la colección de MongoDB.
    Lanza RuntimeError si MONGODB_URI no está configurada.
    """
    if not MONGODB_URI:
        raise RuntimeError(
            "La variable de entorno MONGODB_URI no está configurada. "
            "Agrégala en el panel de Vercel → Settings → Environment Variables."
        )
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return client[MONGODB_DB][MONGODB_COL]


def _leer_archivo(archivo) -> pd.DataFrame:
    """
    Lee el archivo subido (Excel o CSV) y retorna un DataFrame.
    Lanza ValueError con mensaje descriptivo si el formato no es válido.
    """
    nombre = archivo.filename.lower()
    contenido = archivo.read()

    try:
        if nombre.endswith(".csv"):
            df = pd.read_csv(BytesIO(contenido), dtype=str)
        elif nombre.endswith((".xlsx", ".xls")):
            df = pd.read_excel(BytesIO(contenido), dtype=str)
        else:
            raise ValueError(
                f"Formato de archivo no soportado: '{archivo.filename}'. "
                "Solo se aceptan .csv, .xlsx o .xls"
            )
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo '{archivo.filename}': {e}")

    # Normalizar nombres de columnas (quitar espacios extra)
    df.columns = [c.strip() for c in df.columns]

    # Verificar columnas requeridas
    faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El archivo no contiene las columnas requeridas: {sorted(faltantes)}. "
            f"Columnas encontradas: {list(df.columns)}"
        )

    return df


def _compilar_fila(
    fila_num: int,
    tipo_raw: str,
    nombre_raw: str,
    valor_raw: str,
    tabla: TablaSimbolos,
) -> dict:
    """
    Aplica el pipeline completo (léxico → sintáctico → semántico) a una fila.

    Retorna un dict con el resultado de la fila compilada:
        {
            "fila": int,
            "tipo": str,
            "nombre": str,
            "expresion": str,
            "valor_resuelto": float,
        }

    Lanza ErrorLexico, ErrorSintactico o ErrorSemantico según el nivel del error.
    """
    # ---- FASE 1: ANÁLISIS LÉXICO ----------------------------------------
    # Columna 1: Tipo_Registro
    try:
        tipo_str = str(tipo_raw).strip()
        tokenizar(tipo_str)             # tokenización de sanidad
        tipo = validar_tipo_registro(tipo_str)
    except ErrorLexico as e:
        raise ErrorLexico(f"Fila {fila_num} [Tipo_Registro]: {e}")

    # Columna 2: Nombre_Variable
    try:
        nombre_str = str(nombre_raw).strip()
        tokenizar_nombre_variable(nombre_str)  # validación léxica
        nombre = validar_nombre_variable(nombre_str)
    except ErrorLexico as e:
        raise ErrorLexico(f"Fila {fila_num} [Nombre_Variable]: {e}")

    # Columna 3: Valor_Asignacion — tokenizar la expresión completa
    valor_str = str(valor_raw).strip()
    try:
        tokens_valor = tokenizar(valor_str)
    except ErrorLexico as e:
        raise ErrorLexico(f"Fila {fila_num} [Valor_Asignacion]: {e}")

    # ---- FASE 2: ANÁLISIS SINTÁCTICO ------------------------------------
    # Los tipos 'insumo' y 'costo_empaque' aceptan solo un número literal
    if tipo in ("insumo", "costo_empaque"):
        if len(tokens_valor) != 1 or tokens_valor[0].tipo not in ("NUMBER_INT", "NUMBER_FLOAT"):
            raise ErrorSintactico(
                f"Fila {fila_num} [Valor_Asignacion]: "
                f"El tipo '{tipo}' requiere exactamente un valor numérico literal "
                f"(entero o decimal). Se encontró: '{valor_str}'"
            )
        ast = None  # no se necesita AST para literales
    else:
        # tipo == 'calculo': parsear expresión matemática completa
        try:
            ast = parsear_valor(tokens_valor)
        except ErrorSintactico as e:
            raise ErrorSintactico(f"Fila {fila_num} [Valor_Asignacion]: {e}")

    # ---- FASE 3: ANÁLISIS SEMÁNTICO ------------------------------------
    try:
        if tipo == "insumo":
            valor_resuelto = tabla.registrar_insumo(nombre, valor_str, fila_num)
        elif tipo == "costo_empaque":
            valor_resuelto = tabla.registrar_costo_empaque(nombre, valor_str, fila_num)
        else:
            valor_resuelto = tabla.registrar_calculo(nombre, valor_str, ast, fila_num)
    except ErrorSemantico:
        raise  # ya trae el mensaje con fila incluida

    return {
        "fila":           fila_num,
        "tipo":           tipo,
        "nombre":         nombre,
        "expresion":      valor_str,
        "valor_resuelto": round(valor_resuelto, 6),
    }


# ---------------------------------------------------------------------------
# Rutas Flask
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "servicio": "Minicompilador USIL 2026",
        "version": "1.0.0",
        "descripcion": (
            "Minicompilador para gestión de inventario y costos "
            "del taller de manufactura."
        ),
        "rutas": {
            "POST /compile":   "Compila un archivo Excel/CSV",
            "GET  /historial": "Últimas 20 compilaciones exitosas",
        },
    })


@app.route("/compile", methods=["POST"])
def compilar():
    """
    Endpoint principal de compilación.

    Recibe: multipart/form-data con campo 'archivo' (Excel o CSV).
    Retorna:
      - 200 OK   → compilación exitosa con Tabla de Símbolos e ID de MongoDB
      - 400      → error del archivo, léxico, sintáctico o semántico
      - 500      → error interno del servidor / MongoDB
    """
    # --- Validar que se envió un archivo ---
    if "archivo" not in request.files:
        return jsonify({
            "status":  "error",
            "fase":    "entrada",
            "mensaje": "No se encontró el campo 'archivo' en la solicitud. "
                       "Envía el archivo con el campo multipart llamado 'archivo'.",
        }), 400

    archivo = request.files["archivo"]
    if not archivo.filename:
        return jsonify({
            "status":  "error",
            "fase":    "entrada",
            "mensaje": "El archivo recibido no tiene nombre.",
        }), 400

    # --- Leer el archivo ---
    try:
        df = _leer_archivo(archivo)
    except ValueError as e:
        return jsonify({
            "status":  "error",
            "fase":    "lectura_archivo",
            "mensaje": str(e),
        }), 400

    if df.empty:
        return jsonify({
            "status":  "error",
            "fase":    "lectura_archivo",
            "mensaje": "El archivo está vacío o no contiene filas de datos.",
        }), 400

    # --- Pipeline de compilación fila a fila ---
    tabla = TablaSimbolos()
    filas_procesadas = []
    total_filas = len(df)

    for idx, row in df.iterrows():
        fila_num = idx + 2  # +2: encabezado (fila 1) + índice base 0

        tipo_raw  = row.get("Tipo_Registro",    "")
        nombre_raw = row.get("Nombre_Variable",  "")
        valor_raw  = row.get("Valor_Asignacion", "")

        # Saltar filas completamente vacías
        if pd.isna(tipo_raw) or str(tipo_raw).strip() == "":
            continue

        try:
            resultado_fila = _compilar_fila(
                fila_num, tipo_raw, nombre_raw, valor_raw, tabla
            )
            filas_procesadas.append(resultado_fila)

        except ErrorLexico as e:
            return jsonify({
                "status":           "error",
                "fase":             "lexico",
                "fila":             fila_num,
                "mensaje":          str(e),
                "filas_procesadas": len(filas_procesadas),
                "total_filas":      total_filas,
                "ayuda":            "Revise el contenido de la celda indicada.",
            }), 400

        except ErrorSintactico as e:
            return jsonify({
                "status":           "error",
                "fase":             "sintactico",
                "fila":             fila_num,
                "mensaje":          str(e),
                "filas_procesadas": len(filas_procesadas),
                "total_filas":      total_filas,
                "ayuda":            "Verifique que la expresión matemática sea válida.",
            }), 400

        except ErrorSemantico as e:
            return jsonify({
                "status":           "error",
                "fase":             "semantico",
                "fila":             fila_num,
                "mensaje":          str(e),
                "filas_procesadas": len(filas_procesadas),
                "total_filas":      total_filas,
                "ayuda": (
                    "Asegúrese de declarar las variables con 'insumo' o "
                    "'costo_empaque' antes de usarlas en un 'calculo'."
                ),
            }), 400

    # --- Compilación exitosa: construir documento para MongoDB ---
    tabla_final = tabla.como_lista()
    documento_mongo = {
        "metadata": {
            "archivo_origen": archivo.filename,
            "total_filas":    total_filas,
            "filas_validas":  len(filas_procesadas),
            "compilado_en":   datetime.now(timezone.utc).isoformat(),
        },
        "tabla_de_simbolos": tabla_final,
        "resumen": {
            entry["nombre"]: entry["valor_resuelto"]
            for entry in tabla_final
        },
    }

    # --- Insertar en MongoDB Atlas ---
    try:
        coleccion = _get_mongo_collection()
        resultado_insert = coleccion.insert_one(documento_mongo)
        id_insertado = str(resultado_insert.inserted_id)
    except RuntimeError as e:
        # MongoDB URI no configurada — devolver éxito igual pero sin persistencia
        return jsonify({
            "status":            "ok_sin_persistencia",
            "advertencia":       str(e),
            "tabla_de_simbolos": tabla_final,
            "resumen":           documento_mongo["resumen"],
            "metadata":          documento_mongo["metadata"],
        }), 200
    except PyMongoError as e:
        return jsonify({
            "status":  "error",
            "fase":    "base_de_datos",
            "mensaje": f"No se pudo guardar en MongoDB Atlas: {e}",
            "ayuda":   (
                "Verifique que la variable MONGODB_URI sea correcta, "
                "que el cluster esté activo y que la IP de Vercel esté "
                "en la lista blanca de MongoDB Atlas."
            ),
        }), 500

    # --- Respuesta final exitosa ---
    return jsonify({
        "status":            "ok",
        "mensaje":           f"Archivo compilado exitosamente. {len(filas_procesadas)} instrucción(es) procesadas.",
        "id_documento":      id_insertado,
        "tabla_de_simbolos": tabla_final,
        "resumen":           documento_mongo["resumen"],
        "metadata":          documento_mongo["metadata"],
    }), 200


@app.route("/historial", methods=["GET"])
def historial():
    """
    Retorna las últimas 20 compilaciones exitosas almacenadas en MongoDB.
    """
    try:
        coleccion = _get_mongo_collection()
        documentos = list(
            coleccion.find(
                {},
                {"_id": 1, "metadata": 1, "resumen": 1}
            ).sort("metadata.compilado_en", -1).limit(20)
        )
        # Convertir ObjectId a string
        for doc in documentos:
            doc["_id"] = str(doc["_id"])

        return jsonify({
            "status":       "ok",
            "total":        len(documentos),
            "compilaciones": documentos,
        }), 200

    except RuntimeError as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500
    except PyMongoError as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500


# ---------------------------------------------------------------------------
# Manejadores de error globales
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"status": "error", "mensaje": "Solicitud inválida.", "detalle": str(e)}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "mensaje": f"Ruta no encontrada: {request.path}"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({
        "status":  "error",
        "mensaje": f"Método '{request.method}' no permitido en '{request.path}'.",
    }), 405


@app.errorhandler(413)
def request_too_large(e):
    return jsonify({
        "status":  "error",
        "mensaje": "El archivo supera el límite de 10 MB.",
    }), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "status":  "error",
        "mensaje": "Error interno del servidor.",
        "detalle": str(e),
    }), 500


# ---------------------------------------------------------------------------
# Punto de entrada (desarrollo local)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    print(f"🚀  Minicompilador USIL 2026 corriendo en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
