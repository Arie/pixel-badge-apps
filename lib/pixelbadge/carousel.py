# Carousel: the visible stat tracked by identity across active-list rebuilds.


class Carousel:
    """The visible stat, tracked by IDENTITY. After a poll rebuilds the active
    list, the same stat keeps showing instead of jumping to whatever now sits at
    its old index."""

    def __init__(self, seq):
        self.seq = seq
        self.cur_id = seq[0]["id"]

    def refresh(self, seq):
        self.seq = seq
        if not any(s["id"] == self.cur_id for s in seq):
            self.cur_id = seq[0]["id"]  # current stat went idle/away

    def _pos(self):
        for i in range(len(self.seq)):
            if self.seq[i]["id"] == self.cur_id:
                return i
        return 0

    def step(self, n):
        self.cur_id = self.seq[(self._pos() + n) % len(self.seq)]["id"]

    def current(self):
        return self.seq[self._pos()]
