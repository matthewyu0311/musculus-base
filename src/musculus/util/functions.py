# SPDX-License-Identifier: MIT

__all__ = [
    "EMPTY_MAPPING",
    "EMPTY_ITERATOR",
    "seq_startswith",
    "seq_endswith",
    "throw",
    "get_all_slots",
    "get_all_attrs",
    "slots_tuple",
    "slots_values",
    "eq_slots_noshort",
    "repr_slots",
    "repr_slots_positional",
    "compare_with",
    "make_compare_fns",
    "compare_slots",
    "eq_slots",
    "hash_slots",
    "runtime_final",
    "blocked_setattr",
    "blocked_delattr",
    "new_with_fields",
    "immutable",
    "SlottedImmutableMixin",
]

import operator
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Reversible
from itertools import chain
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Never, NoReturn, final, overload

EMPTY_MAPPING: Mapping[Any, Never] = MappingProxyType({})


class _EmptyIterator(Iterator[Never]):
    __slots__ = ()

    def __iter__(self):
        return self

    def __next__(self) -> NoReturn:
        raise StopIteration


EMPTY_ITERATOR = _EmptyIterator()


def seq_startswith[T](seq: Iterable[T], prefix: Iterable[T]) -> bool:
    """If the arguments are iterators, the remainder of the iterators are not always exhausted."""
    it1 = iter(seq)
    it2 = iter(prefix)
    while True:
        try:
            x = next(it2)
        except StopIteration:
            # We have exhausted the prefix
            return True

        try:
            y = next(it1)
            if x != y:
                return False
        except StopIteration:
            # We have exhausted the sequence before we're done
            return False


def seq_endswith[T](seq: Reversible[T], suffix: Reversible[T]) -> bool:
    return seq_startswith(reversed(seq), reversed(suffix))


def throw(
    e: BaseException | type[BaseException] | None = None, /, *args, **kwargs
) -> NoReturn:
    """Raise as a function. Does not support explicit `raise ... from ...` setting."""
    if isinstance(e, BaseException):
        raise e
    elif isinstance(e, type):
        if not issubclass(e, BaseException):  # type: ignore
            raise TypeError("exceptions must derive from BaseException")
        ex = e(*args, **kwargs)
        raise ex
    else:
        ex = sys.exception()
        if ex is None:
            raise RuntimeError("No active exception to reraise")
        raise ex


def get_all_slots(cls) -> Iterable[str]:
    """Gets all names of slots defined in this class and the MROs, in MRO order."""

    return chain.from_iterable(
        c.__slots__ for c in cls.__mro__ if hasattr(c, "__slots__")
    )


def get_all_attrs(obj) -> Iterable[str]:
    try:
        yield from obj.__dict__
    except AttributeError:
        pass
    yield from get_all_slots(obj.__class__)


def slots_tuple(obj) -> tuple[Any, ...]:
    return tuple(getattr(obj, k) for k in get_all_slots(obj.__class__) if k[0] != "_")


def slots_values(obj, *, include_under: bool = False) -> dict[str, Any]:
    return {
        k: getattr(obj, k)
        for k in get_all_slots(obj.__class__)
        if include_under or k[0] != "_"
    }


def eq_slots_noshort(self, other) -> bool:
    """Instances compare equal only if all of their public slotted attributes compare equal.
    No `is` short-circuit takes place; this preserves behavior around float `nan`."""
    cls = self.__class__
    if not isinstance(other, cls):
        return NotImplemented
    return all(
        getattr(self, k) == getattr(other, k) for k in get_all_slots(cls) if k[0] != "_"
    )


eq_slots_noshort.__name__ = "__eq__"


def repr_slots(self) -> str:
    o = [
        f"{k}={getattr(self, k)!r}"
        for k in get_all_slots(self.__class__)
        if k[0] != "_"
    ]
    return f"{self.__class__.__qualname__}({', '.join(o)})"


def repr_slots_positional(self) -> str:
    cls = self.__class__
    o = [f"{getattr(self, k)!r}" for k in get_all_slots(cls) if k[0] != "_"]
    return f"{cls.__qualname__}({', '.join(o)})"


repr_slots.__name__ = repr_slots_positional.__name__ = "__repr__"


