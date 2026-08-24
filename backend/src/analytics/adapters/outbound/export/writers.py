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


class _Echo:
    """A file-like object whose write() returns the value (for streaming csv)."""

    def write(self, value: str) -> str:
        return value


def iter_csv(rows: Iterable[dict]) -> Iterator[str]:
    writer = csv.writer(_Echo())
    yield writer.writerow([header for _, header in COLUMNS])
    for row in rows:
        yield writer.writerow([row.get(key) for key, _ in COLUMNS])


def build_xlsx(rows: Iterable[dict]) -> bytes:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title="products")
    sheet.append([header for _, header in COLUMNS])
    for row in rows:
        sheet.append([row.get(key) for key, _ in COLUMNS])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
