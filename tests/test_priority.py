import unittest

from src.domain.priority import Priority


class TestPriority(unittest.TestCase):

    def test_supported_priorities(self):
        self.assertEqual(Priority("Low"), Priority.LOW)
        self.assertEqual(Priority("Medium"), Priority.MEDIUM)
        self.assertEqual(Priority("High"), Priority.HIGH)
        self.assertEqual(Priority("Critical"), Priority.CRITICAL)

    def test_unsupported_priority(self):
        with self.assertRaises(ValueError):
            Priority("Extreme")

    def test_only_four_priorities_exist(self):
        self.assertEqual(
            {priority.value for priority in Priority},
            {"Low", "Medium", "High", "Critical"}
        )


if __name__ == "__main__":
    unittest.main()