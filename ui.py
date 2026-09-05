"""
Tkinter UI for the local iLovePDF-style desktop app.

Layout: a red-accented sidebar of tools (mirrors ilovepdf.com's tool grid)
on the left, a swappable content area on the right. Every PDF operation
lives in core.py; this module is purely presentation + orchestration.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import core


def resource_path(relative_path: str) -> str:
    """Resolve a bundled asset path, both when run from source and when
    frozen into a single-file executable by PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

RED = "#E5322D"
RED_DARK = "#C81E1E"
BG = "#F4F6F8"
SIDEBAR_BG = "#FFFFFF"
CARD_BG = "#FFFFFF"
TEXT_DARK = "#22262A"
TEXT_MUTED = "#6B7280"
BORDER = "#E2E5E9"

FONT_FAMILY = "Segoe UI"


def open_in_explorer(path: str) -> None:
    path = os.path.abspath(path)
    try:
        if os.path.isfile(path):
            subprocess.run(["explorer", "/select,", path])
        else:
            os.startfile(path)  # noqa: S606 - user-initiated, Windows only
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tool registry (mirrors the ilovepdf.com tool grid / ilovepdf-nodejs task types)
# ---------------------------------------------------------------------------

TOOLS = [
    {"key": "merge", "label": "Merge PDF", "icon": "⊕", "category": "Organize",
     "desc": "Combine multiple PDFs into a single file, in the order you choose."},
    {"key": "split", "label": "Split PDF", "icon": "✂", "category": "Organize",
     "desc": "Split a PDF by fixed page count or by custom page ranges."},
    {"key": "remove", "label": "Remove Pages", "icon": "✖", "category": "Organize",
     "desc": "Delete specific pages from a PDF."},
    {"key": "extract", "label": "Extract Pages", "icon": "↪", "category": "Organize",
     "desc": "Pull selected pages out into a brand new PDF."},
    {"key": "rotate", "label": "Rotate PDF", "icon": "↻", "category": "Organize",
     "desc": "Rotate all or selected pages by 90, 180 or 270 degrees."},
    {"key": "compress", "label": "Compress PDF", "icon": "⚙", "category": "Optimize",
     "desc": "Shrink file size by recompressing embedded images."},
    {"key": "watermark", "label": "Watermark", "icon": "☷", "category": "Edit",
     "desc": "Stamp text over every page (opacity, angle, size)."},
    {"key": "pdf2img", "label": "PDF to Image", "icon": "▣", "category": "Convert",
     "desc": "Render each page to a PNG or JPG image."},
    {"key": "img2pdf", "label": "Image to PDF", "icon": "▢", "category": "Convert",
     "desc": "Combine one or more images into a single PDF."},
    {"key": "pdf2text", "label": "PDF to Text", "icon": "≡", "category": "Convert",
     "desc": "Extract all text content from a PDF into a .txt file."},
    {"key": "protect", "label": "Protect PDF", "icon": "\U0001F512", "category": "Security",
     "desc": "Encrypt a PDF with a password."},
    {"key": "unlock", "label": "Unlock PDF", "icon": "\U0001F513", "category": "Security",
     "desc": "Remove password protection (password required)."},
]

CATEGORY_ORDER = ["Organize", "Optimize", "Edit", "Convert", "Security"]


# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------

