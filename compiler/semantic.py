"""
compiler/semantic.py
====================
Analizador Semántico y Tabla de Símbolos del minicompilador USIL 2026.

Responsabilidades:
  1. Mantener la Tabla de Símbolos (TS) en memoria durante la compilación.
  2. Registrar variables de tipo 'insumo' y 'costo_empaque' con su valor literal.
  3. Evaluar expresiones de tipo 'calculo', verificando que cada variable
     referenciada ya exista en la TS (muro de contención semántico).
  4. Detectar y reportar:
       - Redeclaración de variable ya existente
       - Uso de variable no declarada
       - División por cero en expresiones constantes
       - Tipos de valor incompatibles (string donde se esperaba número)
"""

from typing import Dict, Any, List
from .parser import (
    NodoAST, NodoNumero, NodoIdentificador, NodoBinario,
    extraer_identificadores,
)


class ErrorSemantico(Exception):
    """Excepción lanzada por violaciones semánticas."""


# ---------------------------------------------------------------------------
# Tabla de Símbolos
# ---------------------------------------------------------------------------

class TablaSimbolos:
    """
    Tabla de Símbolos en memoria para el minicompilador.

    Cada entrada tiene la forma:
        {
            "nombre":    str,   # nombre de la variable
            "tipo":      str,   # 'insumo' | 'costo_empaque' | 'calculo'
            "valor":     float, # valor numérico resuelto
            "expresion": str,   # expresión original tal como vino del CSV
            "fila":      int,   # número de fila en el archivo fuente
        }
    """

    def __init__(self):
        # Diccionario principal: nombre_variable → entrada completa
        self._tabla: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Operaciones públicas
    # ------------------------------------------------------------------

    def registrar_insumo(self, nombre: str, valor_raw: str, fila: int) -> float:
        """
        Registra una variable de tipo 'insumo' con valor numérico literal.

        Lanza ErrorSemantico si:
          - La variable ya fue declarada.
          - El valor no es un número válido.
        """
        self._verificar_no_redeclarada(nombre, fila)
        valor_num = self._parsear_numero(valor_raw, nombre, fila)
        self._tabla[nombre] = {
            "nombre":    nombre,
            "tipo":      "insumo",
            "valor":     valor_num,
            "expresion": str(valor_raw).strip(),
            "fila":      fila,
        }
        return valor_num

    def registrar_costo_empaque(self, nombre: str, valor_raw: str, fila: int) -> float:
        """
        Registra una variable de tipo 'costo_empaque' con valor numérico literal.

        Lanza ErrorSemantico si:
          - La variable ya fue declarada.
          - El valor no es un número válido.
        """
        self._verificar_no_redeclarada(nombre, fila)
        valor_num = self._parsear_numero(valor_raw, nombre, fila)
        self._tabla[nombre] = {
            "nombre":    nombre,
            "tipo":      "costo_empaque",
            "valor":     valor_num,
            "expresion": str(valor_raw).strip(),
            "fila":      fila,
        }
        return valor_num

    def registrar_calculo(
        self,
        nombre: str,
        expresion_raw: str,
        ast: NodoAST,
        fila: int,
    ) -> float:
        """
        Evalúa y registra una variable de tipo 'calculo'.

        Verifica semánticamente que todas las variables usadas en la expresión
        existan en la Tabla de Símbolos antes de evaluar.

        Lanza ErrorSemantico si:
          - La variable ya fue declarada.
          - Se referencia una variable no declarada.
          - Ocurre una división por cero.
        """
        self._verificar_no_redeclarada(nombre, fila)

        # 1. Verificar todas las variables referenciadas existen en la TS
        ids_usados = extraer_identificadores(ast)
        for var_ref in ids_usados:
            if var_ref not in self._tabla:
                raise ErrorSemantico(
                    f"Fila {fila}: Error semántico — la variable '{var_ref}' "
                    f"utilizada en el cálculo de '{nombre}' no ha sido declarada. "
                    "Declare el insumo o costo_empaque antes de usarlo en un cálculo."
                )

        # 2. Evaluar la expresión con los valores de la TS
        valor_num = self._evaluar_ast(ast, nombre, fila)

        self._tabla[nombre] = {
            "nombre":    nombre,
            "tipo":      "calculo",
            "valor":     valor_num,
            "expresion": str(expresion_raw).strip(),
            "fila":      fila,
        }
        return valor_num

    def obtener(self, nombre: str) -> Dict[str, Any]:
        """Retorna la entrada de la Tabla de Símbolos para 'nombre'."""
        return self._tabla.get(nombre)

    def existe(self, nombre: str) -> bool:
        """Verifica si una variable ya está registrada."""
        return nombre in self._tabla

    def como_dict(self) -> Dict[str, Dict[str, Any]]:
        """Retorna una copia del estado completo de la Tabla de Símbolos."""
        return dict(self._tabla)

    def como_lista(self) -> List[Dict[str, Any]]:
        """Retorna la Tabla de Símbolos como lista ordenada por fila."""
        return sorted(self._tabla.values(), key=lambda e: e["fila"])

    def reset(self):
        """Limpia la Tabla de Símbolos (para reutilizar la instancia)."""
        self._tabla.clear()

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _verificar_no_redeclarada(self, nombre: str, fila: int):
        if nombre in self._tabla:
            entrada_previa = self._tabla[nombre]
            raise ErrorSemantico(
                f"Fila {fila}: Error semántico — la variable '{nombre}' "
                f"ya fue declarada en la fila {entrada_previa['fila']} "
                f"como tipo '{entrada_previa['tipo']}'. "
                "No se permiten redeclaraciones."
            )

    @staticmethod
    def _parsear_numero(valor_raw: str, nombre: str, fila: int) -> float:
        """Convierte valor_raw a float; lanza ErrorSemantico si no es numérico."""
        try:
            return float(str(valor_raw).strip())
        except (ValueError, TypeError):
            raise ErrorSemantico(
                f"Fila {fila}: Error semántico — el valor asignado a '{nombre}' "
                f"('{valor_raw}') no es un número válido. "
                "Los tipos 'insumo' y 'costo_empaque' solo aceptan literales numéricos."
            )

    def _evaluar_ast(self, nodo: NodoAST, nombre_calc: str, fila: int) -> float:
        """
        Evalúa recursivamente el AST usando los valores de la Tabla de Símbolos.
        """
        if isinstance(nodo, NodoNumero):
            return nodo.valor

        if isinstance(nodo, NodoIdentificador):
            # Ya verificamos existencia antes, pero por seguridad:
            if nodo.nombre not in self._tabla:
                raise ErrorSemantico(
                    f"Fila {fila}: Error semántico — variable '{nodo.nombre}' "
                    "no encontrada en la Tabla de Símbolos durante la evaluación."
                )
            return self._tabla[nodo.nombre]["valor"]

        if isinstance(nodo, NodoBinario):
            val_izq = self._evaluar_ast(nodo.izquierda, nombre_calc, fila)
            val_der = self._evaluar_ast(nodo.derecha, nombre_calc, fila)
            op = nodo.operador.valor

            if op == "+":
                return val_izq + val_der
            if op == "-":
                return val_izq - val_der
            if op == "*":
                return val_izq * val_der
            if op == "/":
                if val_der == 0:
                    raise ErrorSemantico(
                        f"Fila {fila}: Error semántico — división por cero "
                        f"en el cálculo de '{nombre_calc}'."
                    )
                return val_izq / val_der

        raise ErrorSemantico(
            f"Fila {fila}: Nodo AST desconocido durante la evaluación: {type(nodo)}"
        )
