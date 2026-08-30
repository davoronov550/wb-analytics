#!/usr/bin/env bash
# Роль приложения и по одной базе на сервис.
#
# Отдельная база на сервис — это то, что делает распил настоящим: запрос из
# одного сервиса физически не может присоединить таблицу другого. Общая база
# вернула бы связанность, которую миграция как раз убирает.
#
# Почему .sh, а не .sql: psql НЕ подставляет свои переменные (:'name') внутри
# dollar-quoted блоков, поэтому идиома «DO $$ ... :'app_user' ... $$» молча
# отправляет на сервер литерал и падает. В shell-скрипте подстановка честная.
#
# Скрипт идемпотентен, но entrypoint запускает его только на ЧИСТОМ томе.
# На существующем томе применять вручную:
#   docker exec -i wb-analytics-dev-postgres-1 bash < 01-databases.sh

set -euo pipefail

APP_USER="${APP_DB_USER:-wb_app}"
APP_PASSWORD="${APP_DB_PASSWORD:-wbapp}"

DATABASES=(
    wb_catalog
    wb_ingestion
    wb_identity
    wb_scheduling
    wb_notifications
    wb_export
)

psql_super() {
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --no-password "$@"
}

echo "==> Роль приложения: $APP_USER"
# Без суперправ. CREATEDB нужен: testcontainers и pytest создают и удаляют
# временные базы на каждом прогоне.
psql_super --dbname postgres <<-SQL
	SELECT format('CREATE ROLE %I LOGIN CREATEDB PASSWORD %L', '$APP_USER', '$APP_PASSWORD')
	WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$APP_USER')
	\gexec
SQL

for db in "${DATABASES[@]}"; do
    echo "==> База: $db"
    psql_super --dbname postgres <<-SQL
		SELECT format('CREATE DATABASE %I OWNER %I', '$db', '$APP_USER')
		WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '$db')
		\gexec
	SQL

    # PUBLIC лишается права создавать объекты в схеме public: это должен уметь
    # владелец, а не любой подключившийся.
    psql_super --dbname "$db" <<-SQL
		REVOKE CREATE ON SCHEMA public FROM PUBLIC;
		GRANT ALL ON SCHEMA public TO "$APP_USER";
	SQL
done

echo "==> Готово: роль $APP_USER, баз — ${#DATABASES[@]}"