class FileListPicker(ttk.Frame):
    """Listbox of file paths with add / remove / reorder controls."""

    def __init__(self, master, filetypes, multiple=True, allow_reorder=True):
        super().__init__(master)
        self.filetypes = filetypes
        self.multiple = multiple
        self.on_change = None

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_frame, selectmode="extended", height=7,
            font=(FONT_FAMILY, 10), bg="white", relief="solid", borderwidth=1,
            highlightthickness=0, activestyle="none",
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", pady=(6, 0))

        ttk.Button(btn_row, text="Add Files…", command=self._add_files).pack(side="left")
        ttk.Button(btn_row, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Clear", command=self._clear).pack(side="left")

        if allow_reorder:
            ttk.Button(btn_row, text="↑ Up", width=6, command=self._move_up).pack(side="right", padx=(6, 0))
            ttk.Button(btn_row, text="↓ Down", width=8, command=self._move_down).pack(side="right")

    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Select file(s)", filetypes=self.filetypes)
        if not paths:
            return
        if not self.multiple:
            self.listbox.delete(0, "end")
            self.listbox.insert("end", paths[0])
        else:
            for p in paths:
                self.listbox.insert("end", p)
        self._changed()

    def _remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
        self._changed()

    def _clear(self):
        self.listbox.delete(0, "end")
        self._changed()

    def _move_up(self):
        sel = list(self.listbox.curselection())
        for i in sel:
            if i == 0:
                continue
            text = self.listbox.get(i)
            self.listbox.delete(i)
            self.listbox.insert(i - 1, text)
            self.listbox.selection_set(i - 1)
        self._changed()

    def _move_down(self):
        sel = list(self.listbox.curselection())
        for i in reversed(sel):
            if i >= self.listbox.size() - 1:
                continue
            text = self.listbox.get(i)
            self.listbox.delete(i)
            self.listbox.insert(i + 1, text)
            self.listbox.selection_set(i + 1)
        self._changed()

    def _changed(self):
        if self.on_change:
            self.on_change(self.get_paths())

    def get_paths(self) -> list[str]:
        return list(self.listbox.get(0, "end"))

    def set_paths(self, paths: list[str]):
        self.listbox.delete(0, "end")
        for p in paths:
            self.listbox.insert("end", p)
        self._changed()


class PathEntry(ttk.Frame):
    """Single-line path entry with a Browse button. mode: 'open' | 'save' | 'dir'"""

    def __init__(self, master, mode="open", filetypes=(("All files", "*.*"),),
                 defaultextension="", initialfile=""):
        super().__init__(master)
        self.mode = mode
        self.filetypes = filetypes
        self.defaultextension = defaultextension
        self.initialfile = initialfile
        self.on_change = None

        self.var = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.var)
        entry.pack(side="left", fill="x", expand=True)
        self.var.trace_add("write", lambda *_: self.on_change and self.on_change(self.var.get()))
        ttk.Button(self, text="Browse…", command=self._browse).pack(side="left", padx=(6, 0))

    def _browse(self):
        if self.mode == "open":
            path = filedialog.askopenfilename(title="Select file", filetypes=self.filetypes)
        elif self.mode == "save":
            path = filedialog.asksaveasfilename(
                title="Save as", filetypes=self.filetypes,
                defaultextension=self.defaultextension, initialfile=self.initialfile,
            )
        else:
            path = filedialog.askdirectory(title="Select folder")
        if path:
            self.var.set(path)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str):
        self.var.set(value)


class LabeledEntry(ttk.Frame):
    def __init__(self, master, label, default="", show=None, width=20):
        super().__init__(master)
        ttk.Label(self, text=label).pack(anchor="w")
        self.var = tk.StringVar(value=default)
        ttk.Entry(self, textvariable=self.var, show=show, width=width).pack(fill="x", pady=(2, 0))

    def get(self) -> str:
        return self.var.get()


# ---------------------------------------------------------------------------
# Base tool page
# ---------------------------------------------------------------------------