def compare_with[K, T, T2 = Never](
    op: Callable[[K, K], bool],
    key_fn: Callable[[T | T2], K],
    *,
    short: bool,
    transform: Callable[[Any], T | T2] | None = None,
) -> Callable[[Any, object], bool]:
    """Instances compare equal if they are identical objects,
    or if all of their public slotted attributes compare equal.
    The `is` short-circuit shall be used only if none of the slots holds float `nan`.

    `transform` specifies a transformation function that transforms other into the  class as self.
    """

    def compare(self: T, other: object, /) -> bool:
        if self is other:
            return short
        if isinstance(other, self.__class__):
            other_key = key_fn(other)
        else:
            if transform is None:
                return NotImplemented
            try:
                transformed = transform(other)
            except Exception:
                return NotImplemented
            else:
                other_key = key_fn(transformed)
        return op(key_fn(self), other_key)

    compare.__name__ = op.__name__
    return compare


def make_compare_fns(key_fn: Callable[[Any], Any]) -> tuple[
    Callable[[Any, object], bool],
    Callable[[Any, object], bool],
    Callable[[Any, object], bool],
    Callable[[Any, object], bool],
    Callable[[Any, object], bool],
    Callable[..., int],
]:
    lt = compare_with(operator.__lt__, key_fn, short=False)
    le = compare_with(operator.__le__, key_fn, short=True)
    eq = compare_with(operator.__eq__, key_fn, short=True)
    ge = compare_with(operator.__ge__, key_fn, short=True)
    gt = compare_with(operator.__gt__, key_fn, short=False)

    def __hash__(self) -> int:
        return hash(key_fn(self))

    return (lt, le, eq, ge, gt, __hash__)


compare_slots = make_compare_fns(slots_tuple)
eq_slots: Callable[[Any, Any], bool] = compare_slots[2]
hash_slots: Callable[..., int] = compare_slots[5]


#############################################
#### Runtime finality and frozen classes ####
def _runtime_final(cls=None):
    """Decorator to inject an `__init_subclass__` method that disallows subclassing at runtime."""

    def impl(cls):
        def init_subclass(*_args, **_kwargs):
            raise TypeError(f"{cls.__qualname__} cannot be subclassed")

        cls.__init_subclass__ = init_subclass
        cls = final(cls)

        return cls

    if cls is None:
        return impl
    return impl(cls)


if TYPE_CHECKING:
    runtime_final = final
else:
    runtime_final = _runtime_final


def blocked_setattr(self, name, _):
    raise AttributeError(f"Attribute {name!r} is read-only", name=name, obj=self)


def blocked_delattr(self, name):
    raise AttributeError(f"Attribute {name!r} is read-only", name=name, obj=self)


@overload
def new_with_fields[T1](cls: type[T1], /, **fields) -> T1: ...


@overload
def new_with_fields[T1, T2](cls: type[T1], subcls: type[T2], /, **fields) -> T2: ...


def new_with_fields(cls, subcls=None, /, **fields):
    """For classes with dynamic subclass dispatch logic.
    `cls`: the class whose direct superclass contains the `__new__` implementation.
    `subcls`: the exact type of the instance to be created (must be a subclass of `cls`).
    If not given, same as `cls`.
    """

    if subcls is None:
        subcls = cls
    elif not issubclass(subcls, cls):
        raise TypeError(f"{subcls!r} is not a subclass of {cls!r}")
    obj = super(cls, subcls).__new__(subcls)
    setter = object.__setattr__
    for k, v in fields.items():
        setter(obj, k, v)
    return obj


def immutable(cls):
    """Decorator to make `__setattr__` and `__delattr__` of a class raise `AttributeError`.

    NOTE: This mechanism protects against ordinary modifications (`something.foo = bar`, `del something.foo`) but
    can be circumvented via `object.__setattr__(object, name, value)`.
    """

    cls.__setattr__ = blocked_setattr
    cls.__delattr__ = blocked_delattr
    return cls


@immutable
class SlottedImmutableMixin:
    __slots__ = ()

    __lt__, __le__, __eq__, __ge__, __gt__, __hash__ = make_compare_fns(slots_tuple)
