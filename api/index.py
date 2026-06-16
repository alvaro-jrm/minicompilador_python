import os
import sys

# -- Path fix para Vercel serverless --
# En Vercel, el working directory no es la raíz del proyecto.
# Agregamos la raíz explícitamente para que `compiler` sea importable.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import json
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from flask import Flask, request, jsonify

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

from compiler.lexer import tokenizar, tokenizar_nombre_variable, ErrorLexico
from compiler.parser import parsear_valor, validar_tipo_registro, validar_nombre_variable, ErrorSintactico
from compiler.semantic import TablaSimbolos, ErrorSemantico

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB  = os.environ.get("MONGODB_DB", "compilador_usil")
MONGODB_COL = os.environ.get("MONGODB_COL", "compilaciones")

COLUMNAS_REQUERIDAS = {"Tipo_Registro", "Nombre_Variable", "Valor_Asignacion"}


def _get_mongo_collection():
    if not MONGO_AVAILABLE:
        raise RuntimeError("pymongo no está instalado.")
    if not MONGODB_URI:
        raise RuntimeError(
            "MONGODB_URI no configurada. Agrégala en Vercel → Settings → Environment Variables."
        )
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
            raise ValueError(f"Formato no soportado: '{archivo.filename}'. Solo .csv, .xlsx o .xls")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo: {e}")

    df.columns = [c.strip() for c in df.columns]
    faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"Columnas faltantes: {sorted(faltantes)}. "
            f"Encontradas: {list(df.columns)}"
        )
    return df


def _compilar_fila(fila_num, tipo_raw, nombre_raw, valor_raw, tabla):
    # LÉXICO
    try:
        tipo = validar_tipo_registro(str(tipo_raw).strip())
    except ErrorLexico as e:
        raise ErrorLexico(f"Fila {fila_num} [Tipo_Registro]: {e}")

    try:
        nombre = validar_nombre_variable(str(nombre_raw).strip())
    except (ErrorLexico, ErrorSintactico) as e:
        raise ErrorLexico(f"Fila {fila_num} [Nombre_Variable]: {e}")

    valor_str = str(valor_raw).strip()
    try:
        tokens_valor = tokenizar(valor_str)
    except ErrorLexico as e:
        raise ErrorLexico(f"Fila {fila_num} [Valor_Asignacion]: {e}")

    # SINTÁCTICO
    if tipo in ("insumo", "costo_empaque"):
        if len(tokens_valor) != 1 or tokens_valor[0].tipo not in ("NUMBER_INT", "NUMBER_FLOAT"):
            raise ErrorSintactico(
                f"Fila {fila_num}: '{tipo}' requiere un número literal. "
                f"Se encontró: '{valor_str}'"
            )
        ast = None
    else:
        try:
            ast = parsear_valor(tokens_valor)
        except ErrorSintactico as e:
            raise ErrorSintactico(f"Fila {fila_num} [Valor_Asignacion]: {e}")

    # SEMÁNTICO
    if tipo == "insumo":
        valor_resuelto = tabla.registrar_insumo(nombre, valor_str, fila_num)
    elif tipo == "costo_empaque":
        valor_resuelto = tabla.registrar_costo_empaque(nombre, valor_str, fila_num)
    else:
        valor_resuelto = tabla.registrar_calculo(nombre, valor_str, ast, fila_num)

    return {
        "fila": fila_num,
        "tipo": tipo,
        "nombre": nombre,
        "expresion": valor_str,
        "valor_resuelto": round(valor_resuelto, 6),
    }


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "servicio": "Minicompilador USIL 2026",
        "version": "1.0.0",
        "rutas": {
            "POST /compile": "Compila un archivo Excel/CSV",
            "GET /historial": "Ultimas 20 compilaciones exitosas",
        },
    })


