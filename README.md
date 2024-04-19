# sqlrepo

![coverage](./coverage.svg)

>SQLAlchemy repository pattern.

## Current state

Now, some features of repository pattern works incorrect or some parts of it is hard to understand
or use. I want to simplify work with repositories, so this is TODO for my project:

* [ ] Add more test cases for main functionality. Now, tested only base cases of repository
    method use.
* [ ] Add wrapper for all non sqlrepo exceptions. Now, some functionality could raise
      "raw" SQLAlchemy error. I want to avoid the situation, when developer make
      try-except with all possible exceptions, when works with my package.
* [ ] Add more use-cases of `specific_column_mapping` option. Now it only works with
      `search_by` and `order_by` params. I want to add it for filters, joins and other
      parts, where it can be used.
* [ ] Integrate sqlrepo with FastAPI or some other web-frameworks.
* [ ] Add pydantic-like configuration. Current implementation works on ClassVar. I want to separate
      configuration and main repository code.

If all these todo items are finished, it means, that all, what I want, is implemented.
If you want to give me advice or feedback, you are welcome.

## Install

sqlrepo project doesn't has optional dependencies, so you can install it just as regular:

With pip:

```bash
pip install sqlrepo
```

With poetry:

```bash
poetry add sqlrepo
```

With PDM:

```bash
pdm add sqlrepo
```

or other dependency managers.

## Usage

sqlrepo provides base classes with CRUD operations, so you just need to inherit them with your
SQLAlchemy model like this:

```python
from sqlrepo import BaseSyncRepository, BaseAsyncRepository

from your_package.models import YourModel

class YourModelSyncRepository(BaseSyncRepository[YourModel]):
    pass

class YourModelAsyncRepository(BaseAsyncRepository[YourModel]):
    pass
```

## Configuration

sqlrepo Repository classes provide many options, which you can configure to make repositories
work like you need:

### `model_class`

Model class for repository.

You can set this option manually, but it is not recommended. Repository will automatically
add model_class attribute by extracting it from Generic type.

Use case:

```python
from my_package.models import Admin

class AdminRepository(BaseSyncRepository[Admin]):
    pass

# So, when you will use AdminRepository, model_class attribute will be set with Admin
# automatically.
```

or you can do it twice like this:

```python
from my_package.models import Admin

class AdminRepository(BaseSyncRepository[Admin]):
    model_class = Admin
```

### `specific_column_mapping`

Warning! Current version of sqlrepo doesn't support this mapping for filters, joins and loads.

Uses as mapping for some attributes, that you need to alias or need to specify column
from other models.

Warning: if you specify column from other model, it may cause errors. For example, update
doesn't use it for filters, because joins are not presents in update.

Current implementation use these option in search_by and order_by params, if you pass them as
strings.

```python
from my_package.models import Admin

class AdminRepository(BaseSyncRepository[Admin]):
    specific_column_mapping = {"custom_field": Admin.id, "other_field": Admin.name}


admins = AdminRepository(session).list(
    search='abc',
    search_by="other_field",
    order_by='custom_field',
)
```

### `use_flush`

Uses as flag of `flush` method in SQLAlchemy session.

By default, True, because repository has (mostly) multiple methods evaluate use. For example,
generally, you want to create some model instances, create some other (for example, log table)
and then receive other model instance in one use (for example, in Unit of work pattern).

If you will work with repositories as single methods uses, switch to use_flush=False. It will
make queries commit any changes.

### `update_set_none`

Uses as flag of set None option in `update_instance` method.

If True, allow to force `update_instance` instance columns with None value. Works together
with `update_allowed_none_fields`.

By default False, because it's not safe to set column to None - current version if sqlrepo
not able to check optional type. Will be added in next versions, and then `update_set_none`
will be not necessary.

### `update_allowed_none_fields`

Set of strings, which represents columns of model.

Uses as include or exclude for given data in `update_instance` method.

By default allow any fields. Not dangerous, because `update_set_none` by default set to False,
and there will be no affect on `update_instance` method

### `allow_disable_filter_by_value`

Uses as flag of filtering in disable method.

