from typing import TYPE_CHECKING, Any, Literal

import pytest
from sqlalchemy_filter_converter import (
    AdvancedOperatorFilterConverter,
    DjangoLikeFilterConverter,
    SimpleFilterConverter,
)

from sqlrepo.config import RepositoryConfig
from sqlrepo.exc import RepositoryAttributeError
from sqlrepo import constants as c
from sqlrepo.repositories import BaseRepository, RepositoryModelClassIncorrectUseWarning
from tests.utils import MyModel

if TYPE_CHECKING:
    from tests.utils import OtherModel  # noqa: F401


def test_inherit_skip() -> None:
    assert BaseRepository.__inheritance_check_model_class__ is True

    class MyRepo(BaseRepository):
        __inheritance_check_model_class__ = False

    assert MyRepo.__inheritance_check_model_class__ is True


def test_already_set_model_class_warn() -> None:
    with pytest.warns(RepositoryModelClassIncorrectUseWarning):

        class MyRepo(BaseRepository[MyModel]):
            model_class = MyModel


def test_cant_eval_forward_ref() -> None:
    with pytest.warns(RepositoryModelClassIncorrectUseWarning):

        class MyRepo(BaseRepository["OtherModel"]): ...


def test_eval_forward_ref() -> None:
    class MyRepo(BaseRepository["MyModel"]): ...

    assert MyRepo.model_class == MyModel


def test_generic_incorrect_type() -> None:
    with pytest.warns(
        RepositoryModelClassIncorrectUseWarning,
        match=c.REPOSITORY_GENERIC_TYPE_IS_NOT_MODEL,
    ):

        class MyRepo(BaseRepository[int]): ...


def test_no_generic() -> None:
    with pytest.warns(
        RepositoryModelClassIncorrectUseWarning,
        match=c.REPOSITORY_GENERIC_TYPE_NOT_PASSED_WARNING,
    ):

        class MyRepo(BaseRepository): ...


def test_generic_not_class() -> None:
    with pytest.warns(
        RepositoryModelClassIncorrectUseWarning,
        match=c.REPOSITORY_GENERIC_TYPE_IS_NOT_CLASS_WARNING,
    ):

        class MyRepo(BaseRepository['25']): ...


def test_correct_use() -> None:
    class CorrectRepo(BaseRepository[MyModel]): ...

    assert CorrectRepo.model_class == MyModel


def test_validate_disable_attributes() -> None:
    class CorrectRepo(BaseRepository[MyModel]):
        config = RepositoryConfig(
            disable_id_field="id",
            disable_field="bl",
            disable_field_type=bool,
        )

    CorrectRepo._validate_disable_attributes()


def test_validate_disable_attributes_raise_error() -> None:
    class CorrectRepo(BaseRepository[MyModel]): ...

    with pytest.raises(RepositoryAttributeError):
        CorrectRepo._validate_disable_attributes()


@pytest.mark.parametrize(
    ("strategy", "expected_class"),
    [
        ("simple", SimpleFilterConverter),
        ("advanced", AdvancedOperatorFilterConverter),
        ("django", DjangoLikeFilterConverter),
    ],
)
def test_get_filter_convert_class(
    strategy: Literal["simple", "advanced", "django"],
    expected_class: Any,
) -> None:  # noqa: ANN401
    class CorrectRepo(BaseRepository[MyModel]):
        config = RepositoryConfig(filter_convert_strategy=strategy)

    assert CorrectRepo.config.get_filter_convert_class() == expected_class
