"""The service template produces a working service (T034).

The check that matters is the placeholder sweep. cookiecutter copies a file
without rendering it when ``binaryornot`` decides the file is binary, and that
heuristic trips at roughly 30% high bytes in the first kilobyte — which a few
lines of Cyrillic comments in a short file reach easily. The generated service
then contains literal ``{{ cookiecutter.… }}`` and fails at import, or worse,
in a place that reads like a dependency problem.

It happened to ``pyproject.toml`` while this template was being written, and it
failed silently: cookiecutter reported success. Hence a test rather than a note
in the README.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cookiecutter.main import cookiecutter

TEMPLATE = Path(__file__).resolve().parent.parent / "service-template"

# Anything cookiecutter should have replaced. Matched loosely on purpose: a
# stray `{%` is as broken as a stray `{{`.
UNRENDERED = re.compile(r"\{\{\s*cookiecutter|\{%\s*(if|for|endif|endfor)\b")

TEXT_SUFFIXES = {".py", ".toml", ".yaml", ".yml", ".ini", ".mako", ".md", ".j2", ""}


def _generate(tmp_path: Path, **context: str) -> Path:
    defaults = {
        "service_name": "probe",
        "has_database": "yes",
        "has_kafka": "yes",
        "has_grpc": "no",
        "has_redis": "no",
    }
    cookiecutter(
        str(TEMPLATE),
        no_input=True,
        output_dir=str(tmp_path),
        extra_context={**defaults, **context},
    )
    return tmp_path / str({**defaults, **context}["service_name"])


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _generate(tmp_path_factory.mktemp("full"))


def _text_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            yield path


class TestRendering:
    def test_no_placeholder_survives_generation(self, generated: Path) -> None:
        """The failure this test exists for, and it is silent without it."""
        offenders = {
            str(path.relative_to(generated)): UNRENDERED.findall(
                path.read_text(encoding="utf-8", errors="replace")
            )
            for path in _text_files(generated)
            if UNRENDERED.search(path.read_text(encoding="utf-8", errors="replace"))
        }

        assert not offenders, f"unrendered template syntax: {offenders}"

    def test_the_sweep_can_actually_fail(self) -> None:
        """Guards the guard: a detector that never fires reports nothing."""
        assert UNRENDERED.search('name = "wb-{{ cookiecutter.service_name }}"')
        assert not UNRENDERED.search('name = "wb-catalog"')

    def test_service_name_reaches_every_layer(self, generated: Path) -> None:
        manifest = (generated / "pyproject.toml").read_text(encoding="utf-8")

        assert 'name = "wb-probe"' in manifest
        assert (generated / "src" / "probe" / "main.py").exists()


class TestStructure:
    @pytest.mark.parametrize(
        "relative",
        [
            "pyproject.toml",
            "Dockerfile",
            "helm-values.yaml",
            "src/probe/main.py",
            "src/probe/composition/container.py",
            "src/probe/domain/__init__.py",
            "src/probe/application/__init__.py",
            "src/probe/adapters/inbound/__init__.py",
            "src/probe/adapters/outbound/__init__.py",
            "tests/test_smoke.py",
            "tests/test_layering.py",
        ],
    )
    def test_expected_file_is_present(self, generated: Path, relative: str) -> None:
        assert (generated / relative).exists(), relative

    def test_the_package_is_marked_as_typed(self, generated: Path) -> None:
        """Without `py.typed`, everything importing this service sees it as
        untyped and `mypy` silently stops checking the boundary — the same
        defect `libs/platform` had, found there once and reintroduced here
        because the template never carried the marker.
        """
        assert (generated / "src" / "probe" / "py.typed").exists()

    def test_the_hexagon_is_the_starting_shape(self, generated: Path) -> None:
        """A service that starts flat never becomes layered afterwards."""
        package = generated / "src" / "probe"

        assert {"domain", "application", "adapters", "composition"} <= {
            child.name for child in package.iterdir() if child.is_dir()
        }

    def test_the_layering_check_ships_with_the_service(self, generated: Path) -> None:
        """The constraint is worth what its enforcement is worth."""
        content = (generated / "tests" / "test_layering.py").read_text(encoding="utf-8")

        assert "sqlalchemy" in content
        assert "fastapi" in content


class TestOptionalParts:
    def test_a_service_without_a_database_gets_no_alembic(self, tmp_path: Path) -> None:
        """Unused scaffolding is worse than none: an empty alembic/ eventually
        receives a migration that nothing runs."""
        service = _generate(tmp_path, service_name="stateless", has_database="no")

        assert not (service / "alembic").exists()
        assert not (service / "alembic.ini").exists()

    def test_alembic_sees_the_service_tables_from_the_start(self, generated: Path) -> None:
        """The wiring, not the tables. `service_metadata` is empty in a fresh
        service; connecting it to `target_metadata` later is the step someone
        forgets, and the symptom is an autogenerate that reports no changes for
        a table that was just added."""
        env = (generated / "alembic" / "env.py").read_text(encoding="utf-8")
        models = generated / "src" / "probe" / "adapters" / "outbound" / "persistence" / "models.py"

        assert models.exists()
        assert "target_metadata = [service_metadata, outbox_metadata]" in env
        assert "service_metadata" in models.read_text(encoding="utf-8")

    def test_a_service_with_a_database_gets_its_own_history(self, generated: Path) -> None:
        """One history per service — a shared one would couple deploys."""
        assert (generated / "alembic" / "env.py").exists()
        assert (generated / "alembic" / "versions").is_dir()

    def test_extras_follow_the_answers(self, tmp_path: Path) -> None:
        """A spare extra pulls a driver into the image and its CVE surface."""
        minimal = _generate(tmp_path, service_name="minimal", has_database="no", has_kafka="no")
        manifest = (minimal / "pyproject.toml").read_text(encoding="utf-8")

        assert "db" not in _extras(manifest)
        assert "kafka" not in _extras(manifest)
        assert "web" in _extras(manifest)

    def test_kafka_does_not_drag_redis_along(self, tmp_path: Path) -> None:
        """The two were one flag, so every Kafka service carried the Redis
        driver — and, worse, refused to start without `REDIS_DSN`, because the
        composition root built `RedisSettings()` in the same branch. Found by
        generating the first real service, not by this suite, which is why the
        assertion is now here."""
        service = _generate(tmp_path, service_name="kafkaonly", has_kafka="yes", has_redis="no")
        manifest = (service / "pyproject.toml").read_text(encoding="utf-8")
        container = (service / "src" / "kafkaonly" / "composition" / "container.py").read_text(
            encoding="utf-8"
        )

        assert "kafka" in _extras(manifest)
        assert "redis" not in _extras(manifest)
        assert "RedisSettings" not in container

    def test_redis_arrives_when_asked_for(self, tmp_path: Path) -> None:
        """The other direction: a flag that never turns anything on is worse
        than no flag, because it reads as configured."""
        service = _generate(tmp_path, service_name="cached", has_kafka="no", has_redis="yes")
        manifest = (service / "pyproject.toml").read_text(encoding="utf-8")
        container = (service / "src" / "cached" / "composition" / "container.py").read_text(
            encoding="utf-8"
        )

        assert "redis" in _extras(manifest)
        assert "RedisSettings()" in container


def _extras(manifest: str) -> set[str]:
    match = re.search(r"wb-platform\[([^\]]+)\]", manifest)
    return set(match.group(1).split(",")) if match else set()


class TestDockerfile:
    def test_build_context_is_documented_as_the_repository_root(self, generated: Path) -> None:
        """A context scoped to the service cannot see libs/platform or the
        root lockfile, and the failure reads like a dependency problem."""
        dockerfile = (generated / "Dockerfile").read_text(encoding="utf-8")

        assert "REPOSITORY ROOT" in dockerfile
        assert "-f services/probe/Dockerfile" in dockerfile

    def test_runs_as_a_non_root_user(self, generated: Path) -> None:
        assert "USER app" in (generated / "Dockerfile").read_text(encoding="utf-8")

    def test_healthcheck_avoids_the_ipv6_localhost_trap(self, generated: Path) -> None:
        """The app binds 0.0.0.0 (IPv4 only) while localhost resolves to ::1
        first — the probe would report a healthy service as refused."""
        dockerfile = (generated / "Dockerfile").read_text(encoding="utf-8")

        assert "127.0.0.1" in dockerfile
        assert "localhost:" not in dockerfile

    def test_entrypoint_matches_what_the_module_exposes(self, generated: Path) -> None:
        """The gap this closes: the service passed every other check and
        produced an image that could not start.

        `main.py` deliberately has no import-time `app`, so a CMD naming
        `main:app` fails at container start — after the build succeeded, after
        the tests passed, in the one place nothing was looking. Asserting the
        two agree is cheaper than finding out from a crash loop.
        """
        dockerfile = (generated / "Dockerfile").read_text(encoding="utf-8")
        module = (generated / "src" / "probe" / "main.py").read_text(encoding="utf-8")

        assert "--factory" in dockerfile
        assert "main:create_app" in dockerfile
        assert "main:app" not in dockerfile
        assert "def create_app(" in module  # the factory the CMD names exists

    def test_lockfile_drift_fails_the_build(self, generated: Path) -> None:
        """`--locked` beats resolving something the tests never saw."""
        assert "--locked" in (generated / "Dockerfile").read_text(encoding="utf-8")


class TestHelmValues:
    def test_image_tag_is_not_latest(self, generated: Path) -> None:
        """`latest` makes a rollback ambiguous at the one moment it must not be."""
        values = (generated / "helm-values.yaml").read_text(encoding="utf-8")

        assert "tag: latest" not in values

    def test_secrets_are_referenced_not_embedded(self, generated: Path) -> None:
        values = (generated / "helm-values.yaml").read_text(encoding="utf-8")

        assert "wbapp" not in values
        assert "password" not in values.lower()

    def test_consumers_scale_on_lag(self, generated: Path) -> None:
        """A consumer waiting on a slow downstream is idle and lagging at once,
        so CPU is the wrong signal."""
        values: Any = (generated / "helm-values.yaml").read_text(encoding="utf-8")

        assert "lagThreshold" in values