class ToolPage(ttk.Frame):
    def __init__(self, master, app, tool):
        super().__init__(master, style="Content.TFrame")
        self.app = app
        self.tool = tool
        self._busy_widgets: list[tk.Widget] = []

        header = ttk.Frame(self, style="Content.TFrame")
        header.pack(fill="x", padx=28, pady=(24, 8))

        back = ttk.Button(header, text="← Home", command=app.show_home, style="Link.TButton")
        back.pack(anchor="w")

        title_row = ttk.Frame(header, style="Content.TFrame")
        title_row.pack(fill="x", pady=(10, 0))
        ttk.Label(title_row, text=tool["icon"], font=(FONT_FAMILY, 22), foreground=RED,
                  background=BG).pack(side="left", padx=(0, 10))
        ttk.Label(title_row, text=tool["label"], font=(FONT_FAMILY, 20, "bold"),
                  foreground=TEXT_DARK, background=BG).pack(side="left")

        ttk.Label(header, text=tool["desc"], font=(FONT_FAMILY, 10), foreground=TEXT_MUTED,
                  background=BG, wraplength=760, justify="left").pack(anchor="w", pady=(4, 0))

        body_container = ttk.Frame(self, style="Card.TFrame")
        body_container.pack(fill="both", expand=True, padx=28, pady=(0, 12))
        self.body = ttk.Frame(body_container, style="Card.TFrame", padding=20)
        self.body.pack(fill="both", expand=True)

        footer = ttk.Frame(self, style="Content.TFrame")
        footer.pack(fill="x", padx=28, pady=(0, 20))

        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(footer, textvariable=self.status_var, background=BG,
                                       foreground=TEXT_MUTED, font=(FONT_FAMILY, 9))
        self.status_label.pack(anchor="w")

    # -- helpers for subclasses -------------------------------------------------

    def section(self, text):
        ttk.Label(self.body, text=text, font=(FONT_FAMILY, 11, "bold"),
                  foreground=TEXT_DARK, background=CARD_BG).pack(anchor="w", pady=(0, 6))

    def spacer(self, h=14):
        ttk.Frame(self.body, height=h, style="Card.TFrame").pack()

    def make_run_button(self, text, command):
        btn = tk.Button(
            self.body, text=text, command=command, bg=RED, fg="white",
            activebackground=RED_DARK, activeforeground="white",
            font=(FONT_FAMILY, 11, "bold"), relief="flat", padx=18, pady=8,
            cursor="hand2", borderwidth=0,
        )
        self._busy_widgets.append(btn)
        return btn

    def set_status(self, text, error=False):
        self.status_var.set(text)
        self.status_label.configure(foreground=(RED if error else TEXT_MUTED))

    def start_busy(self, message="Processing…"):
        for w in self._busy_widgets:
            try:
                w.configure(state="disabled")
            except tk.TclError:
                pass
        self.progress.pack(fill="x", pady=(0, 6))
        self.progress.start(12)
        self.set_status(message)

    def stop_busy(self):
        self.progress.stop()
        self.progress.pack_forget()
        for w in self._busy_widgets:
            try:
                w.configure(state="normal")
            except tk.TclError:
                pass

    def run_task(self, func, args=(), busy_message="Processing…", on_success=None, success_message=None):
        """Run `func(*args)` on a background thread; marshal result back to the UI thread."""
        self.start_busy(busy_message)

        def worker():
            try:
                result = func(*args)
                error = None
            except Exception as exc:  # noqa: BLE001 - surfaced to the user as-is
                result, error = None, exc
            self.after(0, lambda: self._finish(result, error, on_success, success_message))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, result, error, on_success, success_message):
        self.stop_busy()
        if error is not None:
            self.set_status(f"Error: {error}", error=True)
            messagebox.showerror("Operation failed", str(error))
            return
        if success_message:
            self.set_status(success_message)
        if on_success:
            on_success(result)


# ---------------------------------------------------------------------------
# Individual tool pages
# ---------------------------------------------------------------------------

PDF_FILETYPES = (("PDF files", "*.pdf"), ("All files", "*.*"))
IMAGE_FILETYPES = (("Image files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"), ("All files", "*.*"))


