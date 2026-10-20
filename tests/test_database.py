import pytest

from app.core import database, init_db


class FakeSession:
    def __init__(self, fail=False):
        self.fail = fail
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def commit(self):
        self.commits += 1
        if self.fail:
            raise RuntimeError("commit failed")

    async def rollback(self):
        self.rollbacks += 1

    async def close(self):
        self.closes += 1


async def collect_dependency(generator):
    return await generator.__anext__()


async def test_get_db_commits_and_closes_after_success(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()

    yielded = await collect_dependency(dependency)
    assert yielded is session

    with pytest.raises(StopAsyncIteration):
        await dependency.__anext__()

    assert session.commits == 1
    assert session.rollbacks == 0
    assert session.closes == 1


async def test_get_db_rolls_back_and_closes_after_handler_error(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()

    await collect_dependency(dependency)
    with pytest.raises(ValueError, match="request failed"):
        await dependency.athrow(ValueError("request failed"))

    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.closes == 1


async def test_get_db_rolls_back_if_commit_fails(monkeypatch):
    session = FakeSession(fail=True)
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()

    await collect_dependency(dependency)
    with pytest.raises(RuntimeError, match="commit failed"):
        await dependency.__anext__()

    assert session.rollbacks == 1
    assert session.closes == 1


async def test_init_tables_creates_pgvector_and_metadata(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.executed = []
            self.sync_callbacks = []

        async def execute(self, statement):
            self.executed.append(str(statement))

        async def run_sync(self, callback):
            self.sync_callbacks.append(callback)

    class FakeBegin:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            return self.connection

        async def __aexit__(self, *_args):
            return None

    connection = FakeConnection()
    monkeypatch.setattr(init_db, "engine", type("Engine", (), {
        "begin": lambda _self: FakeBegin(connection)
    })())

    await init_db.init_tables()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in connection.executed[0]
    assert connection.sync_callbacks == [init_db.Base.metadata.create_all]


def test_database_base_is_declarative_base():
    assert database.Base.metadata is not None
