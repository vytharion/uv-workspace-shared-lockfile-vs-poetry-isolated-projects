from __future__ import annotations

import unittest

from app.main import welcome


class WelcomeTests(unittest.TestCase):
    def test_prefixes_shared_greeting(self) -> None:
        self.assertEqual(welcome("Alex"), "[app] Hello, Alex!")

    def test_delegates_blank_fallback_to_shared_lib(self) -> None:
        self.assertEqual(welcome(""), "[app] Hello, friend!")


if __name__ == "__main__":
    unittest.main()
