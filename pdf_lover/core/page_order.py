"""Pure ordering model shared by the UI and headless tools."""
def move_selected(order, selected, before):
    """Insert selected identities before a slot in the original order (zero based)."""
    picked = set(selected)
    moving = [p for p in order if p in picked]
    remaining = [p for p in order if p not in picked]
    slot = sum(p not in picked for p in order[:max(0, min(len(order), before))])
    return tuple(remaining[:slot] + moving + remaining[slot:])


class OrderHistory:
    """Bounded immutable page-identity snapshots; never holds PDF images/objects."""
    LIMIT = 32
    PAGE_BUDGET = 100000

    def __init__(self):
        self.undo_stack, self.redo_stack = [], []

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()

    def _trim(self, stack):
        while len(stack) > self.LIMIT or sum(len(item[0]) for item in stack) > self.PAGE_BUDGET:
            stack.pop(0)

    def record(self, state):
        self.undo_stack.append(state)
        self._trim(self.undo_stack)
        self.redo_stack.clear()

    def step(self, state, redo=False):
        source, target = (self.redo_stack, self.undo_stack) if redo else (self.undo_stack, self.redo_stack)
        if not source:
            return None
        target.append(state)
        self._trim(target)
        return source.pop()
