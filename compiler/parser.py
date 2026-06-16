"""
compiler/parser.py
==================
Analizador Sintáctico del minicompilador USIL 2026.

Implementa un parser recursivo descendente (Recursive Descent Parser)
para la siguiente Gramática Libre de Contexto (CFG):

    programa    → instruccion
    instruccion → tipo_reg IDENTIFIER '=' expresion
                | tipo_reg IDENTIFIER '=' NUMBER
    tipo_reg    → KW_INSUMO | KW_COSTO_EMPAQUE | KW_CALCULO

    expresion   → termino rest_expr
    rest_expr   → ('+' | '-') termino rest_expr
                | ε

    termino     → factor rest_term
    rest_term   → ('*' | '/') factor rest_term
                | ε

    factor      → NUMBER_INT
                | NUMBER_FLOAT
                | IDENTIFIER
                | '(' expresion ')'

Esta gramática garantiza:
  - Precedencia correcta (* / antes que + -)
  - Asociatividad por la izquierda
  - Soporte para expresiones anidadas con paréntesis
  - Identificadores como operandos (variables)

El parser trabaja con las 3 columnas del Excel por separado:
  - Tipo_Registro  → validado por `validar_tipo_registro`
  - Nombre_Variable → validado por `validar_nombre_variable`
  - Valor_Asignacion → validado por `parsear_valor`
"""

from typing import List, Optional
from .lexer import Token, ErrorLexico


class ErrorSintactico(Exception):
    """Excepción lanzada cuando la estructura sintáctica es inválida."""


# ---------------------------------------------------------------------------
# Nodos del Árbol de Sintaxis Abstracta (AST)
# ---------------------------------------------------------------------------

class NodoAST:
    """Clase base para todos los nodos del AST."""
    pass


class NodoNumero(NodoAST):
    def __init__(self, token: Token):
        self.token = token
        self.valor = float(token.valor)

    def __repr__(self):
        return f"Numero({self.valor})"


class NodoIdentificador(NodoAST):
    def __init__(self, token: Token):
        self.token = token
        self.nombre = token.valor

    def __repr__(self):
        return f"ID({self.nombre})"


class NodoBinario(NodoAST):
    def __init__(self, izquierda: NodoAST, operador: Token, derecha: NodoAST):
        self.izquierda = izquierda
        self.operador = operador
        self.derecha = derecha

    def __repr__(self):
        return f"BinOp({self.izquierda!r} {self.operador.valor} {self.derecha!r})"


class NodoAsignacion(NodoAST):
    def __init__(self, tipo_reg: str, nombre_var: str, expresion: NodoAST):
        self.tipo_reg = tipo_reg
        self.nombre_var = nombre_var
        self.expresion = expresion

    def __repr__(self):
        return f"Asignacion({self.tipo_reg}, {self.nombre_var} = {self.expresion!r})"


# ---------------------------------------------------------------------------
# Parser recursivo descendente
# ---------------------------------------------------------------------------

