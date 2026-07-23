"""
ROA OCR — Enhanced Table Parser (TableParser v2)
===================================================
Reconstructs tabular blocks from OCR text into clean Markdown tables.

Improvements over v1:
  - Detects pipe-delimited tables (| col | col |)
  - Detects CSV-style content
  - Better column alignment using whitespace analysis
  - Handles merged/empty cells
  - Preserves non-table content untouched
  - Configurable sensitivity
"""
import re
from typing import List, Optional


class TableParser:
    """
    Detector and formatter for tabular data in OCR text.
    Identifies rows with structured spacing and converts to Markdown tables.
    """

    def __init__(self, min_columns: int = 2, col_separator_spaces: int = 2):
        self.min_columns = min_columns
        self.col_separator_spaces = col_separator_spaces

    def is_table_row(self, line: str) -> bool:
        """Determine if a line looks like part of a table."""
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            return False

        # Already pipe-delimited?
        if self._is_pipe_row(stripped):
            return True

        # Tab or multi-space separated
        parts = re.split(
            r'\t+|\s{' + str(self.col_separator_spaces) + r',}',
            stripped
        )
        parts = [p for p in parts if p.strip()]
        return len(parts) >= self.min_columns

    def _is_pipe_row(self, line: str) -> bool:
        """Check if line is already pipe-delimited."""
        if '|' not in line:
            return False
        parts = [p.strip() for p in line.split('|') if p.strip()]
        return len(parts) >= self.min_columns

    def _is_separator_row(self, line: str) -> bool:
        """Check if line is a Markdown table separator (|---|---|)."""
        stripped = line.strip()
        return bool(re.match(r'^[\|\s\-:]+$', stripped)) and '---' in stripped

    def parse_text_to_tables(self, text: str) -> str:
        """
        Process full text and convert detected tabular blocks to Markdown.
        Non-table content passes through untouched.
        """
        lines = text.split("\n")
        output_lines = []
        in_table = False
        table_buffer: List[List[str]] = []

        for line in lines:
            # Skip lines that are already Markdown table separators
            if self._is_separator_row(line):
                if in_table:
                    continue  # Will regenerate separator
                output_lines.append(line)
                continue

            # Check for pipe-delimited rows (pass through or normalize)
            if self._is_pipe_row(line.strip()):
                cols = [c.strip() for c in line.strip().split('|')]
                cols = [c for c in cols if c]  # Remove empty from leading/trailing |
                if len(cols) >= self.min_columns:
                    table_buffer.append(cols)
                    in_table = True
                    continue

            # Check for space/tab delimited rows
            if self.is_table_row(line):
                columns = self._split_row(line.strip())
                if len(columns) >= self.min_columns:
                    table_buffer.append(columns)
                    in_table = True
                    continue

            # If we were in a table and hit a non-table line, flush
            if in_table:
                output_lines.extend(self._format_table_markdown(table_buffer))
                table_buffer = []
                in_table = False

            output_lines.append(line)

        # Flush remaining table buffer
        if in_table and table_buffer:
            output_lines.extend(self._format_table_markdown(table_buffer))

        return "\n".join(output_lines)

    def _split_row(self, line: str) -> List[str]:
        """Split a line into columns using tabs or multi-spaces."""
        parts = re.split(
            r'\t+|\s{' + str(self.col_separator_spaces) + r',}',
            line.strip()
        )
        return [p.strip() for p in parts if p.strip()]

    def _format_table_markdown(self, rows: List[List[str]]) -> List[str]:
        """Format a list of row data into a Markdown table."""
        if not rows:
            return []

        # Determine max columns
        max_cols = max(len(r) for r in rows)

        # Normalize rows (pad short rows with empty strings)
        norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]

        # Calculate column widths for alignment
        col_widths = []
        for col_idx in range(max_cols):
            max_width = max(len(row[col_idx]) for row in norm_rows)
            col_widths.append(max(max_width, 3))

        markdown = []

        # Header
        header = norm_rows[0]
        header_line = "| " + " | ".join(
            h.ljust(col_widths[i]) for i, h in enumerate(header)
        ) + " |"
        markdown.append(header_line)

        # Separator
        sep_line = "| " + " | ".join(
            "-" * col_widths[i] for i in range(max_cols)
        ) + " |"
        markdown.append(sep_line)

        # Data rows
        for row in norm_rows[1:]:
            data_line = "| " + " | ".join(
                row[i].ljust(col_widths[i]) for i in range(max_cols)
            ) + " |"
            markdown.append(data_line)

        markdown.append("")  # Trailing blank line
        return markdown

    def detect_csv_block(self, text: str) -> Optional[str]:
        """
        Detect and convert CSV-like content (comma-separated) to Markdown tables.
        Only triggers when multiple consecutive lines have the same number of commas.
        """
        lines = text.split("\n")
        csv_buffer = []
        output_parts = []
        expected_cols = None

        for line in lines:
            commas = line.count(",")
            if commas >= 1:
                cols = [c.strip().strip('"') for c in line.split(",")]
                if expected_cols is None:
                    expected_cols = len(cols)
                    csv_buffer.append(cols)
                elif len(cols) == expected_cols:
                    csv_buffer.append(cols)
                else:
                    if len(csv_buffer) >= 2:
                        output_parts.extend(self._format_table_markdown(csv_buffer))
                    else:
                        for row in csv_buffer:
                            output_parts.append(", ".join(row))
                    csv_buffer = []
                    expected_cols = None
                    output_parts.append(line)
            else:
                if len(csv_buffer) >= 2:
                    output_parts.extend(self._format_table_markdown(csv_buffer))
                elif csv_buffer:
                    for row in csv_buffer:
                        output_parts.append(", ".join(row))
                csv_buffer = []
                expected_cols = None
                output_parts.append(line)

        if len(csv_buffer) >= 2:
            output_parts.extend(self._format_table_markdown(csv_buffer))
        elif csv_buffer:
            for row in csv_buffer:
                output_parts.append(", ".join(row))

        return "\n".join(output_parts)
