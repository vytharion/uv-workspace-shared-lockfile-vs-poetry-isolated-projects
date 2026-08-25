from __future__ import annotations

import unittest

from shared_lib.greetings import greet


class GreetTests(unittest.TestCase):
    def test_uses_provided_name(self) -> None:
        self.assertEqual(greet("Alex"), "Hello, Alex!")

    def test_trims_surrounding_whitespace(self) -> None:
        self.assertEqual(greet("  Dana  "), "Hello, Dana!")

    def test_falls_back_when_name_is_blank(self) -> None:
        self.assertEqual(greet("   "), "Hello, friend!")


if __name__ == "__main__":
    unittest.main()
