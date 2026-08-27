"""CSV / XLSX writers for product export.

CSV is produced line-by-line (streamed via StreamingHttpResponse); XLSX is built
with openpyxl in write-only mode. Both are pure given an iterable of row dicts.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from io import BytesIO

from openpyxl import Workbook

# (row-dict key, column header)
COLUMNS: list[tuple[str, str]] = [
    ("wb_id", "wb_id"),
    ("name", "Название"),
    ("price", "Цена"),
    ("sale_price", "Цена со скидкой"),
    ("discount_abs", "Скидка"),
    ("rating", "Рейтинг"),
    ("reviews_count", "Отзывы"),
    ("query", "Запрос"),
]


# Excel and LibreOffice execute a cell whose text begins with one of these. Product
# names come from Wildberries, so an attacker who can list an item under a crafted
# name would otherwise get code execution in whoever opens the export.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value):
    """Neutralise spreadsheet formulas, leaving everything else untouched.

    Prefixing with an apostrophe is the standard mitigation: spreadsheets read it
    as "treat the rest as literal text" and do not display it as part of the value.
    """
    if isinstance(value, str) and value.startswith(_FORMULA_TRIGGERS):
        return "'" + value
    return value


class _Echo:
    """A file-like object whose write() returns the value (for streaming csv)."""

    def write(self, value: str) -> str:
        return value


def iter_csv(rows: Iterable[dict]) -> Iterator[str]:
    writer = csv.writer(_Echo())
    yield writer.writerow([header for _, header in COLUMNS])
    for row in rows:
        yield writer.writerow([_safe_cell(row.get(key)) for key, _ in COLUMNS])


def build_xlsx(rows: Iterable[dict]) -> bytes:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title="products")
    sheet.append([header for _, header in COLUMNS])
    for row in rows:
        sheet.append([_safe_cell(row.get(key)) for key, _ in COLUMNS])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
