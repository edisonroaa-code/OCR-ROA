"""
ROA OCR — Parser de Tablas a Markdown (TableParser)
===================================================
Reconstruye bloques de texto tabulares y datos multicolumna en tablas Markdown limpias.
"""
import re
from typing import List, Dict, Any, Optional

class TableParser:
    """
    Detector y formateador de tablas para conversión a Markdown.
    Identifica filas con múltiples espacios o tabulaciones y genera sintaxis Markdown (| col1 | col2 |).
    """

    def __init__(self, min_columns: int = 2, col_separator_spaces: int = 2):
        self.min_columns = min_columns
        self.col_separator_spaces = col_separator_spaces

    def is_table_row(self, line: str) -> bool:
        """Determina si una línea de texto parece pertenecer a una tabla."""
        if not line or len(line.strip()) < 5:
            return False
        
        # Si tiene tabulaciones o múltiples espacios consecutivos entre palabras
        parts = re.split(r'\t+|\s{' + str(self.col_separator_spaces) + r',}', line.strip())
        return len(parts) >= self.min_columns

    def parse_text_to_tables(self, text: str) -> str:
        """
        Procesa el texto completo y convierte bloques tabulares detectados a Markdown.
        """
        lines = text.split("\n")
        output_lines = []
        in_table = False
        table_buffer: List[List[str]] = []

        for line in lines:
            if self.is_table_row(line):
                columns = [col.strip() for col in re.split(r'\t+|\s{' + str(self.col_separator_spaces) + r',}', line.strip()) if col.strip()]
                if len(columns) >= self.min_columns:
                    table_buffer.append(columns)
                    in_table = True
                    continue

            # Si salimos de una sección de tabla, renderizar el buffer acumulado
            if in_table:
                output_lines.extend(self._format_table_markdown(table_buffer))
                table_buffer = []
                in_table = False

            output_lines.append(line)

        # Si el texto termina dentro de una tabla
        if in_table and table_buffer:
            output_lines.extend(self._format_table_markdown(table_buffer))

        return "\n".join(output_lines)

    def _format_table_markdown(self, rows: List[List[str]]) -> List[str]:
        if not rows:
            return []

        # Determinar número máximo de columnas
        max_cols = max(len(r) for r in rows)
        
        # Normalizar filas
        norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]

        markdown = []

        # Encabezado (primera fila)
        header = norm_rows[0]
        markdown.append("| " + " | ".join(header) + " |")

        # Separador Markdown (|---|---|)
        markdown.append("| " + " | ".join(["---"] * max_cols) + " |")

        # Filas de datos
        for row in norm_rows[1:]:
            markdown.append("| " + " | ".join(row) + " |")

        markdown.append("")  # Línea en blanco final
        return markdown
