from __future__ import annotations

import json
import math
from collections.abc import Sequence

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect: object):
        del dialect

        def process(value: object) -> str | None:
            if value is None:
                return None
            vector = self._coerce(value)
            if vector is None:
                raise ValueError(f"Expected a finite {self.dimensions}-dimensional vector.")
            return "[" + ",".join(format(item, ".17g") for item in vector) + "]"

        return process

    def result_processor(self, dialect: object, coltype: object):
        del dialect, coltype

        def process(value: object) -> list[float] | None:
            if value is None:
                return None
            vector = self._coerce(value)
            if vector is None:
                raise ValueError(f"Database returned an invalid vector({self.dimensions}) value.")
            return vector

        return process

    def _coerce(self, value: object) -> list[float] | None:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray, str)):
            return None
        if len(value) != self.dimensions:
            return None
        result: list[float] = []
        for item in value:
            if isinstance(item, bool):
                return None
            try:
                number = float(item)
            except (TypeError, ValueError):
                return None
            if not math.isfinite(number):
                return None
            result.append(number)
        return result
