"""Tk-free hit geometry for the virtual page grid; no thumbnails or widgets."""
import math


def card_box(page, columns, cell_width, row_height, gap):
    row, column = divmod(page - 1, columns)
    return (column * cell_width + gap / 2, row * row_height + gap / 2,
            (column + 1) * cell_width - gap / 2, (row + 1) * row_height - gap / 2)


def intersects(box, rectangle):
    x1, y1, x2, y2 = rectangle
    return box[0] <= x2 and box[2] >= x1 and box[1] <= y2 and box[3] >= y1


def marquee_pages(rectangle, count, columns, cell_width, row_height, gap):
    """Visit only rows crossed by the marquee, including pages outside the viewport."""
    first = max(0, math.floor(rectangle[1] / row_height))
    last = min(math.ceil(count / columns) - 1, math.floor(rectangle[3] / row_height))
    for row in range(first, last + 1):
        for column in range(columns):
            page = row * columns + column + 1
            if page <= count and intersects(card_box(page, columns, cell_width, row_height, gap), rectangle):
                yield page
