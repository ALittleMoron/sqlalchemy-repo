import datetime
from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy_utils import create_database, database_exists, drop_database  # type: ignore


def create_db(uri: str) -> None:
    """Drop the database at ``uri`` and create a brand new one."""
    destroy_db(uri)
    create_database(uri)


def destroy_db(uri: str) -> None:
    """Destroy the database at ``uri``, if it exists."""
    if database_exists(uri):
        drop_database(uri)


def generate_datetime_list(*, n: int = 10, tz: Any = None) -> list[datetime.datetime]:  # noqa
    """Generate list of datetimes of given length with or without timezone."""
    now = datetime.datetime.now(tz=tz)  # type: ignore
    res = [now]
    for i in range(1, n):
        delta = datetime.timedelta(days=i)
        res.append(now + delta)
    return res


class Base(DeclarativeBase):  # noqa
    pass


class MyModel(Base):  # noqa
    __tablename__ = 'my_model'

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa
    name: Mapped[str]
    other_name: Mapped[str]
    dt: Mapped[datetime.datetime]
    bl: Mapped[bool]
    other_models: Mapped[list['OtherModel']] = relationship(back_populates='my_model', uselist=True)

    @hybrid_property
    def full_name(self):  # noqa
        return self.name + '' + self.other_name

    @hybrid_method
    def get_full_name(self):  # noqa
        return self.name + '' + self.other_name


class OtherModel(Base):  # noqa
    __tablename__ = 'other_model'

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa
    name: Mapped[str]
    other_name: Mapped[str]
    my_model_id: Mapped[int] = mapped_column(ForeignKey('my_model.id', ondelete='CASCADE'))
    my_model: Mapped['MyModel'] = relationship(back_populates='other_models', uselist=False)

    @hybrid_property
    def full_name(self):  # noqa
        return self.name + '' + self.other_name

    @hybrid_method
    def get_full_name(self):  # noqa
        return self.name + '' + self.other_name
