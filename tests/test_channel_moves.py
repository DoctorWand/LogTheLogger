import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel_moves import find_moved_channels


def reorder(order_before, order_after):
    """Build position changes like Discord does when channels get reordered."""
    before = {cid: pos for pos, cid in enumerate(order_before)}
    after = {cid: pos for pos, cid in enumerate(order_after)}
    return [(cid, before[cid], after[cid]) for cid in order_before if before[cid] != after[cid]]


class FindMovedChannelsTest(unittest.TestCase):
    def test_top_to_bottom_reports_only_the_dragged_channel(self):
        changes = reorder(list(range(1, 11)), list(range(2, 11)) + [1])
        self.assertEqual(len(changes), 10)
        self.assertEqual(find_moved_channels(changes), [1])

    def test_bottom_to_top_reports_only_the_dragged_channel(self):
        changes = reorder(list(range(1, 11)), [10] + list(range(1, 10)))
        self.assertEqual(find_moved_channels(changes), [10])

    def test_move_into_the_middle(self):
        changes = reorder([1, 2, 3, 4, 5, 6], [2, 3, 4, 1, 5, 6])
        self.assertEqual(find_moved_channels(changes), [1])

    def test_swap_of_neighbours_reports_one_channel(self):
        changes = reorder([1, 2, 3], [2, 1, 3])
        self.assertEqual(len(find_moved_channels(changes)), 1)

    def test_single_change_is_the_move(self):
        self.assertEqual(find_moved_channels([(7, 0, 5)]), [7])

    def test_only_shifted_channels_report_nothing(self):
        # Dragged channel went to another category (logged separately); the rest
        # of the old category only closed the gap and kept their order.
        self.assertEqual(find_moved_channels([(2, 1, 0), (3, 2, 1), (4, 3, 2)]), [])

    def test_empty(self):
        self.assertEqual(find_moved_channels([]), [])


if __name__ == "__main__":
    unittest.main()
