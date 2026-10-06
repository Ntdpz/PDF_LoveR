"""Pure ordering model shared by the UI and headless tools."""
def move_selected(order, selected, before):
    """Insert selected identities before a slot in the original order (zero based)."""
    picked = set(selected)
    moving = [p for p in order if p in picked]
    remaining = [p for p in order if p not in picked]
    slot = sum(p not in picked for p in order[:max(0, min(len(order), before))])
    return tuple(remaining[:slot] + moving + remaining[slot:])
