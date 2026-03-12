import unittest

from agile.utils.argparser import Argparser, Argument


class TestArgparser(unittest.TestCase):

    def setUp(self):
        self.parser = Argparser("参数解析工具")

    def test_list_args(self):
        self.parser.list_args(argv=[])

    def test_list_args_with_input(self):
        self.parser.add_args([
            Argument(arg_name="path", arg_type=str, required=True),
            Argument(arg_name="count", arg_type=int, required=False),
        ])

        args = self.parser.list_args(argv=["--path", "/tmp/demo", "--count", "3"])
        args_by_name = {arg.arg_name: arg for arg in args}

        self.assertEqual(args_by_name["path"].current_val, "/tmp/demo")
        self.assertEqual(args_by_name["count"].current_val, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