class MergePage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "merge")
        super().__init__(master, app, tool)

        self.section("1. Add PDFs (drag with Up/Down to reorder)")
        self.picker = FileListPicker(self.body, PDF_FILETYPES, multiple=True)
        self.picker.pack(fill="both", expand=True)

        self.spacer()
        self.section("2. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="merged.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Merge PDFs", self._run).pack(anchor="w")

    def _run(self):
        paths = self.picker.get_paths()
        out = self.output.get()
        if len(paths) < 2:
            messagebox.showwarning("Merge PDF", "Add at least two PDF files.")
            return
        if not out:
            messagebox.showwarning("Merge PDF", "Choose an output file.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", f"Merged {len(paths)} files.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(core.merge_pdfs, (paths, out), "Merging PDFs…", on_success, "Merge complete.")


class SplitPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "split")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.pack(fill="x")

        self.spacer()
        self.section("2. Split mode")
        self.mode_var = tk.StringVar(value="every_n")
        mode_row = ttk.Frame(self.body, style="Card.TFrame")
        mode_row.pack(fill="x")
        ttk.Radiobutton(mode_row, text="Every N pages", value="every_n", variable=self.mode_var,
                         command=self._toggle_mode).pack(side="left")
        ttk.Radiobutton(mode_row, text="Custom ranges", value="ranges", variable=self.mode_var,
                         command=self._toggle_mode).pack(side="left", padx=(16, 0))

        self.n_entry = LabeledEntry(self.body, "Pages per file", default="1", width=10)
        self.n_entry.pack(anchor="w", pady=(10, 0))

        self.ranges_entry = LabeledEntry(
            self.body, "Ranges (e.g. 1-3,4-6,7)  each group -> one file", default="", width=40
        )

        self.spacer()
        self.section("3. Output folder")
        self.output_dir = PathEntry(self.body, mode="dir")
        self.output_dir.pack(fill="x")

        self.spacer()
        self.make_run_button("Split PDF", self._run).pack(anchor="w")
        self._toggle_mode()

    def _toggle_mode(self):
        if self.mode_var.get() == "every_n":
            self.ranges_entry.pack_forget()
            self.n_entry.pack(anchor="w", pady=(10, 0))
        else:
            self.n_entry.pack_forget()
            self.ranges_entry.pack(anchor="w", pady=(10, 0))

    def _run(self):
        inp = self.input.get()
        out_dir = self.output_dir.get()
        if not inp or not out_dir:
            messagebox.showwarning("Split PDF", "Select an input file and an output folder.")
            return

        mode = self.mode_var.get()
        try:
            n = int(self.n_entry.get()) if mode == "every_n" else 1
        except ValueError:
            messagebox.showwarning("Split PDF", "Pages per file must be a number.")
            return

        def on_success(outputs):
            self.set_status(f"Created {len(outputs)} file(s) in {out_dir}")
            if messagebox.askyesno("Done", f"Created {len(outputs)} file(s).\nOpen the output folder?"):
                open_in_explorer(out_dir)

        self.run_task(
            core.split_pdf,
            (inp, out_dir, mode, n, self.ranges_entry.get()),
            "Splitting PDF…", on_success, None,
        )


class RemovePagesPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "remove")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.on_change = self._on_input_change
        self.input.pack(fill="x")
        self.info_var = tk.StringVar(value="")
        ttk.Label(self.body, textvariable=self.info_var, foreground=TEXT_MUTED,
                  background=CARD_BG, font=(FONT_FAMILY, 9)).pack(anchor="w", pady=(4, 0))

        self.spacer()
        self.section("2. Pages to remove")
        self.pages_entry = LabeledEntry(self.body, "e.g. 2,4-6", width=40)
        self.pages_entry.pack(anchor="w")

        self.spacer()
        self.section("3. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="output.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Remove Pages", self._run).pack(anchor="w")

    def _on_input_change(self, path):
        if not path or not os.path.isfile(path):
            self.info_var.set("")
            return
        try:
            info = core.get_pdf_info(path)
            self.info_var.set(f"{info.page_count} page(s)")
        except Exception as exc:
            self.info_var.set(str(exc))

    def _run(self):
        inp, out = self.input.get(), self.output.get()
        if not inp or not out:
            messagebox.showwarning("Remove Pages", "Select an input file and an output file.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", "Pages removed.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(core.remove_pages, (inp, out, self.pages_entry.get()),
                      "Removing pages…", on_success, "Done.")


class ExtractPagesPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "extract")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.on_change = self._on_input_change
        self.input.pack(fill="x")
        self.info_var = tk.StringVar(value="")
        ttk.Label(self.body, textvariable=self.info_var, foreground=TEXT_MUTED,
                  background=CARD_BG, font=(FONT_FAMILY, 9)).pack(anchor="w", pady=(4, 0))

        self.spacer()
        self.section("2. Pages to keep")
        self.pages_entry = LabeledEntry(self.body, "e.g. 1-3,7", width=40)
        self.pages_entry.pack(anchor="w")

        self.spacer()
        self.section("3. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="extracted.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Extract Pages", self._run).pack(anchor="w")

    def _on_input_change(self, path):
        if not path or not os.path.isfile(path):
            self.info_var.set("")
            return
        try:
            info = core.get_pdf_info(path)
            self.info_var.set(f"{info.page_count} page(s)")
        except Exception as exc:
            self.info_var.set(str(exc))

    def _run(self):
        inp, out = self.input.get(), self.output.get()
        if not inp or not out:
            messagebox.showwarning("Extract Pages", "Select an input file and an output file.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", "Pages extracted.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(core.extract_pages, (inp, out, self.pages_entry.get()),
                      "Extracting pages…", on_success, "Done.")


class RotatePage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "rotate")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.on_change = self._on_input_change
        self.input.pack(fill="x")
        self.info_var = tk.StringVar(value="")
        ttk.Label(self.body, textvariable=self.info_var, foreground=TEXT_MUTED,
                  background=CARD_BG, font=(FONT_FAMILY, 9)).pack(anchor="w", pady=(4, 0))

        self.spacer()
        self.section("2. Rotation")
        self.angle_var = tk.StringVar(value="90")
        angle_row = ttk.Frame(self.body, style="Card.TFrame")
        angle_row.pack(fill="x")
        for val in ("90", "180", "270"):
            ttk.Radiobutton(angle_row, text=f"{val}°", value=val, variable=self.angle_var).pack(side="left", padx=(0, 12))

        self.spacer(8)
        self.pages_entry = LabeledEntry(self.body, "Pages (blank = all)", default="", width=40)
        self.pages_entry.pack(anchor="w")

        self.spacer()
        self.section("3. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="rotated.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Rotate PDF", self._run).pack(anchor="w")

    def _on_input_change(self, path):
        if not path or not os.path.isfile(path):
            self.info_var.set("")
            return
        try:
            info = core.get_pdf_info(path)
            self.info_var.set(f"{info.page_count} page(s)")
        except Exception as exc:
            self.info_var.set(str(exc))

    def _run(self):
        inp, out = self.input.get(), self.output.get()
        if not inp or not out:
            messagebox.showwarning("Rotate PDF", "Select an input file and an output file.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", "PDF rotated.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(
            core.rotate_pdf,
            (inp, out, int(self.angle_var.get()), self.pages_entry.get()),
            "Rotating…", on_success, "Done.",
        )


class CompressPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "compress")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.pack(fill="x")

        self.spacer()
        self.section("2. Compression level")
        self.level_var = tk.StringVar(value="recommended")
        for val, label in (("low", "Low (best quality)"), ("recommended", "Recommended"), ("extreme", "Extreme (smallest size)")):
            ttk.Radiobutton(self.body, text=label, value=val, variable=self.level_var).pack(anchor="w")

        self.spacer()
        self.section("3. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="compressed.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Compress PDF", self._run).pack(anchor="w")

    def _run(self):
        inp, out = self.input.get(), self.output.get()
        if not inp or not out:
            messagebox.showwarning("Compress PDF", "Select an input file and an output file.")
            return

        def on_success(sizes):
            orig, new = sizes
            pct = (1 - new / orig) * 100 if orig else 0
            msg = f"{core.format_bytes(orig)} → {core.format_bytes(new)} ({pct:.0f}% smaller)"
            self.set_status(msg)
            if messagebox.askyesno("Done", f"{msg}\n\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(core.compress_pdf, (inp, out, self.level_var.get()),
                      "Compressing…", on_success, None)


class WatermarkPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "watermark")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.pack(fill="x")

        self.spacer()
        self.section("2. Watermark text")
        self.text_entry = LabeledEntry(self.body, "Text", default="CONFIDENTIAL", width=40)
        self.text_entry.pack(anchor="w")

        opts_row = ttk.Frame(self.body, style="Card.TFrame")
        opts_row.pack(fill="x", pady=(10, 0))
        self.opacity_entry = LabeledEntry(opts_row, "Opacity (0-1)", default="0.3", width=10)
        self.opacity_entry.pack(side="left")
        self.rotation_entry = LabeledEntry(opts_row, "Rotation (deg)", default="45", width=10)
        self.rotation_entry.pack(side="left", padx=(16, 0))
        self.size_entry = LabeledEntry(opts_row, "Font size", default="40", width=10)
        self.size_entry.pack(side="left", padx=(16, 0))

        self.spacer()
        self.section("3. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="watermarked.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Add Watermark", self._run).pack(anchor="w")

    def _run(self):
        inp, out = self.input.get(), self.output.get()
        if not inp or not out:
            messagebox.showwarning("Watermark", "Select an input file and an output file.")
            return
        try:
            opacity = float(self.opacity_entry.get())
            rotation = int(self.rotation_entry.get())
            font_size = int(self.size_entry.get())
        except ValueError:
            messagebox.showwarning("Watermark", "Opacity/rotation/font size must be numbers.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", "Watermark added.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(
            core.add_watermark,
            (inp, out, self.text_entry.get(), opacity, rotation, font_size),
            "Adding watermark…", on_success, "Done.",
        )


class PdfToImagesPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "pdf2img")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.pack(fill="x")

        self.spacer()
        self.section("2. Options")
        opts_row = ttk.Frame(self.body, style="Card.TFrame")
        opts_row.pack(fill="x")
        ttk.Label(opts_row, text="Format").pack(side="left")
        self.fmt_var = tk.StringVar(value="png")
        ttk.Combobox(opts_row, textvariable=self.fmt_var, values=["png", "jpg"], width=6,
                     state="readonly").pack(side="left", padx=(6, 20))
        self.dpi_entry = LabeledEntry(opts_row, "DPI", default="150", width=8)
        self.dpi_entry.pack(side="left")

        self.spacer()
        self.section("3. Output folder")
        self.output_dir = PathEntry(self.body, mode="dir")
        self.output_dir.pack(fill="x")

        self.spacer()
        self.make_run_button("Convert to Images", self._run).pack(anchor="w")

    def _run(self):
        inp, out_dir = self.input.get(), self.output_dir.get()
        if not inp or not out_dir:
            messagebox.showwarning("PDF to Image", "Select an input file and an output folder.")
            return
        try:
            dpi = int(self.dpi_entry.get())
        except ValueError:
            messagebox.showwarning("PDF to Image", "DPI must be a number.")
            return

        def on_success(outputs):
            self.set_status(f"Created {len(outputs)} image(s) in {out_dir}")
            if messagebox.askyesno("Done", f"Created {len(outputs)} image(s).\nOpen the output folder?"):
                open_in_explorer(out_dir)

        self.run_task(core.pdf_to_images, (inp, out_dir, self.fmt_var.get(), dpi),
                      "Rendering pages…", on_success, None)


class ImagesToPdfPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "img2pdf")
        super().__init__(master, app, tool)

        self.section("1. Add images (in the order they should appear)")
        self.picker = FileListPicker(self.body, IMAGE_FILETYPES, multiple=True)
        self.picker.pack(fill="both", expand=True)

        self.spacer()
        self.section("2. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="images.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Create PDF", self._run).pack(anchor="w")

    def _run(self):
        paths = self.picker.get_paths()
        out = self.output.get()
        if not paths:
            messagebox.showwarning("Image to PDF", "Add at least one image.")
            return
        if not out:
            messagebox.showwarning("Image to PDF", "Choose an output file.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", "PDF created.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(core.images_to_pdf, (paths, out), "Building PDF…", on_success, "Done.")


class PdfToTextPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "pdf2text")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.pack(fill="x")

        self.spacer()
        self.section("2. Password (only if the PDF is protected)")
        self.password_entry = LabeledEntry(self.body, "Password", default="", show="*", width=30)
        self.password_entry.pack(anchor="w")

        self.spacer()
        self.section("3. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=(("Text files", "*.txt"),),
                                 defaultextension=".txt", initialfile="extracted.txt")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Extract Text", self._run).pack(anchor="w")

    def _run(self):
        inp, out = self.input.get(), self.output.get()
        if not inp or not out:
            messagebox.showwarning("PDF to Text", "Select an input file and an output file.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", "Text extracted.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(core.pdf_to_text, (inp, out, self.password_entry.get() or None),
                      "Extracting text…", on_success, "Done.")


class ProtectPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "protect")
        super().__init__(master, app, tool)

        self.section("1. Select a PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.pack(fill="x")

        self.spacer()
        self.section("2. Set a password")
        pw_row = ttk.Frame(self.body, style="Card.TFrame")
        pw_row.pack(fill="x")
        self.password_entry = LabeledEntry(pw_row, "Password", show="*", width=25)
        self.password_entry.pack(side="left")
        self.confirm_entry = LabeledEntry(pw_row, "Confirm password", show="*", width=25)
        self.confirm_entry.pack(side="left", padx=(16, 0))

        self.spacer()
        self.section("3. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="protected.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Protect PDF", self._run).pack(anchor="w")

    def _run(self):
        inp, out = self.input.get(), self.output.get()
        pw, confirm = self.password_entry.get(), self.confirm_entry.get()
        if not inp or not out:
            messagebox.showwarning("Protect PDF", "Select an input file and an output file.")
            return
        if not pw:
            messagebox.showwarning("Protect PDF", "Enter a password.")
            return
        if pw != confirm:
            messagebox.showwarning("Protect PDF", "Passwords do not match.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", "PDF protected.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(core.protect_pdf, (inp, out, pw), "Encrypting…", on_success, "Done.")


class UnlockPage(ToolPage):
    def __init__(self, master, app):
        tool = next(t for t in TOOLS if t["key"] == "unlock")
        super().__init__(master, app, tool)

        self.section("1. Select a protected PDF")
        self.input = PathEntry(self.body, mode="open", filetypes=PDF_FILETYPES)
        self.input.pack(fill="x")

        self.spacer()
        self.section("2. Current password")
        self.password_entry = LabeledEntry(self.body, "Password", show="*", width=30)
        self.password_entry.pack(anchor="w")

        self.spacer()
        self.section("3. Output file")
        self.output = PathEntry(self.body, mode="save", filetypes=PDF_FILETYPES,
                                 defaultextension=".pdf", initialfile="unlocked.pdf")
        self.output.pack(fill="x")

        self.spacer()
        self.make_run_button("Unlock PDF", self._run).pack(anchor="w")

    def _run(self):
        inp, out = self.input.get(), self.output.get()
        if not inp or not out:
            messagebox.showwarning("Unlock PDF", "Select an input file and an output file.")
            return

        def on_success(_):
            if messagebox.askyesno("Done", "PDF unlocked.\nOpen the output folder?"):
                open_in_explorer(out)

        self.run_task(core.unlock_pdf, (inp, out, self.password_entry.get()),
                      "Unlocking…", on_success, "Done.")


PAGE_CLASSES = {
    "merge": MergePage,
    "split": SplitPage,
    "remove": RemovePagesPage,
    "extract": ExtractPagesPage,
    "rotate": RotatePage,
    "compress": CompressPage,
    "watermark": WatermarkPage,
    "pdf2img": PdfToImagesPage,
    "img2pdf": ImagesToPdfPage,
    "pdf2text": PdfToTextPage,
    "protect": ProtectPage,
    "unlock": UnlockPage,
}


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

class ToolCard(tk.Frame):
    def __init__(self, master, tool, on_click):
        super().__init__(master, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1,
                          bd=0, cursor="hand2")
        self.tool = tool
        self.on_click = on_click

        icon = tk.Label(self, text=tool["icon"], font=(FONT_FAMILY, 26), bg=CARD_BG, fg=RED)
        icon.pack(pady=(18, 6))
        title = tk.Label(self, text=tool["label"], font=(FONT_FAMILY, 12, "bold"), bg=CARD_BG, fg=TEXT_DARK)
        title.pack()
        desc = tk.Label(self, text=tool["desc"], font=(FONT_FAMILY, 9), bg=CARD_BG, fg=TEXT_MUTED,
                         wraplength=190, justify="center")
        desc.pack(pady=(4, 18), padx=12)

        for widget in (self, icon, title, desc):
            widget.bind("<Button-1>", lambda e: self.on_click(self.tool["key"]))
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, _e):
        self.configure(highlightbackground=RED, highlightthickness=2)

    def _on_leave(self, _e):
        self.configure(highlightbackground=BORDER, highlightthickness=1)


class HomePage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Content.TFrame")
        self.app = app

        header = ttk.Frame(self, style="Content.TFrame")
        header.pack(fill="x", padx=28, pady=(24, 10))
        ttk.Label(header, text="Every tool you need to work with PDFs", font=(FONT_FAMILY, 18, "bold"),
                  background=BG, foreground=TEXT_DARK).pack(anchor="w")
        ttk.Label(header, text="100% offline — files never leave your computer.",
                  font=(FONT_FAMILY, 10), background=BG, foreground=TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        canvas_holder = ttk.Frame(self, style="Content.TFrame")
        canvas_holder.pack(fill="both", expand=True, padx=20)

        canvas = tk.Canvas(canvas_holder, bg=BG, highlightthickness=0)
        vscroll = ttk.Scrollbar(canvas_holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas, style="Content.TFrame")
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_inner_configure(_e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(e):
            canvas.itemconfigure(inner_id, width=e.width)

        inner.bind("<Configure>", on_inner_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        for category in CATEGORY_ORDER:
            tools_in_cat = [t for t in TOOLS if t["category"] == category]
            if not tools_in_cat:
                continue
            ttk.Label(inner, text=category, font=(FONT_FAMILY, 12, "bold"), background=BG,
                      foreground=TEXT_DARK).pack(anchor="w", padx=8, pady=(14, 8))
            grid = ttk.Frame(inner, style="Content.TFrame")
            grid.pack(fill="x", padx=8)
            for col in range(4):
                grid.columnconfigure(col, weight=1, uniform="card")
            for i, tool in enumerate(tools_in_cat):
                card = ToolCard(grid, tool, app.show_tool)
                card.grid(row=i // 4, column=i % 4, sticky="nsew", padx=8, pady=8, ipadx=4)


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PaperHeart — Offline PDF Toolkit")
        self.geometry("1180x760")
        self.minsize(960, 620)
        self.configure(bg=BG)

        try:
            self.iconbitmap(resource_path(os.path.join("assets", "paperheart.ico")))
        except Exception:
            pass

        self._setup_styles()
        self._build_layout()
        self.show_home()

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=BG)
        style.configure("Content.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("Sidebar.TFrame", background=SIDEBAR_BG)

        style.configure("TLabel", background=BG, foreground=TEXT_DARK, font=(FONT_FAMILY, 10))
        style.configure("TButton", font=(FONT_FAMILY, 10), padding=6)
        style.configure("Link.TButton", font=(FONT_FAMILY, 10), foreground=RED, padding=0)
        style.map("Link.TButton", foreground=[("active", RED_DARK)])

        style.configure("Sidebar.TButton", font=(FONT_FAMILY, 10), padding=(12, 8),
                         background=SIDEBAR_BG, borderwidth=0, anchor="w")
        style.map("Sidebar.TButton", background=[("active", "#FDEEEE")], foreground=[("active", RED)])

        style.configure("TRadiobutton", background=CARD_BG, font=(FONT_FAMILY, 10))
        style.configure("TEntry", padding=4)
        style.configure("Horizontal.TProgressbar", troughcolor=BORDER, background=RED)

    def _build_layout(self):
        top_bar = tk.Frame(self, bg="white", height=56, highlightbackground=BORDER, highlightthickness=1)
        top_bar.pack(side="top", fill="x")
        top_bar.pack_propagate(False)
        tk.Label(top_bar, text="♥", font=(FONT_FAMILY, 18, "bold"), bg="white", fg=RED).pack(
            side="left", padx=(20, 6))
        tk.Label(top_bar, text="PaperHeart", font=(FONT_FAMILY, 15, "bold"), bg="white", fg=TEXT_DARK).pack(
            side="left")
        tk.Label(top_bar, text="Offline PDF Toolkit", font=(FONT_FAMILY, 10), bg="white",
                  fg=TEXT_MUTED).pack(side="left", padx=(10, 0))

        body = ttk.Frame(self, style="Content.TFrame")
        body.pack(side="top", fill="both", expand=True)

        sidebar = tk.Frame(body, bg=SIDEBAR_BG, width=200, highlightbackground=BORDER, highlightthickness=1)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ttk.Button(sidebar, text="⌂  Home", style="Sidebar.TButton",
                   command=self.show_home).pack(fill="x", padx=8, pady=(14, 6))

        for category in CATEGORY_ORDER:
            tools_in_cat = [t for t in TOOLS if t["category"] == category]
            if not tools_in_cat:
                continue
            tk.Label(sidebar, text=category.upper(), bg=SIDEBAR_BG, fg=TEXT_MUTED,
                     font=(FONT_FAMILY, 8, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
            for tool in tools_in_cat:
                ttk.Button(
                    sidebar, text=f'{tool["icon"]}  {tool["label"]}', style="Sidebar.TButton",
                    command=lambda k=tool["key"]: self.show_tool(k),
                ).pack(fill="x", padx=8)

        self.content = ttk.Frame(body, style="Content.TFrame")
        self.content.pack(side="left", fill="both", expand=True)

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def show_home(self):
        self._clear_content()
        HomePage(self.content, self).pack(fill="both", expand=True)

    def show_tool(self, key: str):
        page_cls = PAGE_CLASSES.get(key)
        if not page_cls:
            messagebox.showinfo("Coming soon", f"'{key}' is not implemented yet.")
            return
        self._clear_content()
        page_cls(self.content, self).pack(fill="both", expand=True)
