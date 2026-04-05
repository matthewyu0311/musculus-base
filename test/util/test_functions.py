# SPDX-License-Identifier: MIT

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from typing import Self, cast


class TestUtilFunctions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global runtime_final, immutable, new_with_fields
        from musculus.util.functions import (
            immutable,
            new_with_fields,
            runtime_final,
        )

    def test_runtime_final(self):
        @runtime_final
        class FinalClass:
            pass

        with self.assertRaises(TypeError):
            NotAllowSubclass = type("NotAllowSubclass", (FinalClass,), {})

    def _make_class(self):
        @immutable
        class TestClass:
            __slots__ = ("_value",)

            @property
            def value(self) -> int:
                return self._value

            def __new__(cls, value: int):
                memo = -value
                return new_with_fields(cls, _value=value)

            def __hash__(self):
                return self._value

            def __repr__(self) -> str:
                return f"{self.__class__.__name__}({self._value!r})"

            def __eq__(self, other):
                return isinstance(other, self.__class__) and other._value == self._value

        return TestClass

    def test_freeze(self):
        SimpleMemoClass = self._make_class()
        instance = SimpleMemoClass(value=123)
        self.assertEqual(getattr(instance, "value"), 123)
        with self.assertRaises(AttributeError):
            setattr(instance, "value", 0x00FFFF00)
        with self.assertRaises(AttributeError):
            delattr(instance, "value")
        with self.assertRaises(AttributeError):
            setattr(instance, "non_existent_attribute", 0xFF)
        with self.assertRaises(AttributeError):
            delattr(instance, "non_existent_attribute")
        with self.assertRaises(AttributeError):
            getattr(instance, "non_existent_attribute")
        with self.assertRaises(TypeError):
            SimpleMemoClass()  # type: ignore

    def test_thread_safety(self):
        SimpleMemoClass = self._make_class()
        data = tuple(range(0, 0xFFFFFFFF + 1, 0x00A1B2C3))
        rev = tuple(reversed(data))
        tl = threading.local()
        count = 8
        repeats = 2
        for _ in range(repeats):

            def worker(dat):
                for tl.i in dat:
                    self.assertEqual(SimpleMemoClass(tl.i).value, tl.i)

            with ThreadPoolExecutor(count) as exe:
                tasks = [
                    (exe.submit(worker, data if n % 1 else rev)) for n in range(count)
                ]
            exe.shutdown()
            for task in tasks:
                self.assertIsNone(task.result())
