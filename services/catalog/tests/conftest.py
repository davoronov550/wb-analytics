"""Фикстуры сервиса. Инфраструктурные берутся из платформы, чтобы девять
сервисов поднимали контейнеры одинаково."""

from wb_platform.testing import postgres_dsn

__all__ = ["postgres_dsn"]
