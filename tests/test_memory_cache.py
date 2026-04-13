import unittest
from typing import Any, cast

from agile.cache import MemoryCache


class Foo:
    created_count = 0

    def __init__(self, name: str = "default", version: int = 1):
        Foo.created_count += 1
        self.name = name
        self.version = version
        print("Foo instance created")


class TestMemoryCache(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cache = MemoryCache()
        cls.cache.set("a", 1)
        cls.cache.set("b", 2)
        cls.cache.set("c", 3)

    def test_get(self):
        self.assertEqual(self.cache.get("a"), 1)
        self.assertEqual(self.cache.get("b"), 2)
        self.assertEqual(self.cache.get("c"), 3)

    def test_get_or_set(self):
        self.cache.delete("foo")
        Foo.created_count = 0

        foo1 = self.cache.get_or_set("foo", lambda: Foo())
        foo2 = self.cache.get_or_set("foo", lambda: Foo())
        self.assertIs(foo1, foo2)
        self.assertEqual(Foo.created_count, 1)

    def test_get_or_set_with_init_args(self):
        self.cache.delete("foo_with_args")
        Foo.created_count = 0

        foo1 = self.cache.get_or_set("foo_with_args", lambda: Foo("bar", 2))
        foo2 = self.cache.get_or_set("foo_with_args", lambda: Foo("bar", 3))

        self.assertIs(foo1, foo2)
        self.assertEqual(Foo.created_count, 1)
        self.assertEqual(foo2.name, "bar")
        self.assertEqual(foo2.version, 2)

    def test_get_or_set_callbacks(self):
        self.cache.delete("foo_callbacks")
        Foo.created_count = 0
        callback_events = []

        def on_get(key, value):
            callback_events.append(("get", key, value))

        def on_set(key, value):
            callback_events.append(("set", key, value))

        foo1 = self.cache.get_or_set(
            "foo_callbacks",
            lambda: Foo("cb", 1),
            on_get=on_get,
            on_set=on_set,
        )
        foo2 = self.cache.get_or_set(
            "foo_callbacks",
            lambda: Foo("cb", 2),
            on_get=on_get,
            on_set=on_set,
        )

        self.assertIs(foo1, foo2)
        self.assertEqual(Foo.created_count, 1)
        self.assertEqual(len(callback_events), 2)
        self.assertEqual(callback_events[0][0], "set")
        self.assertEqual(callback_events[0][1], "foo_callbacks")
        self.assertIs(callback_events[0][2], foo1)
        self.assertEqual(callback_events[1][0], "get")
        self.assertEqual(callback_events[1][1], "foo_callbacks")
        self.assertIs(callback_events[1][2], foo2)

    def test_get_or_set_callbacks_emit_get_after_set(self):
        self.cache.delete("foo_callbacks_emit")
        Foo.created_count = 0
        callback_events = []

        def on_get(key, value):
            callback_events.append(("get", key, value))

        def on_set(key, value):
            callback_events.append(("set", key, value))

        foo1 = self.cache.get_or_set(
            "foo_callbacks_emit",
            lambda: Foo("emit", 1),
            on_get=on_get,
            on_set=on_set,
            emit_get_after_set=True,
        )
        foo2 = self.cache.get_or_set(
            "foo_callbacks_emit",
            lambda: Foo("emit", 2),
            on_get=on_get,
            on_set=on_set,
            emit_get_after_set=True,
        )

        self.assertIs(foo1, foo2)
        self.assertEqual(Foo.created_count, 1)
        self.assertEqual(len(callback_events), 3)
        self.assertEqual(callback_events[0][0], "set")
        self.assertEqual(callback_events[0][1], "foo_callbacks_emit")
        self.assertIs(callback_events[0][2], foo1)
        self.assertEqual(callback_events[1][0], "get")
        self.assertEqual(callback_events[1][1], "foo_callbacks_emit")
        self.assertIs(callback_events[1][2], foo1)
        self.assertEqual(callback_events[2][0], "get")
        self.assertEqual(callback_events[2][1], "foo_callbacks_emit")
        self.assertIs(callback_events[2][2], foo2)

    def test_items_keys_values(self):
        self.cache.clear()
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.set("c", 3)
        # items
        items = dict(self.cache.items())
        self.assertEqual(items, {"a": 1, "b": 2, "c": 3})
        # keys
        keys = set(self.cache.keys())
        self.assertEqual(keys, {"a", "b", "c"})
        # values
        values = set(self.cache.values())
        self.assertEqual(values, {1, 2, 3})

    def test_generic_hint_usage(self):
        int_cache: MemoryCache[str, int] = MemoryCache[str, int]()
        int_cache.set("count", 7)

        self.assertEqual(int_cache.get("count"), 7)
        self.assertEqual(int_cache.get("missing", 0), 0)

    def test_strict_types_default_false(self):
        cache = MemoryCache()
        cache.set(1, "ok")
        self.assertEqual(cache.get(1), "ok")

    def test_strict_types_key_and_value(self):
        cache = MemoryCache(strict_types=True)
        cache.set("count", 1)
        cache.set(1, 2)
        cache.set((1, "x"), 3)

        with self.assertRaisesRegex(TypeError, r"field=key, expected=Hashable, actual=list, key=\[1, 2\], value=2"):
            cache.set(cast(Any, [1, 2]), 2)

        with self.assertRaisesRegex(TypeError, r"field=value, expected=int, actual=str, key='count', value='2'"):
            cache.set("count", "2")

    def test_strict_types_get_or_set(self):
        cache = MemoryCache(strict_types=True)
        self.assertEqual(cache.get_or_set("n", lambda: 1), 1)

        with self.assertRaises(TypeError):
            cache.get_or_set("m", lambda: "bad")

    def test_strict_types_with_generic_runtime_check(self):
        cache = MemoryCache[tuple, str](strict_types=True)
        cache.set((1, 2), "ok")

        with self.assertRaisesRegex(TypeError, r"field=key, expected=tuple, actual=str, key='1,2', value='ok'"):
            cache.set("1,2", "ok")

        with self.assertRaisesRegex(TypeError, r"field=value, expected=str, actual=int, key=\(3, 4\), value=123"):
            cache.set((3, 4), 123)

