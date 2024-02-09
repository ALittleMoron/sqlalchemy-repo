import asyncio
from typing import TYPE_CHECKING, Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from tests.utils import create_db, destroy_db

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


@pytest.fixture(scope="session")
def event_loop() -> 'Generator[asyncio.AbstractEventLoop, None, None]':
    """Event loop fixture."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
def db_uri() -> str:
    """URI for test db (will be created in db_engine)."""
    return 'test_db'


@pytest.fixture(scope='session')
def db_sync_engine(db_uri: str) -> 'Generator[Engine, None, None]':
    """SQLAlchemy engine session-based fixture."""
    create_db(db_uri)
    engine = create_engine(db_uri, echo=False, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
    destroy_db(db_uri)


@pytest.fixture(scope='session')
def db_sync_session_factory(db_sync_engine: 'Engine') -> 'scoped_session[Session]':
    """SQLAlchemy session factory session-based fixture."""
    return scoped_session(
        sessionmaker(
            bind=db_sync_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        ),
    )


@pytest.fixture()
def db_sync_session(
    db_sync_session_factory: 'scoped_session[Session]',
) -> 'Generator[Session, None, None]':
    """SQLAlchemy session fixture."""
    with db_sync_session_factory() as session:
        yield session
