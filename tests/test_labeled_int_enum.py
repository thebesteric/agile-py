import unittest

from agile.commons.enum import LabeledIntEnum


class Status(LabeledIntEnum):
    PENDING = (0, "Pending")
    ACTIVE = (1, "Active")


class TestLabeledIntEnum(unittest.TestCase):

    def test_label_and_display(self):
        self.assertEqual(Status.PENDING.label, "Pending")
        self.assertEqual(Status.PENDING.display(), "0 (Pending)")

    def test_get_all(self):
        self.assertEqual(
            Status.get_all(),
            [(0, "Pending"), (1, "Active")],
        )

    def test_get_format_instructions(self):
        self.assertEqual(
            Status.get_format_instructions(),
            "  - 0: Pending\n  - 1: Active",
        )

    def test_get_format_instructions_with_title(self):
        self.assertEqual(
            Status.get_format_instructions(title="## Available statuses:"),
            "## Available statuses:\n  - 0: Pending\n  - 1: Active",
        )

    def test_from_value(self):
        self.assertEqual(Status.from_value(0), Status.PENDING)
        self.assertIsNone(Status.from_value(999))

    def test_from_name(self):
        self.assertEqual(Status.from_name("ACTIVE"), Status.ACTIVE)
        self.assertIsNone(Status.from_name("missing"))
        self.assertIsNone(Status.from_name("active"))


if __name__ == "__main__":
    unittest.main()

