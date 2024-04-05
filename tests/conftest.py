import asyncio
import os
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Generator

import pytest
from mimesis import Datetime, Locale, Text
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker

from tests.utils import (
    Base,
    MyModel,
    OtherModel,
    coin_flip,
    create_db,
    create_db_item_async,
    create_db_item_sync,
    destroy_db,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session

    from tests.types import AsyncFactoryFunctionProtocol, SyncFactoryFunctionProtocol


true_stmt = {'y', 'Y', 'yes', 'Yes', 't', 'true', 'True', '1'}
IS_DOCKER_TEST = os.environ.get('IS_DOCKER_TEST', 'false') in true_stmt


@pytest.fixture(scope="session")
def event_loop() -> 'Generator[asyncio.AbstractEventLoop, None, None]':
    """Event loop fixture."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
def db_name() -> str:
    """Db name as fixture."""
    return 'test_db'


@pytest.fixture(scope='session')
def db_user() -> str:
    """DB user as fixture."""
    return 'postgres'


@pytest.fixture(scope='session')
def db_password() -> str:
    """DB password as fixture."""
    return 'postgres'


@pytest.fixture(scope='session')
def db_host() -> str:
    """DB host as fixture."""
    if IS_DOCKER_TEST:
        return 'db'
    return 'localhost'


@pytest.fixture(scope='session')
def db_port() -> int:
    """DB port as fixture."""
    return 5432


@pytest.fixture(scope='session')
def db_domain(db_name: str, db_user: str, db_password: str, db_host: str, db_port: int) -> str:
    """Domain for test db without specified driver."""
    return f'{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'


@pytest.fixture(scope='session')
def db_sync_url(db_domain: str) -> str:
    """URL for test db (will be created in db_engine): sync driver."""
    return f'postgresql://{db_domain}'


@pytest.fixture(scope='session')
def db_async_url(db_domain: str) -> str:
    """URL for test db (will be created in db_engine): async driver."""
    return f'postgresql+asyncpg://{db_domain}'


@pytest.fixture(scope='module')
def db_sync_engine(db_sync_url: str) -> 'Generator[Engine, None, None]':
    """SQLAlchemy engine session-based fixture."""
    with suppress(SQLAlchemyError):
        create_db(db_sync_url)
    engine = create_engine(db_sync_url, echo=False, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
    with suppress(SQLAlchemyError):
        destroy_db(db_sync_url)


@pytest.fixture(scope='module')
def db_sync_session_factory(db_sync_engine: 'Engine') -> 'scoped_session[Session]':
    """SQLAlchemy session factory session-based fixture."""
    return scoped_session(
        sessionmaker(
            bind=db_sync_engine,
            autoflush=False,
            expire_on_commit=False,
        ),
    )


@pytest.fixture()
def db_sync_session(
    db_sync_engine: 'Engine',
    db_sync_session_factory: 'scoped_session[Session]',
) -> 'Generator[Session, None, None]':
    """SQLAlchemy session fixture."""
    Base.metadata.create_all(db_sync_engine)
    with db_sync_session_factory() as session:
        yield session
    Base.metadata.drop_all(db_sync_engine)


@pytest.fixture()
def mymodel_sync_factory(
    dt_faker: Datetime,
    text_faker: Text,
) -> 'SyncFactoryFunctionProtocol[MyModel]':
    """Function-factory, that create MyModel instances."""

    def _create(
        session: 'Session',
        *,
        commit: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> MyModel:
        params: dict[str, Any] = dict(
            name=text_faker.sentence(),
            other_name=text_faker.sentence(),
            dt=dt_faker.datetime(),
            bl=coin_flip(),
        )
        params.update(kwargs)
        return create_db_item_sync(session, MyModel, params, commit=commit)

    return _create


@pytest.fixture()
def othermodel_sync_factory(
    text_faker: Text,
    mymodel_sync_factory: 'SyncFactoryFunctionProtocol[MyModel]',
) -> 'SyncFactoryFunctionProtocol[OtherModel]':
    """Function-factory, that create OtherModel instances."""

    def _create(
        session: 'Session',
        *,
        commit: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> OtherModel:
        if 'model_id' not in kwargs:
            model_id = mymodel_sync_factory(session, commit=commit).id
        else:
            model_id = kwargs.pop('model_id')
        params: dict[str, Any] = dict(
            name=text_faker.sentence(),
            other_name=text_faker.sentence(),
            model_id=model_id,
        )
        params.update(kwargs)
        return create_db_item_sync(session, OtherModel, params, commit=commit)

    return _create


@pytest.fixture()
def mymodel_async_factory(
    text_faker: Text,
    dt_faker: Datetime,
) -> 'AsyncFactoryFunctionProtocol[MyModel]':
    """Function-factory, that create MyModel instances."""

    async def _create(
        session: 'AsyncSession',
        *,
        commit: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> MyModel:
        params: dict[str, Any] = dict(
            name=text_faker.sentence(),
            other_name=text_faker.sentence(),
            dt=dt_faker.datetime(),
            bl=coin_flip(),
        )
        params.update(kwargs)
        return await create_db_item_async(session, MyModel, params, commit=commit)

    return _create


@pytest.fixture()
def othermodel_async_factory(
    text_faker: Text,
    mymodel_async_factory: 'AsyncFactoryFunctionProtocol[MyModel]',
) -> 'AsyncFactoryFunctionProtocol[OtherModel]':
    """Function-factory, that create OtherModel instances."""

    async def _create(
        session: 'AsyncSession',
        *,
        commit: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> OtherModel:
        if 'model_id' not in kwargs:
            model = await mymodel_async_factory(session, commit=commit)
            model_id = model.id
        else:
            model_id = kwargs.pop('model_id')
        params: dict[str, Any] = dict(
            name=text_faker.sentence(),
            other_name=text_faker.sentence(),
            model_id=model_id,
        )
        params.update(kwargs)
        return await create_db_item_async(session, OtherModel, params, commit=commit)

    return _create


@pytest.fixture()
def text_faker() -> Text:
    return Text(locale=Locale.EN)


@pytest.fixture()
def dt_faker() -> Datetime:
    return Datetime(locale=Locale.EN)
