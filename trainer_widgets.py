"""Responsive layout shared by option cards and gear controls."""

import tkinter as tk


class FlowFrame(tk.Frame):
    """Wrap controls to the available width instead of clipping a long row."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.items = []
        self.bind("<Configure>", self.arrange)

    def add(self, widget):
        self.items.append(widget)
        self.arrange()

    def arrange(self, event=None):
        width = max(200, self.winfo_width())
        x = y = row_height = 0
        for widget in self.items:
            item_width = min(width, widget.winfo_reqwidth())
            item_height = widget.winfo_reqheight()
            if x and x + item_width > width:
                x = 0
                y += row_height + 8
                row_height = 0
            widget.place(x=x, y=y, width=item_width, height=item_height)
            x += item_width + 8
            row_height = max(row_height, item_height)
        self.configure(height=y + row_height)
