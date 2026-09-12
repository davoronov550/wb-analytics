"""Начальная схема — такая, какой её оставил Django (T121)

Описывает **существующую** схему, а не желаемую, включая артефакты Django:
индексы `varchar_pattern_ops`, CHECK-ограничения от `PositiveIntegerField` и
внешний ключ `DEFERRABLE INITIALLY DEFERRED`. Обоснование — в докстринге
`adapters/outbound/persistence/models.py`.

Два сценария применения:

* **Чистая база** (dev, тесты, CI) — `alembic upgrade head` создаёт все четыре
  таблицы, включая `outbox`.
* **Приём существующей базы** при выводе сервиса в прод — схема каталога там
  уже есть, поэтому её не создают, а признают:

      alembic stamp head      # схема уже такая, ревизия просто фиксируется
      alembic check           # обязан показать только outbox

  `outbox` придётся создать отдельно: у Django её никогда не было. Это
  добавление таблицы, а не изменение данных.

Проверено, а не предположено: схема, поднятая этой миграцией, побайтово
совпадает с поднятой `manage.py migrate` (сравнение описаний трёх таблиц в
psql), а `alembic check` на копии базы с 500 товарами не нашёл по ним ни одной
операции, и контрольная сумма данных не изменилась.

Revision ID: 64e373ce205a
Revises:
Create Date: 2026-09-12 15:14:49.114878+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "64e373ce205a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_parse_job",
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("created >= 0", name="catalog_parse_job_created_check"),
        sa.CheckConstraint("updated >= 0", name="catalog_parse_job_updated_check"),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index(
        "catalog_par_query_3f40e7_idx", "catalog_parse_job", ["query", "status"], unique=False
    )
    op.create_index(
        "catalog_parse_job_status_8733e16e", "catalog_parse_job", ["status"], unique=False
    )
    op.create_index(
        "catalog_parse_job_status_8733e16e_like",
        "catalog_parse_job",
        [sa.literal_column("status varchar_pattern_ops")],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        "catalog_parse_job_task_id_15f25256_like",
        "catalog_parse_job",
        [sa.literal_column("task_id varchar_pattern_ops")],
        unique=False,
        postgresql_using="btree",
    )
    op.create_table(
        "catalog_search_query",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("text", sa.String(length=200), nullable=False),
        sa.Column("collected_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "collected_count >= 0", name="catalog_search_query_collected_count_check"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "catalog_search_query_text_86d92da4", "catalog_search_query", ["text"], unique=False
    )
    op.create_index(
        "catalog_search_query_text_86d92da4_like",
        "catalog_search_query",
        [sa.literal_column("text varchar_pattern_ops")],
        unique=False,
        postgresql_using="btree",
    )
    op.create_table(
        "catalog_product",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("wb_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("rating", sa.Numeric(precision=2, scale=1), nullable=False),
        sa.Column("reviews_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_query_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("reviews_count >= 0", name="catalog_product_reviews_count_check"),
        sa.ForeignKeyConstraint(
            ["source_query_id"],
            ["catalog_search_query.id"],
            name="catalog_product_source_query_id_1ce1d788_fk_catalog_s",
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wb_id", name="catalog_product_wb_id_key"),
    )
    op.create_index("catalog_pro_price_2d2a4c_idx", "catalog_product", ["price"], unique=False)
    op.create_index("catalog_pro_rating_67a263_idx", "catalog_product", ["rating"], unique=False)
    op.create_index(
        "catalog_pro_reviews_90b1f9_idx", "catalog_product", ["reviews_count"], unique=False
    )
    op.create_index(
        "catalog_pro_sale_pr_d20a45_idx", "catalog_product", ["sale_price"], unique=False
    )
    op.create_index(
        "catalog_product_source_query_id_1ce1d788",
        "catalog_product",
        ["source_query_id"],
        unique=False,
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("partition_key", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_outbox_unpublished",
        "outbox",
        ["id"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    # Every migration must be reversible: a rollback that cannot undo the
    # schema is not a rollback.
    op.drop_index(
        "ix_outbox_unpublished",
        table_name="outbox",
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.drop_table("outbox")
    op.drop_index("catalog_product_source_query_id_1ce1d788", table_name="catalog_product")
    op.drop_index("catalog_pro_sale_pr_d20a45_idx", table_name="catalog_product")
    op.drop_index("catalog_pro_reviews_90b1f9_idx", table_name="catalog_product")
    op.drop_index("catalog_pro_rating_67a263_idx", table_name="catalog_product")
    op.drop_index("catalog_pro_price_2d2a4c_idx", table_name="catalog_product")
    op.drop_table("catalog_product")
    op.drop_index(
        "catalog_search_query_text_86d92da4_like",
        table_name="catalog_search_query",
        postgresql_using="btree",
    )
    op.drop_index("catalog_search_query_text_86d92da4", table_name="catalog_search_query")
    op.drop_table("catalog_search_query")
    op.drop_index(
        "catalog_parse_job_task_id_15f25256_like",
        table_name="catalog_parse_job",
        postgresql_using="btree",
    )
    op.drop_index(
        "catalog_parse_job_status_8733e16e_like",
        table_name="catalog_parse_job",
        postgresql_using="btree",
    )
    op.drop_index("catalog_parse_job_status_8733e16e", table_name="catalog_parse_job")
    op.drop_index("catalog_par_query_3f40e7_idx", table_name="catalog_parse_job")
    op.drop_table("catalog_parse_job")
