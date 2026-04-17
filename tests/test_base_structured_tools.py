import unittest

from agile.agent.tools.base_structured_tools import BaseStructuredTools
from agile.agent.tools.tool_decorators import structured_tool


class DemoTools(BaseStructuredTools):

    @structured_tool
    def echo(self, text: str) -> str:
        """Echo input text."""
        return text


class TestBaseStructuredTools(unittest.TestCase):

    def test_registered_tool_supports_name_and_dunder_name(self):
        tools = DemoTools().get_tools()

        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool.name, "echo")
        self.assertEqual(tool.__name__, "echo")

    def test_registered_tool_is_exposed_on_instance(self):
        demo = DemoTools()

        self.assertTrue(hasattr(demo, "echo"))
        self.assertEqual(demo.echo.name, "echo")
        self.assertEqual(demo.echo.__name__, "echo")


if __name__ == "__main__":
    unittest.main(verbosity=2)

