"""Work out which channel was actually moved in a Discord reorder.

Dragging one channel in Discord rewrites the position of every channel it
passes, and the gateway fires on_guild_channel_update for each of them. Moving
a channel from the top to the bottom therefore produces one update per channel
on the server, although the user moved exactly one.

Given all position changes that arrived together, the channels the user did
NOT move keep their order relative to each other. The largest group of
channels that kept their relative order is the longest increasing subsequence
of their old ranks (read in new order). Everything outside that group is what
was actually moved.
"""

from bisect import bisect_left


def find_moved_channels(changes):
    """Return the ids of the channels that were actually moved.

    changes: iterable of (channel_id, before_position, after_position) for the
    channels whose position changed in one reorder. Ties in position are
    broken by id, matching how Discord sorts channels.
    """
    changes = list(changes)
    if len(changes) <= 1:
        # A single position change is the move itself, there is nothing to filter
        return [cid for cid, _, _ in changes]

    before_order = sorted(changes, key=lambda c: (c[1], c[0]))
    before_rank = {c[0]: rank for rank, c in enumerate(before_order)}
    after_order = sorted(changes, key=lambda c: (c[2], c[0]))
    sequence = [before_rank[c[0]] for c in after_order]

    # Longest increasing subsequence (patience sorting), tracking indices
    tails = []        # tails[k] = index into sequence of the smallest tail of length k+1
    tail_values = []
    parent = [-1] * len(sequence)
    for i, value in enumerate(sequence):
        k = bisect_left(tail_values, value)
        if k > 0:
            parent[i] = tails[k - 1]
        if k == len(tails):
            tails.append(i)
            tail_values.append(value)
        else:
            tails[k] = i
            tail_values[k] = value

    kept = set()
    i = tails[-1] if tails else -1
    while i != -1:
        kept.add(i)
        i = parent[i]

    return [after_order[i][0] for i in range(len(after_order)) if i not in kept]