If True, make additional filter, which will exclude items, which already disabled.
Logic of disable depends on type of disable column. See `disable_field` docstring for more
information.

By default True, because it will make more efficient query to not override disable column. In
some cases (like datetime disable field) it may be better to turn off this flag to save disable
with new context (repeat disable, if your domain supports repeat disable and it make sense).

### `disable_field_type`

Uses as choice of type of disable field.

By default, None. Needs to be set manually, because this option depends on user custom
implementation of disable_field. If None and `disable` method was evaluated, there will be
RepositoryAttributeError exception raised by Repository class.

### `disable_field`

Uses as choice of used defined disable field.

By default, None. Needs to be set manually, because this option depends on user custom
implementation of disable_field. If None and `disable` method was evaluated, there will be
RepositoryAttributeError exception raised by Repository class.

Now only works with string fields, because otherwise sqlalchemy think that Repository class is
sqlalchemy model without mapping, and raise error.

### `disable_id_field`

Uses as choice of used defined id field in model, which supports disable.

By default, None. Needs to be set manually, because this option depends on user custom
implementation of disable_field. If None and `disable` method was evaluated, there will be
RepositoryAttributeError exception raised by Repository class.

Now only works with string fields, because otherwise sqlalchemy think that Repository class is
sqlalchemy model without mapping, and raise error.

### `unique_list_items`

__Warning!__ Ambiguous option!

Current version of `sqlrepo` works with load strategies with user configured option
`load_strategy`. In order to make `list` method works stable, this option is used.
If you don't work with relationships in your model or you don't need unique (for example,
if you use selectinload), set this option to False. Otherwise keep it in True state.

### `filter_convert_strategy`

Uses as choice of filter convert.

By default "simple", so you able to pass filters with ``key-value`` structure. You still can
pass raw filters (just list of SQLAlchemy filters), but if you pass dict, it will be converted
to SQLAlchemy filters with passed strategy.

Currently, supported converters:

* `simple` - `key-value` dict.

* `advanced` - dict with `field`, `value` and `operator` keys.
List of operators: `=, >, <, >=, <=, is, is_not, between, contains`.

* `django-like` - `key-value` dict with django-like lookups system. See django docs for
more info.

### `load_strategy`

Uses as choice of SQLAlchemy load strategies.

By default selectinload, because it makes less errors.

## Unit of work

sqlrepo provides unit of work base implementation to work with all your repositories in one place
with one session:

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlrepo import BaseAsyncRepository, BaseAsyncUnitOfWork

from your_package.models import YourModel, YourOtherModel

async_engine = create_async_engine(...)
async_session = async_sessionmaker(async_engine)


class YourModelAsyncRepository(BaseAsyncRepository[YourModel]):
    pass

class YourOtherModelAsyncRepository(BaseSyncRepository[YourOtherModel]):
    pass


class YourUnitOfWork(BaseAsyncUnitOfWork):
    session_factory = async_session

    async def init_repositories(self, session: AsyncSession) -> None:
        self.your_model_repo = YourModelAsyncRepository(session)
        self.your_other_model_repo = YourOtherModelAsyncRepository(session)

    # Your custom method, that works with your repositories and do business-logic.
    async def work_with_repo_together(self, model_id: int):
        your_model_instance = await self.your_model_repo.get(filters={'id': model_id})
        your_other_model_instance = await self.your_model_repo.list(
            filters={'your_model_id': model_id},
        )
        # Some other stuff
```

Be careful, when you work with Unit of work pattern. For stable work use `expire_on_commit = False`
in your sessionmaker or make sure, that your repositories has option `use_flush = True` to avoid
problems with `session.commit`.

Be sure, you passed `session_factory` in class body, otherwise it will
cause TypeError. `session_factory` is abstract class property. It must
be set or Unit of work will not work.

By default Unit of work will make commit on context manager exit, but you can specify
`__skip_session_use__ = True` for your Unit of work class like this:

```python
...

class YourUnitOfWork(BaseAsyncUnitOfWork):
    __skip_session_use__ = True

...
```

and this will cause no commit or other session manipulation (except session create for repositories
work).
