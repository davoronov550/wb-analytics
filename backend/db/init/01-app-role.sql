-- Least-privilege role for the application.
--
-- The app used to connect as the bootstrap superuser, so any SQL injection or a
-- compromised process would have owned the whole cluster. `wb_app` can read and
-- write its own schema and run migrations, and nothing else.
--
-- Idempotent: safe to re-run against an existing database.
-- Runs automatically on a fresh volume (mounted into /docker-entrypoint-initdb.d/);
-- on an existing volume apply it by hand — init scripts do NOT re-run there.
--
-- The password below is a LOCAL DEV placeholder, like REDIS_PASSWORD's `devredis`.
-- Production must create this role with a real secret and never reuse this value.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wb_app') THEN
        CREATE ROLE wb_app LOGIN PASSWORD 'wbapp';
    END IF;
END
$$;

-- Explicitly strip every elevated attribute, even if the role predates this script.
ALTER ROLE wb_app NOSUPERUSER NOCREATEROLE NOBYPASSRLS NOREPLICATION;
ALTER ROLE wb_app PASSWORD 'wbapp';

-- pytest-django creates and drops a throwaway test database on every run, so the
-- app role needs CREATEDB. This grants no rights over anyone else's databases.
ALTER ROLE wb_app CREATEDB;

GRANT CONNECT ON DATABASE wb_analytics TO wb_app;

-- Django migrations issue DDL, so the role owns the schema it manages.
ALTER SCHEMA public OWNER TO wb_app;

-- On an existing volume the tables were created by the superuser; hand them over.
DO $$
DECLARE obj record;
BEGIN
    FOR obj IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I OWNER TO wb_app', obj.tablename);
    END LOOP;
    FOR obj IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER SEQUENCE public.%I OWNER TO wb_app', obj.sequencename);
    END LOOP;
    FOR obj IN SELECT viewname FROM pg_views WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER VIEW public.%I OWNER TO wb_app', obj.viewname);
    END LOOP;
END
$$;

-- Nobody gets implicit rights on the schema just by being able to connect.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO wb_app;
