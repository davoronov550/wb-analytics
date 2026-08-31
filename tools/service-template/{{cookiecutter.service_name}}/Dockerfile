# syntax=docker/dockerfile:1.7
#
# Build context is the REPOSITORY ROOT, not this directory:
#
#     docker build -f services/{{ cookiecutter.service_name }}/Dockerfile -t wb-{{ cookiecutter.service_name }} .
#
# The service depends on `wb-platform`, a workspace member under `libs/`, and
# on the root `uv.lock`. A context scoped to the service directory cannot see
# either, and the build fails in a way that reads like a dependency problem.

FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /bin/uv

# Use the interpreter already in the image instead of letting uv fetch one.
ENV UV_PYTHON_DOWNLOADS=0 \
    # Precompiled bytecode trades image size for startup latency — worth it
    # for a pod that Kubernetes may restart at any moment.
    UV_COMPILE_BYTECODE=1 \
    # Required with cache mounts: the default hardlink mode cannot span the
    # mount boundary and degrades to a warning plus a slow copy.
    UV_LINK_MODE=copy

WORKDIR /app

# Dependencies first, in their own layer. Bind-mounting the manifests rather
# than copying them means this layer is invalidated only when they change, not
# on every source edit.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=libs/platform/pyproject.toml,target=libs/platform/pyproject.toml \
    --mount=type=bind,source=services/{{ cookiecutter.service_name }}/pyproject.toml,target=services/{{ cookiecutter.service_name }}/pyproject.toml \
    uv sync --locked --no-install-project --no-dev --no-editable \
            --package wb-{{ cookiecutter.service_name }}

COPY libs/platform /app/libs/platform
COPY services/{{ cookiecutter.service_name }} /app/services/{{ cookiecutter.service_name }}
COPY pyproject.toml uv.lock /app/

# `--locked` fails when the lockfile drifts from the manifests, instead of
# silently resolving something the tests never saw.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --package wb-{{ cookiecutter.service_name }}


FROM python:3.13-slim AS runtime

# Non-root: a container escape should not begin with root in the namespace.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --no-create-home app

# Only the virtual environment. Source code stays out of the runtime image —
# `--no-editable` installed the packages into the venv, so nothing needs it.
COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
WORKDIR /app
EXPOSE {{ cookiecutter.http_port }}

# Liveness only — the process, not its dependencies. Kubernetes restarts what
# fails this, and restarting a pod does not fix a database.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:{{ cookiecutter.http_port }}/healthz', timeout=2).status == 200 else 1)"

# 127.0.0.1 rather than localhost in the probe above: the app binds 0.0.0.0
# (IPv4 only), while localhost resolves to ::1 first inside a container — the
# check would report connection refused against a perfectly healthy service.
CMD ["uvicorn", "{{ cookiecutter.package_name }}.main:app", \
     "--host", "0.0.0.0", "--port", "{{ cookiecutter.http_port }}", \
     "--loop", "uvloop", "--http", "httptools", "--no-access-log"]
