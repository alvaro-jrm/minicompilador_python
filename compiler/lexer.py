"""
compiler/lexer.py
=================
Analizador Léxico del minicompilador para el taller de manufactura USIL 2026.

Reconoce los siguientes 17 tipos de token:
  1.  KW_INSUMO        → 'insumo'
  2.  KW_COSTO_EMPAQUE → 'costo_empaque'
  3.  KW_CALCULO       → 'calculo'
  4.  KW_COSTO_PROD    → 'costo_produccion'  (palabra clave de dominio)
  5.  KW_TOTAL         → 'total'             (prefijo de dominio)
  6.  OP_PLUS          → '+'
  7.  OP_MINUS         → '-'
  8.  OP_MUL           → '*'
  9.  OP_DIV           → '/'
  10. OP_ASSIGN        → '='  (asignación implícita entre columnas)
  11. LPAREN           → '('
  12. RPAREN           → ')'
  13. NUMBER_FLOAT     → número decimal, ej. 3.50
  14. NUMBER_INT       → número entero, ej. 150
  15. IDENTIFIER       → nombre de variable válido (snake_case)
  16. WHITESPACE       → espacios/tabulaciones (descartados)
  17. UNKNOWN          → carácter no reconocido (dispara error léxico)
"""

import re
from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Definición de tokens
# ---------------------------------------------------------------------------

# Orden importante: los patrones más específicos deben ir primero.
TOKEN_SPEC: List[tuple] = [
    # --- Palabras clave de tipo de registro ---
    ("KW_COSTO_EMPAQUE", r"\bcosto_empaque\b"),   # antes que IDENTIFIER
    ("KW_CALCULO",       r"\bcalculo\b"),
    ("KW_INSUMO",        r"\binsumo\b"),
    # --- Palabras clave de dominio (nombres de variable reservados) ---
    ("KW_COSTO_PROD",    r"\bcosto_produccion\b"),
    ("KW_TOTAL",         r"\btotal\b"),
    # --- Operadores ---
    ("OP_PLUS",          r"\+"),
    ("OP_MINUS",         r"-"),
    ("OP_MUL",           r"\*"),
    ("OP_DIV",           r"/"),
    ("OP_ASSIGN",        r"="),
    # --- Delimitadores ---
    ("LPAREN",           r"\("),
    ("RPAREN",           r"\)"),
    # --- Literales numéricos (float antes que int) ---
    ("NUMBER_FLOAT",     r"\b\d+\.\d+\b"),
    ("NUMBER_INT",       r"\b\d+\b"),
    # --- Identificadores de variable (snake_case) ---
    ("IDENTIFIER",       r"\b[a-zA-Z_][a-zA-Z0-9_]*\b"),
    # --- Ignorados ---
    ("WHITESPACE",       r"[ \t]+"),
    # --- Error léxico ---
    ("UNKNOWN",          r"."),
]

# Compilar el mega-patrón una sola vez
MASTER_PATTERN = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC)
)


@dataclass
class Token:
    tipo: str
    valor: str
    columna: int

    def __repr__(self) -> str:
        return f"Token({self.tipo}, {self.valor!r}, col={self.columna})"


class ErrorLexico(Exception):
    """Excepción lanzada cuando se encuentra un carácter no reconocido."""


# ---------------------------------------------------------------------------
# Función principal de tokenización
# ---------------------------------------------------------------------------

def tokenizar(texto: str) -> List[Token]:
    """
    Convierte una cadena de texto en una lista de Token.

    Parámetros
    ----------
    texto : str
        Cadena a analizar (contenido de la celda Valor_Asignacion o
        del campo Tipo_Registro / Nombre_Variable).

    Retorna
    -------
    List[Token]
        Lista de tokens reconocidos (sin WHITESPACE).

    Lanza
    -----
    ErrorLexico
        Si se encuentra un carácter desconocido.
    """
    tokens: List[Token] = []
    for match in MASTER_PATTERN.finditer(texto):
        tipo = match.lastgroup
        valor = match.group()
        columna = match.start()

        if tipo == "WHITESPACE":
            continue                       # descartar espacios
        if tipo == "UNKNOWN":
            raise ErrorLexico(
                f"Carácter no reconocido {valor!r} en columna {columna} "
                f"del texto: '{texto}'"
            )
        tokens.append(Token(tipo, valor, columna))

    return tokens


def tokenizar_tipo_registro(valor: str) -> Token:
    """
    Valida y tokeniza exclusivamente el campo Tipo_Registro.
    Solo acepta las palabras clave de tipo registral.

    Lanza ErrorLexico si el valor no es un tipo de registro válido.
    """
    valor_limpio = valor.strip().lower()
    tipos_validos = {
        "insumo":        "KW_INSUMO",
        "costo_empaque": "KW_COSTO_EMPAQUE",
        "calculo":       "KW_CALCULO",
    }
    if valor_limpio not in tipos_validos:
        raise ErrorLexico(
            f"Tipo de registro desconocido: '{valor}'. "
            f"Se esperaba uno de: {list(tipos_validos.keys())}"
        )
    return Token(tipos_validos[valor_limpio], valor_limpio, 0)


def tokenizar_nombre_variable(valor: str) -> Token:
    """
    Valida y tokeniza el campo Nombre_Variable.
    Debe ser un identificador válido en snake_case.

    Lanza ErrorLexico si el nombre contiene caracteres inválidos.
    """
    valor_limpio = valor.strip()
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", valor_limpio):
        raise ErrorLexico(
            f"Nombre de variable inválido: '{valor}'. "
            "Solo se permiten letras, números y guiones bajos, "
            "y no puede comenzar con un número."
        )
    # Verificar si es palabra clave de tipo — no se puede usar como variable
    palabras_reservadas = {"insumo", "costo_empaque", "calculo"}
    if valor_limpio.lower() in palabras_reservadas:
        raise ErrorLexico(
            f"'{valor_limpio}' es una palabra reservada y no puede "
            "usarse como nombre de variable."
        )
    return Token("IDENTIFIER", valor_limpio, 0)
