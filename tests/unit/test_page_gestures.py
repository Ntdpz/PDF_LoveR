"""Marquee geometry contracts, including gaps and offscreen document pages."""
import unittest
from pdf_lover.ui.page_gestures import marquee_pages


class MarqueeTests(unittest.TestCase):
    def pick(self, rect, count=10):
        return list(marquee_pages(rect, count, 4, 100, 150, 8))

    def test_two_rows_and_columns(self):
        self.assertEqual(self.pick((10, 10, 190, 290)), [1, 2, 5, 6])

    def test_gap_does_not_select_adjacent_cards(self):
        self.assertEqual(self.pick((97, 10, 103, 140)), [])

    def test_partial_final_row(self):
        self.assertEqual(self.pick((0, 0, 400, 10000)), list(range(1, 11)))

    def test_outside_document(self):
        self.assertEqual(self.pick((0, 10000, 400, 11000)), [])

    def test_intersection_includes_card_edge(self):
        self.assertEqual(self.pick((96, 146, 96, 146)), [1])

    def test_large_document_offscreen_row(self):
        self.assertEqual(self.pick((110, 3749910, 190, 3749990), 100000), [99998])
