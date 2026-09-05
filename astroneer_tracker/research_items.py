from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
from typing import Callable

PLANETS = ("Sylva", "Desolo", "Calidor", "Vesania", "Novus", "Glacio", "Atrox")


class ResearchListWindow:
    """Completely offline Research Item checklist bundled with the tracker."""

    def __init__(
        self,
        parent: tk.Misc,
        tracker_data: dict,
        storage,
        data_dir: Path,
        get_save_name: Callable[[], str | None],
    ):
        self.parent = parent
        self.tracker_data = tracker_data
        self.storage = storage
        self.get_save_name = get_save_name

        # Research metadata and all 93 images ship inside the application.
        self.asset_dir = Path(__file__).resolve().parent / "assets" / "research_items"
        self.items_file = self.asset_dir / "research_items.json"

        self.window: tk.Toplevel | None = None
        self.canvas = None
        self.inner = None
        self.items: list[dict] = []
        self.photos: dict[str, tk.PhotoImage] = {}
        self.filter_var = tk.StringVar(master=parent, value="All")
        self.planet_var = tk.StringVar(master=parent, value="All Planets")
        self.show_var = tk.StringVar(master=parent, value="All")
        self.count_var = tk.StringVar(master=parent, value="")
        self.status_var = tk.StringVar(master=parent, value="Ready")

    def show(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self._render()
            return

        self.window = tk.Toplevel(self.parent)
        self.window.title("Astroneer Research List")
        self.window.configure(bg="#0b0d12")
        self.window.geometry("1400x850")
        self.window.minsize(950, 650)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        outer = tk.Frame(self.window, bg="#0b0d12")
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        top = tk.Frame(outer, bg="#0b0d12")
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="RESEARCH LIST", bg="#0b0d12", fg="#63d7ff",
                 font=("Segoe UI", 17, "bold")).pack(side="left")

        self.save_label = tk.Label(top, text="", bg="#0b0d12", fg="#e8edf4",
                                   font=("Segoe UI", 10, "bold"))
        self.save_label.pack(side="left", padx=(16, 0))

        filters = tk.Frame(outer, bg="#11151d", bd=1, relief="solid")
        filters.pack(fill="x", pady=(0, 8))
        tk.Label(filters, text="Category:", bg="#11151d", fg="#e8edf4").pack(side="left", padx=(8, 4), pady=6)
        cat = ttk.Combobox(filters, textvariable=self.filter_var,
                           values=("All", "Technology", "Mineral", "Organic", "Unknown"),
                           state="readonly", width=13)
        cat.pack(side="left", pady=6)
        cat.bind("<<ComboboxSelected>>", lambda _e: self._render())

        tk.Label(filters, text="Planet:", bg="#11151d", fg="#e8edf4").pack(side="left", padx=(14, 4), pady=6)
        planet = ttk.Combobox(filters, textvariable=self.planet_var,
                              values=("All Planets",) + PLANETS, state="readonly", width=11)
        planet.pack(side="left", pady=6)
        planet.bind("<<ComboboxSelected>>", lambda _e: self._render())

        tk.Label(filters, text="Show:", bg="#11151d", fg="#e8edf4").pack(side="left", padx=(14, 4), pady=6)
        show = ttk.Combobox(filters, textvariable=self.show_var,
                            values=("All", "Found", "Not Found"), state="readonly", width=11)
        show.pack(side="left", pady=6)
        show.bind("<<ComboboxSelected>>", lambda _e: self._render())

        tk.Label(filters, textvariable=self.count_var, bg="#11151d", fg="#7dff91",
                 font=("Segoe UI", 10, "bold")).pack(side="right", padx=10)

        tk.Label(
            outer,
            text="Click a Research Item image to mark it found. Found images are faded; click again to undo. Planet filter includes every possible flora planet.",
            bg="#0b0d12", fg="#aeb8c6", font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(0, 6))

        holder = tk.Frame(outer, bg="#0b0d12")
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg="#0b0d12", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.inner = tk.Frame(self.canvas, bg="#0b0d12")
        self._inner_window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._inner_window_id, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._wheel)

        status = tk.Frame(outer, bg="#0b0d12")
        status.pack(fill="x", pady=(7, 0))
        tk.Label(status, textvariable=self.status_var, bg="#0b0d12", fg="#7f8b9c",
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(status, text="93 Research Items bundled locally • No internet required",
                 bg="#0b0d12", fg="#7f8b9c", font=("Segoe UI", 8)).pack(side="right")

        self._load_bundled_items()

    def _close(self):
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
        self.window = None

    def _wheel(self, event):
        if self.window is None or not self.window.winfo_exists() or self.canvas is None:
            return
        try:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except Exception:
            pass

    def _selected_save(self) -> str | None:
        try:
            return self.get_save_name()
        except Exception:
            return None

    def _found_set(self) -> set[str]:
        name = self._selected_save()
        if not name:
            return set()
        record = self.tracker_data.setdefault("saves", {}).setdefault(name, {})
        found = record.setdefault("research_items_found", [])
        if not isinstance(found, list):
            found = []
            record["research_items_found"] = found
        return set(str(x) for x in found)

    def _save_found(self, found: set[str]):
        name = self._selected_save()
        if not name:
            return
        record = self.tracker_data.setdefault("saves", {}).setdefault(name, {})
        record["research_items_found"] = sorted(found)
        self.storage.save(self.tracker_data)

    def _toggle(self, uid: str):
        if not self._selected_save():
            messagebox.showinfo("Research List", "Select a save in the tracker first.", parent=self.window)
            return
        found = self._found_set()
        if uid in found:
            found.remove(uid)
        else:
            found.add(uid)
        self._save_found(found)
        self._render()

    def _load_bundled_items(self):
        try:
            payload = json.loads(self.items_file.read_text(encoding="utf-8"))
            self.items = list(payload.get("items", []))
        except Exception as exc:
            self.items = []
            self.status_var.set("Bundled Research List data could not be loaded.")
            messagebox.showerror("Research List", f"Could not load bundled Research Items.\n\n{exc}", parent=self.window)
            return

        missing = [
            item.get("image_filename", "")
            for item in self.items
            if not (self.asset_dir / item.get("image_filename", "")).exists()
        ]
        if missing:
            self.status_var.set(f"Loaded {len(self.items)} items; {len(missing)} bundled images are missing.")
        else:
            self.status_var.set(f"Loaded {len(self.items)} Research Items and all images locally.")
        self._render()

    def _image_for(self, item: dict):
        uid = item["uid"]
        if uid in self.photos:
            return self.photos[uid]
        path = self.asset_dir / item.get("image_filename", f"{uid}.png")
        if not path.exists():
            return None
        try:
            image = tk.PhotoImage(file=str(path))
            factor = max(1, (max(image.width(), image.height()) + 95) // 96)
            if factor > 1:
                image = image.subsample(factor, factor)
            self.photos[uid] = image
            return image
        except Exception:
            return None

    def _visible_items(self):
        category = self.filter_var.get()
        planet = self.planet_var.get()
        show = self.show_var.get()
        found = self._found_set()
        out = []
        for item in self.items:
            if category != "All" and item.get("section") != category:
                continue
            if planet != "All Planets" and planet not in set(item.get("planets") or []):
                continue
            is_found = item.get("uid") in found
            if show == "Found" and not is_found:
                continue
            if show == "Not Found" and is_found:
                continue
            out.append(item)
        return out

    def _render(self):
        if self.inner is None or not self.inner.winfo_exists():
            return
        save_name = self._selected_save()
        self.save_label.configure(text=f"Save: {save_name or 'Select a save'}")
        found = self._found_set()
        self.count_var.set(f"{len(found)} / {len(self.items)} found")

        for child in self.inner.winfo_children():
            child.destroy()

        visible = self._visible_items()
        if not visible:
            tk.Label(self.inner, text="No items match the current filter.", bg="#0b0d12", fg="#aeb8c6").pack(anchor="w", padx=10, pady=10)
            return

        columns = 6
        for c in range(columns):
            self.inner.grid_columnconfigure(c, weight=1, uniform="research")

        row = 0
        col = 0
        current_section = None
        for item in visible:
            section = item.get("section", "")
            if section != current_section:
                if col:
                    row += 1
                    col = 0
                current_section = section
                tk.Label(self.inner, text=f"{section} Research Items", bg="#0b0d12", fg="#63d7ff",
                         font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=columns,
                                                             sticky="w", padx=5, pady=(12, 5))
                row += 1

            uid = item["uid"]
            is_found = uid in found
            card = tk.Frame(self.inner, bg="#11151d", bd=1, relief="solid", highlightthickness=1,
                            highlightbackground="#293343")
            card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            card.grid_columnconfigure(0, weight=1)

            image_canvas = tk.Canvas(card, width=108, height=108, bg="#11151d", highlightthickness=0, cursor="hand2")
            image_canvas.grid(row=0, column=0, pady=(6, 2))
            photo = self._image_for(item)
            if photo is not None:
                image_canvas.create_image(54, 54, image=photo, anchor="center")
            else:
                image_canvas.create_text(54, 54, text="Image\nmissing", fill="#d56b6b",
                                         font=("Segoe UI", 8), justify="center")
            if is_found:
                image_canvas.create_rectangle(0, 0, 108, 108, fill="#0b0d12", outline="", stipple="gray50")
            image_canvas.bind("<Button-1>", lambda _e, value=uid: self._toggle(value))

            tk.Label(card, text="FOUND" if is_found else "NOT FOUND", bg="#11151d",
                     fg="#7f8b9c" if is_found else "#e8edf4",
                     font=("Segoe UI", 8, "bold")).grid(row=1, column=0, pady=(0, 4))
            tk.Label(card,
                     text=f"{item.get('column2_name', 'Column 2')}: {item.get('column2_value', '')}",
                     bg="#11151d", fg="#e8edf4", font=("Segoe UI", 8), wraplength=180,
                     justify="center").grid(row=2, column=0, sticky="ew", padx=5)
            tk.Label(card,
                     text=f"{item.get('column3_name', 'Column 3')}: {item.get('column3_value', '')}",
                     bg="#11151d", fg="#aeb8c6", font=("Segoe UI", 8), wraplength=180,
                     justify="center").grid(row=3, column=0, sticky="ew", padx=5, pady=(2, 7))

            col += 1
            if col >= columns:
                col = 0
                row += 1
