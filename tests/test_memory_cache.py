import unittest

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
