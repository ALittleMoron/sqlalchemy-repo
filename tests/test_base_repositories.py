from typing import TYPE_CHECKING, Any

import pytest
from dev_utils.sqlalchemy.filters.converters import (
    AdvancedOperatorFilterConverter,
    DjangoLikeFilterConverter,
    SimpleFilterConverter,
)

from sqlrepo.config import RepositoryConfig
from sqlrepo.exc import RepositoryAttributeError
from sqlrepo.repositories import BaseRepository, RepositoryModelClassIncorrectUseWarning
from tests.utils import MyModel

if TYPE_CHECKING:
    from tests.utils import OtherModel  # type: ignore  # noqa: F401


def test_inherit_skip() -> None:
    assert BaseRepository.__inheritance_check_model_class__ is True

    class MyRepo(BaseRepository):  # type: ignore
        __inheritance_check_model_class__ = False

    assert MyRepo.__inheritance_check_model_class__ is True


def test_already_set_model_class_warn() -> None:
    with pytest.warns(RepositoryModelClassIncorrectUseWarning):

        class MyRepo(BaseRepository[MyModel]):  # type: ignore
            model_class = MyModel


def test_cant_eval_forward_ref() -> None:
    with pytest.warns(RepositoryModelClassIncorrectUseWarning):

        class MyRepo(BaseRepository["OtherModel"]):  # type: ignore
            ...


def test_eval_forward_ref() -> None:
    class MyRepo(BaseRepository["MyModel"]):  # type: ignore
        ...

    assert MyRepo.model_class == MyModel  # type: ignore


def test_generic_incorrect_type() -> None:
    with pytest.warns(
        RepositoryModelClassIncorrectUseWarning,
        match="Passed GenericType is not SQLAlchemy model declarative class.",
    ):

        class MyRepo(BaseRepository[int]):  # type: ignore
            ...


def test_no_generic() -> None:
    with pytest.warns(
        RepositoryModelClassIncorrectUseWarning,
        match="GenericType was not passed for SQLAlchemy model declarative class.",
    ):

        class MyRepo(BaseRepository):  # type: ignore
            ...


def test_correct_use() -> None:
    class CorrectRepo(BaseRepository[MyModel]): ...

    assert CorrectRepo.model_class == MyModel  # type: ignore


def test_validate_disable_attributes() -> None:
    class CorrectRepo(BaseRepository[MyModel]):
        config = RepositoryConfig(
            disable_id_field="id",
            disable_field="bl",
            disable_field_type=bool,
        )

    CorrectRepo._validate_disable_attributes()  # type: ignore


def test_validate_disable_attributes_raise_error() -> None:
    class CorrectRepo(BaseRepository[MyModel]): ...

    with pytest.raises(RepositoryAttributeError):
        CorrectRepo._validate_disable_attributes()  # type: ignore


@pytest.mark.parametrize(
    ("strategy", "expected_class"),
    [
        ("simple", SimpleFilterConverter),
        ("advanced", AdvancedOperatorFilterConverter),
        ("django", DjangoLikeFilterConverter),
    ],
)
def test_get_filter_convert_class(strategy: str, expected_class: Any) -> None:  # noqa: ANN401
    class CorrectRepo(BaseRepository[MyModel]):
        config = RepositoryConfig(filter_convert_strategy=strategy)  # type: ignore

    assert CorrectRepo.config.get_filter_convert_class() == expected_class
