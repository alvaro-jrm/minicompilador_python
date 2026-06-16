"""
compiler/__init__.py
Paquete del minicompilador USIL 2026.
"""
from .lexer import tokenizar, tokenizar_tipo_registro, tokenizar_nombre_variable, ErrorLexico
from .parser import parsear_valor, validar_tipo_registro, validar_nombre_variable, ErrorSintactico, extraer_identificadores
from .semantic import TablaSimbolos, ErrorSemantico

__all__ = [
    "tokenizar",
    "tokenizar_tipo_registro",
    "tokenizar_nombre_variable",
    "ErrorLexico",
    "parsear_valor",
    "validar_tipo_registro",
    "validar_nombre_variable",
    "ErrorSintactico",
    "extraer_identificadores",
    "TablaSimbolos",
    "ErrorSemantico",
]
