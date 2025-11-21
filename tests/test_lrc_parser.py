"""Tests for LRC parser functionality."""

import unittest

from lrc_parser import ParsedLRC, parse_lrc_text, parse_timestamp


class TestLRCParser(unittest.TestCase):
    """Regression tests for timestamp and LRC parsing."""

    def test_parse_timestamp_valid(self):
        self.assertAlmostEqual(parse_timestamp("00:00.00"), 0.0)
        self.assertAlmostEqual(parse_timestamp("01:02.50"), 62.5)
        self.assertAlmostEqual(parse_timestamp("10:01"), 601.0)

    def test_parse_timestamp_invalid(self):
        with self.assertRaises(ValueError):
            parse_timestamp("invalid")

    def test_parse_lrc_text_returns_lines(self):
        content = """
[ti:Sample]
[ar:Tester]
[00:01.00]Hello world
[00:05.00]<00:05.00>Hello <00:05.40>again
        """
        parsed = parse_lrc_text(content)
        self.assertIsInstance(parsed, ParsedLRC)
        self.assertEqual(parsed.tags["ti"], "Sample")
        self.assertEqual(len(parsed.lines), 2)
        self.assertEqual(parsed.lines[0].text, "Hello world")
        self.assertEqual(len(parsed.lines[1].words), 2)
        self.assertEqual(parsed.lines[1].words[0].text, "Hello")
        self.assertEqual(parsed.lines[1].words[1].text, "again")

    def test_offset_tag_applied(self):
        content = """
[offset:500]
[00:00.00]Shifted
        """
        parsed = parse_lrc_text(content)
        self.assertAlmostEqual(parsed.lines[0].timestamp, 0.5)


if __name__ == "__main__":
    unittest.main()
