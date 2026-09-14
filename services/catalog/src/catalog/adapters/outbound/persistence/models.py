"""SQLAlchemy-таблицы каталога (T120).

Описывают **существующую** схему Django, а не желаемую. Начальная миграция
(T121) обязана лечь на копию прод-базы, ничего не пересоздавая, поэтому здесь
воспроизводятся и артефакты Django, которые сами по себе никому не нужны:

* индексы `varchar_pattern_ops` (`*_like`) — Django создаёт их для `CharField`
  с `db_index`, чтобы работал `LIKE 'префикс%'`;
* `CHECK (… >= 0)` от `PositiveIntegerField`;
* внешний ключ `DEFERRABLE INITIALLY DEFERRED`;
* имена индексов с хешами вида `catalog_pro_price_2d2a4c_idx`.

Не воспроизвести их — значит получить начальную миграцию, которая молча удаляет
три индекса и меняет ограничения. Улучшения идут отдельными миграциями (T122),
где их видно в диффе.

Схема снята с живой базы описанием таблиц в psql, а не выведена
Django: генератор и результат его работы расходятся в деталях вроде того, что
`unique=True` даёт UNIQUE-ограничение, а не уникальный индекс.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["Base", "ParseJobRow", "ProductRow", "SearchQueryRow", "service_metadata"]


class Base(DeclarativeBase):
    """Общая база таблиц каталога.

    Своя `MetaData`, отдельная от `outbox_metadata` платформы: таблица outbox
    принадлежит библиотеке и описана там один раз на девять сервисов.
    `alembic/env.py` передаёт обе последовательностью.
    """

    metadata = MetaData()


service_metadata = Base.metadata


class SearchQueryRow(Base):
    """Поисковый запрос или категория, для которых выполнялся сбор."""

    __tablename__ = "catalog_search_query"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    text_: Mapped[str] = mapped_column("text", String(200), nullable=False)
    collected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("collected_count >= 0", name="catalog_search_query_collected_count_check"),
        Index("catalog_search_query_text_86d92da4", "text"),
        Index(
            "catalog_search_query_text_86d92da4_like",
            text("text varchar_pattern_ops"),
            postgresql_using="btree",
        ),
    )


class ProductRow(Base):
    """Товар. `wb_id` — ключ идемпотентного upsert до миграции T122."""

    __tablename__ = "catalog_product"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    wb_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    reviews_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_query_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "catalog_search_query.id",
            name="catalog_product_source_query_id_1ce1d788_fk_catalog_s",
            # Django откладывает проверку до конца транзакции: это позволяет
            # вставлять товар и запрос в любом порядке внутри неё.
            deferrable=True,
            initially="DEFERRED",
            # Без `ondelete`: у Django `on_delete=SET_NULL` — правило
            # прикладного уровня, реализованное в Python, и в DDL оно не
            # попадает. Объявить его здесь значит завести в базе каскад,
            # которого в проде нет, и получить миграцию, меняющую ограничение
            # на копии прод-базы. Найдено сравнением схем, а не чтением модели.
            #
            # Следствие: удаление запроса со связанными товарами упрётся в
            # внешний ключ. Django обнуляет ссылки заранее, и репозиторий
            # сервиса обязан делать то же самое.
        ),
    )

    __table_args__ = (
        UniqueConstraint("wb_id", name="catalog_product_wb_id_key"),
        CheckConstraint("reviews_count >= 0", name="catalog_product_reviews_count_check"),
        # --- индексы, доставшиеся от Django -------------------------------
        # Однополевые, без tiebreaker. Оставлены: их удаление — отдельное
        # решение, которое принимается после T126, когда будет видно, какие
        # сортировки действительно приходят.
        Index("catalog_pro_price_2d2a4c_idx", "price"),
        Index("catalog_pro_sale_pr_d20a45_idx", "sale_price"),
        Index("catalog_pro_rating_67a263_idx", "rating"),
        Index("catalog_pro_reviews_90b1f9_idx", "reviews_count"),
        Index("catalog_product_source_query_id_1ce1d788", "source_query_id"),
        # --- индексы под пресеты интерфейса (T125) ------------------------
        # Каждый повторяет ORDER BY соответствующего пресета целиком, включая
        # направление каждого уровня и tiebreaker последним. Направления важны
        # буквально: индекс со смешанными порядками читается только в том
        # порядке, в котором создан, — прочесть его «наоборот» PostgreSQL может
        # лишь целиком, инвертировав все уровни сразу. Для
        # `(sale_price ASC, rating DESC)` обратное чтение даёт
        # `(sale_price DESC, rating ASC)`, то есть не тот порядок.
        #
        # Пять комбинаций вместо всех возможных: пять полей в произвольном
        # порядке и направлении дают сотни, и индексировать их все нельзя.
        # Остальные обслуживаются медленнее и логируются (T126).
        Index(
            "catalog_product_reviews_wb_idx",
            text("reviews_count DESC"),
            text("wb_id ASC"),
        ),
        Index(
            "catalog_product_rating_reviews_wb_idx",
            text("rating DESC"),
            text("reviews_count DESC"),
            text("wb_id ASC"),
        ),
        Index(
            "catalog_product_saleprice_rating_wb_idx",
            text("sale_price ASC"),
            text("rating DESC"),
            text("wb_id ASC"),
        ),
        Index(
            "catalog_product_price_wb_idx",
            text("price ASC"),
            text("wb_id ASC"),
        ),
        # Collation задана явно. Порядок текста от неё зависит, и индекс,
        # созданный с одной, а читаемый под `ORDER BY` с другой, просто не
        # используется — запрос тихо деградирует в сортировку всей выборки.
        # Имя локали совпадает с умолчанием базы: расхождение здесь не ошибка
        # времени сборки, а потеря производительности в проде.
        Index(
            "catalog_product_name_wb_idx",
            text('name COLLATE "en_US.utf8" ASC'),
            text("wb_id ASC"),
        ),
    )


class ParseJobRow(Base):
    """Состояние асинхронного прогона сбора."""

    __tablename__ = "catalog_parse_job"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Индекса по `query` отдельно нет: поле ведёт составной индекс ниже.
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created: Mapped[int] = mapped_column(Integer, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("created >= 0", name="catalog_parse_job_created_check"),
        CheckConstraint("updated >= 0", name="catalog_parse_job_updated_check"),
        Index("catalog_par_query_3f40e7_idx", "query", "status"),
        Index("catalog_parse_job_status_8733e16e", "status"),
        Index(
            "catalog_parse_job_status_8733e16e_like",
            text("status varchar_pattern_ops"),
            postgresql_using="btree",
        ),
        Index(
            "catalog_parse_job_task_id_15f25256_like",
            text("task_id varchar_pattern_ops"),
            postgresql_using="btree",
        ),
    )
