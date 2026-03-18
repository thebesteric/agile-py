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

