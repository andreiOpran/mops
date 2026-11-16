from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import engine, get_session
from app.main import app
from tests.gtfs_fixture import build_gtfs_zip


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test.

    Commits made by the code under test only release a savepoint, so every
    test starts from an empty schema (created by `alembic upgrade head`).
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """API client whose requests use `db_session` (rolled back after the test)."""

    def session_override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = session_override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def gtfs_v1(tmp_path: Path) -> Path:
    return build_gtfs_zip(tmp_path / "v1.zip", version="6.41.1")


@pytest.fixture
def gtfs_v2(tmp_path: Path) -> Path:
    return build_gtfs_zip(tmp_path / "v2.zip", version="6.42.0", extra_route=True)