@app.route("/compile", methods=["POST"])
def compilar():
    if "archivo" not in request.files:
        return jsonify({
            "status": "error",
            "fase": "entrada",
            "mensaje": "No se encontró el campo 'archivo'. Envía el archivo con key='archivo' en form-data.",
        }), 400

    archivo = request.files["archivo"]
    if not archivo.filename:
        return jsonify({"status": "error", "fase": "entrada", "mensaje": "Archivo sin nombre."}), 400

    try:
        df = _leer_archivo(archivo)
    except ValueError as e:
        return jsonify({"status": "error", "fase": "lectura_archivo", "mensaje": str(e)}), 400

    if df.empty:
        return jsonify({"status": "error", "fase": "lectura_archivo", "mensaje": "El archivo está vacío."}), 400

    tabla = TablaSimbolos()
    filas_procesadas = []
    total_filas = len(df)

    for idx, row in df.iterrows():
        fila_num = idx + 2
        tipo_raw   = row.get("Tipo_Registro", "")
        nombre_raw = row.get("Nombre_Variable", "")
        valor_raw  = row.get("Valor_Asignacion", "")

        if pd.isna(tipo_raw) or str(tipo_raw).strip() == "":
            continue

        try:
            resultado = _compilar_fila(fila_num, tipo_raw, nombre_raw, valor_raw, tabla)
            filas_procesadas.append(resultado)
        except ErrorLexico as e:
            return jsonify({
                "status": "error", "fase": "lexico",
                "fila": fila_num, "mensaje": str(e),
                "filas_procesadas": len(filas_procesadas),
            }), 400
        except ErrorSintactico as e:
            return jsonify({
                "status": "error", "fase": "sintactico",
                "fila": fila_num, "mensaje": str(e),
                "filas_procesadas": len(filas_procesadas),
            }), 400
        except ErrorSemantico as e:
            return jsonify({
                "status": "error", "fase": "semantico",
                "fila": fila_num, "mensaje": str(e),
                "filas_procesadas": len(filas_procesadas),
            }), 400

    tabla_final = tabla.como_lista()
    documento = {
        "metadata": {
            "archivo_origen": archivo.filename,
            "total_filas": total_filas,
            "filas_validas": len(filas_procesadas),
            "compilado_en": datetime.now(timezone.utc).isoformat(),
        },
        "tabla_de_simbolos": tabla_final,
        "resumen": {e["nombre"]: e["valor_resuelto"] for e in tabla_final},
    }

    try:
        col = _get_mongo_collection()
        result = col.insert_one(documento)
        id_insertado = str(result.inserted_id)
    except RuntimeError as e:
        return jsonify({
            "status": "ok_sin_persistencia",
            "advertencia": str(e),
            "tabla_de_simbolos": tabla_final,
            "resumen": documento["resumen"],
            "metadata": documento["metadata"],
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error", "fase": "base_de_datos",
            "mensaje": f"Error MongoDB: {str(e)}",
        }), 500

    return jsonify({
        "status": "ok",
        "mensaje": f"{len(filas_procesadas)} instruccion(es) compiladas exitosamente.",
        "id_documento": id_insertado,
        "tabla_de_simbolos": tabla_final,
        "resumen": documento["resumen"],
        "metadata": documento["metadata"],
    }), 200


@app.route("/historial", methods=["GET"])
def historial():
    try:
        col = _get_mongo_collection()
        docs = list(col.find({}, {"_id": 1, "metadata": 1, "resumen": 1})
                    .sort("metadata.compilado_en", -1).limit(20))
        for d in docs:
            d["_id"] = str(d["_id"])
        return jsonify({"status": "ok", "total": len(docs), "compilaciones": docs}), 200
    except RuntimeError as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500
    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "mensaje": f"Ruta no encontrada: {request.path}"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"status": "error", "mensaje": f"Metodo '{request.method}' no permitido en '{request.path}'."}), 405

@app.errorhandler(413)
def too_large(e):
    return jsonify({"status": "error", "mensaje": "Archivo supera el limite de 10 MB."}), 413

@app.errorhandler(500)
def server_error(e):
    return jsonify({"status": "error", "mensaje": "Error interno del servidor.", "detalle": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
