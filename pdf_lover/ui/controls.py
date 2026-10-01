"""Consistent UI controls shared by the shell and feature pages."""
import customtkinter as ctk
from pdf_lover.ui.theme import COLORS as C, FONTS, RADIUS


class UIControls:
    def init_fonts(self):
        self.font_body = ctk.CTkFont(family=FONTS["body"], size=16)
        self.font_small = ctk.CTkFont(family=FONTS["body"], size=14)
        self.font_bold = ctk.CTkFont(family=FONTS["body"], size=17, weight="bold")

    def label(self, parent, text="", font=None, color="ink", **kwargs):
        return ctk.CTkLabel(parent, text=text, font=font or self.font_body,
                            text_color=C[color], anchor=kwargs.pop("anchor", "w"), **kwargs)

    def button(self, parent, text, command, primary=False, width=140, **kwargs):
        button = ctk.CTkButton(
            parent, text=text, command=command, width=width, height=44,
            corner_radius=RADIUS["control"], border_width=2,
            border_color=C["accent"] if primary else C["rule"],
            fg_color=C["accent"] if primary else C["surface"],
            hover_color=C["accent-hover"] if primary else C["soft"],
            text_color=C["accent-ink"] if primary else C["ink"],
            text_color_disabled=C["muted"], font=self.font_body, **kwargs,
        )
        # CustomTkinter buttons need explicit keyboard support and instant focus.
        button._canvas.configure(takefocus=1)
        resting_border = C["accent"] if primary else C["rule"]
        button._canvas.bind("<FocusIn>", lambda _: button.configure(border_color=C["focus"]))
        button._canvas.bind("<FocusOut>", lambda _: button.configure(border_color=resting_border))
        for key in ("<Return>", "<space>"):
            button._canvas.bind(key, lambda _, b=button: b.invoke())
        fill = C["accent"] if primary else C["surface"]
        pressed = C["accent-pressed"] if primary else C["soft"]
        def press(_):
            if button.cget("state") == "normal":
                button._resting_fill = button.cget("fg_color")
                button.configure(fg_color=pressed)
        def release(_):
            if button.cget("state") == "normal":
                button.configure(fg_color=getattr(button, "_resting_fill", fill))
        button.bind("<ButtonPress-1>", press)
        button.bind("<ButtonRelease-1>", release)
        return button

    def _entry_focus(self, entry):
        entry.bind("<FocusIn>", lambda _: entry.configure(border_color=C["focus"]))
        entry.bind("<FocusOut>", lambda _: entry.configure(border_color=C["rule"]))

    @staticmethod
    def shorten(text, limit=42):
        if len(text) <= limit:
            return text
        return text[:limit - 15] + "…" + text[-14:]

    def fit_filename(self, text, width):
        if self.font_bold.measure(text) <= width:
            return text
        end = text[-10:]
        prefix = text[:-10]
        while prefix and self.font_bold.measure(prefix + "…" + end) > width:
            prefix = prefix[:-1]
        return prefix + "…" + end
