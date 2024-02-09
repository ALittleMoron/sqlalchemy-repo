from typing import Any, TypeGuard

from sqlrepo.filters.schemas import AdvancedOperatorsSet, OperatorFilterDict


def all_dict_keys_are_str(value: dict[Any, Any]) -> TypeGuard[dict[str, Any]]:
    return all(isinstance(key, str) for key in value)


def is_dict_simple_filter_dict(value: dict[Any, Any]) -> TypeGuard['OperatorFilterDict']:
    if 'field' not in value or not isinstance(value['field'], str):
        return False
    if 'value' not in value:
        return False
    if 'operator' in value and value['operator'] not in AdvancedOperatorsSet:
        return False
    return True
