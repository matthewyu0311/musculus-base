# SPDX-License-Identifier: MIT
"""Functions and types for parsing IANA data files."""

from collections.abc import Iterable, Iterator
from itertools import chain
from sys import intern

type RecordDict = dict[str, str | list[str]]


def iter_records(lines: Iterable[str]) -> Iterator[RecordDict]:
    instance = {}
    field_name = ""
    field_value = ""
    for line in chain(lines, "%%"):
        line = line.rstrip("\n\r")
        if line.startswith(" "):
            # This line is a continuation of the last line
            # Multi-line values are not common --- string + performance should be OK
            field_value += line[1:]
            continue
        left, colon, right = line.partition(":")
        left = left.rstrip()
        right = right.lstrip()
        # End of a field
        # Put the last-seen field into the record
        if field_name:
            old_value = instance.get(field_name, None)
            if old_value is None:
                instance[field_name] = field_value
            elif isinstance(old_value, str):
                instance[field_name] = [old_value, field_value]
            else:
                instance[field_name] = [*old_value, field_value]
        if line == "%%":
            field_name = ""
            field_value = ""
            yield instance
            instance = {}
        else:
            field_name = intern(left)
            field_value = right
