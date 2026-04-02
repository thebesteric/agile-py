import unittest

from agile.commons.enum import LabeledStrEnum


class Role(LabeledStrEnum):
    USER = ("user", "Normal user")
    ADMIN = ("admin", "Administrator")


class TestLabeledStrEnum(unittest.TestCase):

    def test_label_and_display(self):
        self.assertEqual(Role.USER.label, "Normal user")
        self.assertEqual(Role.USER.display(), "user (Normal user)")

    def test_get_all(self):
        self.assertEqual(
            Role.get_all(),
            [("user", "Normal user"), ("admin", "Administrator")],
        )

    def test_get_format_instructions(self):
        self.assertEqual(
            Role.get_format_instructions(),
            "  - user: Normal user\n  - admin: Administrator",
        )

    def test_get_format_instructions_with_title(self):
        self.assertEqual(
            Role.get_format_instructions(title="## Available roles:"),
            "## Available roles:\n  - user: Normal user\n  - admin: Administrator",
        )

    def test_from_value(self):
        self.assertEqual(Role.from_value("user"), Role.USER)
        self.assertIsNone(Role.from_value("missing"))
        self.assertIsNone(Role.from_value("USER"))

    def test_from_name(self):
        self.assertEqual(Role.from_name("ADMIN"), Role.ADMIN)
        self.assertIsNone(Role.from_name("missing"))
        self.assertIsNone(Role.from_name("admin"))


if __name__ == "__main__":
    unittest.main()
