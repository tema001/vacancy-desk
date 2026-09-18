from collections.abc import Callable
from enum import IntEnum
from typing import Annotated, Any

from pydantic import GetCoreSchemaHandler, GetPydanticSchema
from pydantic_core import CoreSchema, core_schema
from sqlalchemy import (
    SmallInteger,
    TypeDecorator,
)


class SmallIntEnum(TypeDecorator):
    impl = SmallInteger
    cache_ok = True

    def __init__(self, enum_class: type[IntEnum], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.enum_class = enum_class

    def process_bind_param(self, value: object, dialect: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return int(value)
        if isinstance(value, int):
            return int(self.enum_class(value))
        raise TypeError(f'expected {self.enum_class.__name__} or int, got {type(value)}')

    def process_result_value(self, value: object, dialect: object) -> IntEnum | None:
        if value is None:
            return None
        return self.enum_class(int(value))


def _enum_from_name(enum_cls: type[IntEnum]) -> Callable[[Any], IntEnum]:
    def parse(value: Any) -> IntEnum:
        if isinstance(value, enum_cls):
            return value
        if isinstance(value, str):
            return enum_cls[value]
        return enum_cls(int(value))

    return parse


def _enum_schema(source: type[IntEnum], handler: GetCoreSchemaHandler) -> CoreSchema:
    return core_schema.no_info_before_validator_function(
        _enum_from_name(source),
        handler(source),
    )


type EnumField[E: IntEnum] = Annotated[E, GetPydanticSchema(_enum_schema)]