class Parser:
    """
    Parser recursivo descendente.

    Recibe una lista de Token del Lexer y construye el AST
    correspondiente a una expresión matemática.
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # --- Utilidades internas ---

    def _token_actual(self) -> Optional[Token]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _consumir(self, tipo_esperado: str) -> Token:
        token = self._token_actual()
        if token is None:
            raise ErrorSintactico(
                f"Se esperaba '{tipo_esperado}' pero se llegó al fin de la expresión."
            )
        if token.tipo != tipo_esperado:
            raise ErrorSintactico(
                f"Se esperaba token '{tipo_esperado}' pero se encontró "
                f"'{token.tipo}' ('{token.valor}') en columna {token.columna}."
            )
        self.pos += 1
        return token

    def _es_tipo(self, *tipos: str) -> bool:
        token = self._token_actual()
        return token is not None and token.tipo in tipos

    # --- Reglas de la gramática ---

    def parsear_expresion(self) -> NodoAST:
        """expresion → termino rest_expr"""
        nodo = self._parsear_termino()
        while self._es_tipo("OP_PLUS", "OP_MINUS"):
            op = self._token_actual()
            self.pos += 1
            derecha = self._parsear_termino()
            nodo = NodoBinario(nodo, op, derecha)
        return nodo

    def _parsear_termino(self) -> NodoAST:
        """termino → factor rest_term"""
        nodo = self._parsear_factor()
        while self._es_tipo("OP_MUL", "OP_DIV"):
            op = self._token_actual()
            self.pos += 1
            derecha = self._parsear_factor()
            nodo = NodoBinario(nodo, op, derecha)
        return nodo

    def _parsear_factor(self) -> NodoAST:
        """factor → NUMBER_INT | NUMBER_FLOAT | IDENTIFIER | '(' expresion ')'"""
        token = self._token_actual()

        if token is None:
            raise ErrorSintactico(
                "Se esperaba un número, identificador o '(' "
                "pero se llegó al fin de la expresión."
            )

        if token.tipo in ("NUMBER_INT", "NUMBER_FLOAT"):
            self.pos += 1
            return NodoNumero(token)

        if token.tipo == "IDENTIFIER":
            self.pos += 1
            return NodoIdentificador(token)

        # También aceptar palabras clave de dominio como identificadores
        if token.tipo in ("KW_COSTO_PROD", "KW_TOTAL"):
            self.pos += 1
            # Tratarlos como identificador para que el semántico los valide
            token_id = Token("IDENTIFIER", token.valor, token.columna)
            return NodoIdentificador(token_id)

        if token.tipo == "LPAREN":
            self.pos += 1
            nodo = self.parsear_expresion()
            self._consumir("RPAREN")
            return nodo

        raise ErrorSintactico(
            f"Token inesperado '{token.valor}' (tipo: {token.tipo}) "
            f"en columna {token.columna}. "
            "Se esperaba un número, variable o paréntesis."
        )

    def parsear(self) -> NodoAST:
        """
        Punto de entrada principal. Parsea la expresión completa
        y verifica que no queden tokens sin consumir.
        """
        if not self.tokens:
            raise ErrorSintactico("La expresión de valor está vacía.")

        nodo = self.parsear_expresion()

        token_restante = self._token_actual()
        if token_restante is not None:
            raise ErrorSintactico(
                f"Token inesperado '{token_restante.valor}' "
                f"al final de la expresión en columna {token_restante.columna}. "
                "Verifique la sintaxis de la expresión."
            )
        return nodo


# ---------------------------------------------------------------------------
# Funciones de validación por columna
# ---------------------------------------------------------------------------

def validar_tipo_registro(valor: str) -> str:
    """
    Valida el campo Tipo_Registro.
    Retorna el valor normalizado o lanza ErrorSintactico.
    """
    tipos_validos = {"insumo", "costo_empaque", "calculo"}
    valor_limpio = str(valor).strip().lower()
    if valor_limpio not in tipos_validos:
        raise ErrorSintactico(
            f"Tipo de registro inválido: '{valor}'. "
            f"Valores permitidos: {sorted(tipos_validos)}."
        )
    return valor_limpio


def validar_nombre_variable(valor: str) -> str:
    """
    Valida el campo Nombre_Variable.
    Retorna el nombre limpio o lanza ErrorSintactico.
    """
    import re
    valor_limpio = str(valor).strip()
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", valor_limpio):
        raise ErrorSintactico(
            f"Nombre de variable sintácticamente inválido: '{valor}'. "
            "Debe comenzar con letra o '_' y contener solo letras, "
            "números y guiones bajos."
        )
    return valor_limpio


def parsear_valor(tokens: List[Token]) -> NodoAST:
    """
    Punto de entrada del parser para el campo Valor_Asignacion.

    Parámetros
    ----------
    tokens : List[Token]
        Tokens producidos por el Lexer para la celda Valor_Asignacion.

    Retorna
    -------
    NodoAST
        Raíz del árbol de sintaxis abstracta.

    Lanza
    -----
    ErrorSintactico
        Si la estructura de la expresión no es válida.
    """
    parser = Parser(tokens)
    return parser.parsear()


def extraer_identificadores(nodo: NodoAST) -> List[str]:
    """
    Recorre el AST en profundidad y recolecta los nombres
    de todos los identificadores (variables) referenciados.

    Se usa en el analizador semántico para verificar
    la Tabla de Símbolos.
    """
    ids: List[str] = []

    if isinstance(nodo, NodoIdentificador):
        ids.append(nodo.nombre)
    elif isinstance(nodo, NodoBinario):
        ids.extend(extraer_identificadores(nodo.izquierda))
        ids.extend(extraer_identificadores(nodo.derecha))
    # NodoNumero no tiene identificadores

    return ids
