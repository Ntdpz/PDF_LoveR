"""Shared native document icon vocabulary."""
import customtkinter as ctk
from PIL import Image, ImageDraw
from pdf_lover.ui.theme import COLORS as C


def document_icon(size=48, color="accent"):
    """One consistent outline icon, drawn at 2x for crisp Windows scaling."""
    image = Image.new("RGBA", (96, 96))
    draw = ImageDraw.Draw(image)
    ink = C[color]
    draw.line([(28, 14), (56, 14), (72, 30), (72, 80), (28, 80), (28, 14)], fill=ink, width=4, joint="curve")
    draw.line([(56, 14), (56, 30), (72, 30)], fill=ink, width=4)
    draw.line([(39, 48), (61, 48)], fill=ink, width=4)
    draw.line([(39, 60), (55, 60)], fill=ink, width=4)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))


def tool_icon(kind, color="muted", size=28):
    """A single outline vocabulary for document tools, rendered locally at 2x."""
    image = Image.new("RGBA", (64, 64))
    draw = ImageDraw.Draw(image)
    ink = C[color]
    if kind in ("image", "slides"):
        draw.rounded_rectangle((10, 14, 54, 50), radius=3, outline=ink, width=3)
        if kind == "image":
            draw.ellipse((37, 21, 43, 27), outline=ink, width=2)
            draw.line([(13, 46), (26, 32), (35, 40), (42, 33), (51, 45)], fill=ink, width=3)
        else:
            draw.line([(32, 50), (32, 58)], fill=ink, width=3)
            draw.line([(23, 58), (41, 58)], fill=ink, width=3)
            draw.line([(19, 25), (45, 25)], fill=ink, width=3)
            draw.line([(19, 34), (38, 34)], fill=ink, width=3)
    elif kind == "lock":
        draw.arc((20, 8, 44, 40), 180, 360, fill=ink, width=3)
        draw.rounded_rectangle((14, 28, 50, 55), radius=3, outline=ink, width=3)
        draw.line([(32, 38), (32, 46)], fill=ink, width=3)
    elif kind == "crop":
        draw.line([(18, 8), (18, 46), (56, 46)], fill=ink, width=3)
        draw.line([(8, 18), (46, 18), (46, 56)], fill=ink, width=3)
    elif kind == "table":
        draw.rounded_rectangle((10, 12, 54, 52), radius=2, outline=ink, width=3)
        for y in (25, 38):
            draw.line([(10, y), (54, y)], fill=ink, width=2)
        for x in (25, 40):
            draw.line([(x, 12), (x, 52)], fill=ink, width=2)
    elif kind in ("import", "export", "compress", "split"):
        draw.line([(16, 12), (16, 52), (48, 52), (48, 12)], fill=ink, width=3)
        if kind == "split":
            draw.line([(23, 25), (41, 25)], fill=ink, width=3)
            draw.line([(23, 39), (41, 39)], fill=ink, width=3)
        else:
            down = kind != "export"
            start, end = (9, 36) if down else (38, 10)
            draw.line([(32, start), (32, end)], fill=ink, width=3)
            delta = -8 if down else 8
            draw.line([(24, end + delta), (32, end), (40, end + delta)], fill=ink, width=3)
    elif kind == "edit":
        draw.line([(14, 49), (18, 37), (43, 12), (52, 21), (27, 46), (14, 49)], fill=ink, width=3)
        draw.line([(36, 19), (45, 28)], fill=ink, width=3)
    else:
        if kind == "pages":
            draw.line([(10, 17), (10, 55), (41, 55)], fill=ink, width=3)
        draw.line([(19, 9), (41, 9), (53, 21), (53, 48), (19, 48), (19, 9)], fill=ink, width=3)
        draw.line([(41, 9), (41, 21), (53, 21)], fill=ink, width=3)
        draw.line([(26, 29), (45, 29)], fill=ink, width=3)
        draw.line([(26, 37), (40, 37)], fill=ink, width=3)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
