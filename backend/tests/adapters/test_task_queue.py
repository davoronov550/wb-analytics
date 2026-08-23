"""US5 async core (T054) — EnqueueCollection idempotency + CeleryTaskQueue.

Offline: fake ParseJob repository and a fake Celery app (no broker, no DB).
"""

from catalog.application.dto import ParseJob, ParseStatus
from catalog.application.use_cases.enqueue_collection import COLLECT_TASK_NAME, EnqueueCollection
from shared.adapters.task_queue import CeleryTaskQueue


class FakeParseJobRepo:
    def __init__(self, active: ParseJob | None = None):
        self._active = active
        self.created: list[ParseJob] = []
        self._counter = 0

    def find_active(self, query: str) -> ParseJob | None:
        return self._active

    def create_pending(self, query: str) -> ParseJob:
        self._counter += 1
        job = ParseJob(task_id=f"task-{self._counter}", query=query, status=ParseStatus.PENDING)
        self.created.append(job)
        return job

    def get(self, task_id):  # pragma: no cover - not used
        return None

    def mark_running(self, task_id):  # pragma: no cover
        pass

    def mark_done(self, task_id, created, updated):  # pragma: no cover
        pass

    def mark_failed(self, task_id, error):  # pragma: no cover
        pass


class FakeQueue:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def enqueue(self, task_name: str, payload: dict) -> str:
        self.calls.append((task_name, payload))
        return str(payload.get("task_id"))


def test_enqueue_creates_pending_job_and_dispatches_task():
    repo, queue = FakeParseJobRepo(), FakeQueue()

    job = EnqueueCollection(repository=repo, queue=queue).execute("наушники", max_pages=3)

    assert job.status == ParseStatus.PENDING
    assert len(repo.created) == 1
    assert queue.calls == [
        (COLLECT_TASK_NAME, {"task_id": job.task_id, "query": "наушники", "max_pages": 3})
    ]


def test_enqueue_is_idempotent_when_active_job_exists():
    existing = ParseJob(task_id="t-existing", query="наушники", status=ParseStatus.RUNNING)
    repo, queue = FakeParseJobRepo(active=existing), FakeQueue()

    job = EnqueueCollection(repository=repo, queue=queue).execute("наушники")

    assert job is existing
    assert repo.created == []
    assert queue.calls == []


class _FakeResult:
    id = "celery-id-1"


class _FakeTask:
    def __init__(self, name, app):
        self._name = name
        self._app = app

    def apply_async(self, kwargs=None):
        self._app.sent.append((self._name, kwargs))
        return _FakeResult()


class _FakeCeleryApp:
    def __init__(self):
        self.sent: list[tuple[str, dict]] = []
        self.tasks = self  # so app.tasks[name] returns a task bound to this app

    def __getitem__(self, name):
        return _FakeTask(name, self)


def test_celery_task_queue_applies_registered_task():
    app = _FakeCeleryApp()

    task_id = CeleryTaskQueue(app).enqueue(COLLECT_TASK_NAME, {"query": "q", "task_id": "x"})

    assert app.sent == [(COLLECT_TASK_NAME, {"query": "q", "task_id": "x"})]
    assert task_id == "celery-id-1"
