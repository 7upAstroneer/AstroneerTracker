from __future__ import annotations

from datetime import datetime
import tkinter as tk
import time
import math
import re
import hashlib
import zlib
import copy
from pathlib import Path
from tkinter import ttk, messagebox

from .config import APP_NAME, VERSION, default_save_directory, tracker_data_file
from .saves import SaveInfo, find_savegames
from .session import ActiveSaveDetector
from .processes import is_astroneer_running
from .diagnostics import DiagnosticsArchive
from .player_actor_probe import parse_player_actor_candidates
from .planet_classifier import classify_planet
from .storage import TrackerStorage
from .location_state import LocationStateTracker
from .ps_timing import PowerShellTimingModel
from .death_tracker import DeathTracker
from .gateway_core_probe import probe_core_activation
from .galastropod_probe import probe_galastropods, GALASTROPOD_NAME_BY_PLANET
from .live_death_monitor import LiveDeathMonitor
from .offplanet_probe import probe_position
from .special_location_detector import inspect_special_location
from .gateway_probe import get_gateway_activation_total
from .gateway_planet_probe import probe_gateways_by_planet
from .rename_fingerprint import get_rename_fingerprint
from .research_items import ResearchListWindow
from .orbital_platform_probe import probe_orbital_platforms
from .megatech_actor_probe import probe_megatech_actors


PLANETS = ["Sylva", "Desolo", "Calidor", "Vesania", "Novus", "Glacio", "Atrox"]
TRACKED_LOCATIONS = PLANETS + [
    "Orbital Platform",
    "Unidentified Satellite",
    "Sun Room",
]
PLANET_DAY_SECONDS = {"Sylva":720,"Desolo":115,"Calidor":810,"Vesania":810,"Novus":210,"Glacio":1200,"Atrox":1200}


GATEWAY_MAX_BY_PLANET = {
    "Sylva": 6,
    "Desolo": 2,
    "Calidor": 6,
    "Vesania": 6,
    "Novus": 2,
    "Glacio": 6,
    "Atrox": 6,
}


# v0.51 planet-information panel scaffolding.
# These are intentionally easy-to-edit placeholders. Icons and wording will
# be refined later without changing the panel layout.
PLANET_DETAIL_CARDS = {
    # Order:
    # Key Resources, Gateway, Core, Terrarium, Galastropod, EXO Aide, Circuit(s)
    #
    # Tuple layout:
    # (card key, main value, optional secondary value)

    "Sylva": [
        ("Key Resources", "Hydrogen; Nitrogen; Sphalerite", ""),
        ("Gateway", "5 U/s", ""),
        ("Core", "Quartz", ""),
        ("Terrarium", "Soil; Zinc; Bouncevine", ""),
        ("Galastropods", "Provides Light", "Mutant Hissbine"),
        ("EXO Aids (3 U/s)", "Srf/Cv: Laterite\nMntl: Glass\nCore: Nitrogen", ""),
        ("Circuit(s)", "B", ""),
    ],

    "Desolo": [
        ("Key Resources", "Wolframite; Sphalerite", ""),
        ("Gateway", "8 U/s", ""),
        ("Core", "Zinc", ""),
        ("Terrarium", "Soil; Tungsten; Daggeroot", ""),
        ("Galastropods", "Enhanced Compass", "Mutant Hissbine"),
        ("EXO Aids (4 U/s)", "Srf/Cv: Sphalerite\nMntl: Ceramic\nCore: Alu Alloy", ""),
        ("Circuit(s)", "", ""),
    ],

    "Vesania": [
        ("Key Resources", "Lithium; Titanite; Argon; Nitrogen", ""),
        ("Gateway", "16 U/s", ""),
        ("Core", "Graphene", ""),
        ("Terrarium", "Soil; Lithium; Lashleaf", ""),
        ("Galastropods", "Damage Immunity", "Cataplant"),
        ("EXO Aids (5 U/s)", "Srf/Cv: Graphite\nMntl: Hydrogen\nCore: Silicone", ""),
        ("Circuit(s)", "A / B / C", ""),
    ],

    "Novus": [
        ("Key Resources", "Hematite; Lithium; Methane", ""),
        ("Gateway", "21 U/s", ""),
        ("Core", "Silicon", ""),
        ("Terrarium", "Soil; Iron; Thistlewhip", ""),
        ("Galastropods", "Provides Power", "Cataplant"),
        ("EXO Aids (5 U/s)", "Srf/Cv: Lithium\nMntl: Methane\nCore: Steel", ""),
        ("Circuit(s)", "B", ""),
    ],

    "Calidor": [
        ("Key Resources", "Wolframite; Malachite; Sulfer", ""),
        ("Gateway", "12 U/s", ""),
        ("Core", "Explosive Powder", ""),
        ("Terrarium", "Soil; Copper; Wheezeweed", ""),
        ("Galastropods", "Provides Oxygen", "Attactus"),
        ("EXO Aids (4 U/s)", "Srf/Cv: Tungsten\nMntl: Plastic\nCore: Sulfur", ""),
        ("Circuit(s)", "A / B", ""),
    ],

    "Glacio": [
        ("Key Resources", "Titanite; Hematite; Argon", ""),
        ("Gateway", "26 U/s", ""),
        ("Core", "Diamonds", ""),
        ("Terrarium", "Soil; Argon; Popcoral", ""),
        ("Galastropods", "Enhanced Tool", "Boomalloon"),
        ("EXO Aids (6 U/s)", "Srf/Cv: Ammonium\nMntl: Argon\nCore: Diamonds", ""),
        ("Circuit(s)", "A", ""),
    ],

    "Atrox": [
        ("Key Resources", "Helium; Sulfur; Methane; Nitrogen", ""),
        ("Gateway", "30 U/s", ""),
        ("Core", "Hydrogen", ""),
        ("Terrarium", "Soil; Helium; Spinelily", ""),
        ("Galastropods", "Enhanced Mobility", "Spewflower"),
        ("EXO Aids (6 U/s)", "Srf/Cv: Helium\nMntl: Graphene\nCore: Nanocarbon Alloy", ""),
        ("Circuit(s)", "A / B / D", ""),
    ],
}


MEGATECH_INFO = {
    "DLS": (
        "Distribution Launch System (DLS)\n"
        "49 Compound; 29 Zinc; 23 Copper; 7 Steel"
    ),
    "Intermodal Platform": (
        "Intermodal Platform\n"
        "50 Resin; 20 Aluminum; 10 Ceramic; 5 Steel; 2 Titanium Alloy"
    ),
    "Biodome": (
        "Biodome\n"
        "Stage 1: 100 Resin; 150 Organic; 30 Steel; 40 Glass; 40 Ammonium\n"
        "Stage 2: 100 Resin; 20 Graphene; 20 Aluminum Alloy; 75 Glass; 80 Nitrogen\n"
        "Stage 3: 150 Resin; 20 Rubber; 20 Plastic; 50 Glass"
    ),
    "Museum": (
        "Museum\n"
        "Stage 1: 200 Compound; 30 Copper; 30 Glass; 15 Silicone; 10 Titanium Alloy\n"
        "Stage 2: 50 Compound; 30 Silicone; 30 Rubber; 20 Aluminum; 5 EXO Chip"
    ),
    "Orbital Platform": (
        "Orbital Platform\n"
        "Stage 1: 250 Resin; 50 Aluminum Alloy; 50 Titanium; 20 Steel; 10 Silicone\n"
        "Stage 2: 150 Compound; 50 Aluminum; 50 Copper; 10 Titanium Alloy; 5 EXO Chip\n"
        "Stage 3: 200 Compound; 75 Steel; 30 Astronium; 20 Nanocarbon Alloy; 2 EXO Chip"
    ),
}
MEGATECH_ROWS = (
    "DLS",
    "Intermodal Platform",
    "Biodome",
    "Museum",
    "Orbital Platform",
)


MAT_INFO = {
    "Desolo": (
        "Desolo M.A.T.\n"
        "1 EXO Chip (1st Signal); 2 Copper; 2 Zinc; "
        "2 Plastic; 2 Aluminum Alloy"
    ),
    "Vesania": (
        "Vesania M.A.T.\n"
        "1 EXO Chip (1st Signal); 2 Hydrogen; 2 Nitrogen; "
        "2 Silicon; 2 Tungsten Carbide; 2 Graphite; "
        "2 Titanium; 2 Tungsten; 3 EXO Chips"
    ),
}


class TrackerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} (v{VERSION})")
        self.root.minsize(900, 600)

        self.save_directory: Path = default_save_directory()
        self.detector = ActiveSaveDetector()
        self.diagnostics = DiagnosticsArchive(tracker_data_file().parent)

        self.storage = TrackerStorage(tracker_data_file())
        self.data = self.storage.load()
        self.location_state = LocationStateTracker(self.data)

        trace_dir = tracker_data_file().parent / "Diagnostics" / "Timer Traces"
        trace_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._timer_trace_path = trace_dir / f"TimerTrace_{trace_stamp}.log"
        self.timing = PowerShellTimingModel(
            self.data,
            trace_path=self._timer_trace_path,
        )

        gateway_trace_dir = tracker_data_file().parent / "Diagnostics" / "Gateway Core Traces"
        gateway_trace_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._gateway_core_trace_path = (
            gateway_trace_dir / f"GatewayCoreTrace_{gateway_trace_stamp}.log"
        )

        death_trace_dir = tracker_data_file().parent / "Diagnostics" / "Death Traces"
        death_trace_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._death_trace_path = death_trace_dir / f"DeathTrace_{death_trace_stamp}.log"
        self.deaths = DeathTracker(
            self.data,
            trace_path=self._death_trace_path,
        )
        self.live_death_monitor = LiveDeathMonitor(trace_path=self._death_trace_path)
        self._last_live_death_status = "not attached"
        self._last_live_death_counted_line = None
        self._last_respawn_snapshot_change_count = 0
        self._last_respawn_snapshot_all_changed = False
        self._last_respawn_snapshot_changed_fields = []
        self._last_death_detected = False
        self._last_backpack_signature = None
        self._last_corpse_count = None
        self._last_death_probe_status = "not probed yet"
        self._last_backpack_rail_ids = []
        self._last_new_backpack_rail_ids = []
        self._last_removed_backpack_rail_ids = []
        self._last_new_death_tokens = []
        self._last_removed_death_tokens = []
        self._last_nearest_planet = None
        self._last_nearest_distance = None
        self._last_orbital_refs = None
        self._last_landing_markers = None
        self._last_satellite_baseline = None
        self._last_sun_room_mesh = None
        self._last_captured_diagnostic = "No save diagnostic captured yet."
        self._last_gateway_total = None
        self._last_gateway_previous = None
        self._last_gateway_delta = None
        self._last_visit_previous = None
        self._last_visit_before = None
        self._last_visit_after = None
        self._last_visit_changed = None
        self._last_player_candidate_lines = []

        self._detector_primed = False
        self._game_was_running = False
        self._last_change_seen = None
        self._pending_logical_name: str | None = None
        self._last_detected_location: str | None = None
        self._last_xyz = None
        self._selected_view_save: str | None = None
        self._selected_location_row: str | None = None
        self._last_rendered_detail_target: str | None = None
        self._physical_save_map: dict[str, SaveInfo] = {}
        self._gateway_symbol_images: dict[str, tk.PhotoImage] = {}
        self._planet_sky_images: dict[str, tk.PhotoImage] = {}
        self._shell_images: dict[str, tk.PhotoImage] = {}
        self._galastropod_images: dict[str, tk.PhotoImage] = {}
        self._gateway_chamber_image: tk.PhotoImage | None = None
        self._exo_aid_image: tk.PhotoImage | None = None
        self._circuit_image: tk.PhotoImage | None = None
        self._core_hover_window: tk.Toplevel | None = None
        self._core_hover_image: tk.PhotoImage | None = None
        self._core_hover_planet: str | None = None
        self._feature_overlay_frame: tk.Frame | None = None
        self._feature_overlay_text: tk.Text | None = None
        self._megatech_count_labels: dict[str, tk.Label] = {}
        self._megatech_name_labels: dict[str, tk.Label] = {}
        self._megatech_tooltip: tk.Toplevel | None = None
        self._mat_tooltip: tk.Toplevel | None = None
        self._desolo_mat_complete_for_render = False
        self._vesania_mat_complete_for_render = False
        self._last_auto_selected_live_save: str | None = None
        self._xeno_lab_present_for_render = False
        self._previous_physical_saves: dict[str, SaveInfo] = {}
        self._last_tick = time.monotonic()
        self._last_save_flush = self._last_tick
        self._startup_timer_armed = False
        self._research_list_window = None

        self._build_ui()
        self._previous_physical_saves = {
            s.display_name: s for s in find_savegames(self.save_directory)
        }
        self.root.protocol("WM_DELETE_WINDOW", self._on_tracker_exit)
        self._refresh()
        self.root.after(300, self._set_initial_window_geometry)

    def _on_tracker_exit(self) -> None:
        """
        Death trace is session-only by request. Delete it when the tracker exits.
        Timer trace behavior is unchanged.
        """
        try:
            self._hide_core_hover_preview()
        except Exception:
            pass

        try:
            self.live_death_monitor.reset_session()
        except Exception:
            pass
        try:
            if self._death_trace_path.exists():
                self._death_trace_path.unlink()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

    def _build_ui(self) -> None:
        # v0.63: compact gameplay summary from the approved dark/neon mockup while
        # leaving the v0.60 tracking, parsing, timing and storage logic intact.
        self.root.configure(bg="#0b0d12")
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Dark.TFrame", background="#0b0d12")
        style.configure("Panel.TFrame", background="#11151d")
        style.configure("Dark.TLabelframe", background="#11151d", foreground="#63d7ff", bordercolor="#293343")
        style.configure("Dark.TLabelframe.Label", background="#0b0d12", foreground="#63d7ff", font=("Segoe UI", 10, "bold"))
        style.configure("Dark.TLabel", background="#0b0d12", foreground="#e8edf4")

        outer = ttk.Frame(self.root, padding=(8, 6), style="Dark.TFrame")
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="Dark.TFrame")
        header.pack(fill="x", pady=(0, 3))

        tk.Label(
            header,
            text=f"{APP_NAME} (v{VERSION})",
            bg="#0b0d12",
            fg="#f4f7fb",
            font=("Segoe UI", 17, "bold"),
        ).pack(side="left")

        self.playing_label = tk.Label(
            header,
            text="Astroneer not running",
            bg="#0b0d12",
            fg="#ff5364",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        self.playing_label.pack(side="left", padx=(14, 0))

        # v0.98: Move the existing PLAY NOW control left so its center lines
        # up approximately over the Novus planet column (5th of 7).  Research
        # List sits immediately to its right; the remainder of the header is
        # intentionally left open for future controls.
        self.play_now_button = tk.Button(
            header,
            text="PLAY NOW",
            command=self._play_now,
            bg="#1d9b5f",
            fg="white",
            activebackground="#16804d",
            activeforeground="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=14,
            pady=4,
            width=13,
        )
        self.play_now_button.place(relx=(4.5 / 7.0), rely=0.5, anchor="center")

        self.research_list_button = tk.Button(
            header,
            text="Research List",
            command=self._open_research_list,
            bg="#5d3f91",
            fg="white",
            activebackground="#7354aa",
            activeforeground="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=14,
            pady=4,
            width=13,
        )
        self.research_list_button.place(relx=(5.55 / 7.0), rely=0.5, anchor="center")

        # Hidden compatibility widgets used by the unchanged v0.60 logic.
        self.timing_text = tk.Text(self.root)
        self.capture_text = tk.Text(self.root)
        self.save_info_label = ttk.Label(self.root)

        # Compact planet dashboard; no extra title row/frame text.
        self.location_detail_frame = ttk.Frame(outer, style="Dark.TFrame")
        self.location_detail_frame.pack(fill="x", anchor="n", pady=(0, 3))
        self.location_detail_header = ttk.Label(self.root)  # compatibility only
        self.location_cards_frame = ttk.Frame(self.location_detail_frame, style="Panel.TFrame")
        self.location_cards_frame.pack(fill="x")

        # Main lower dashboard: gameplay totals left, save browser right.
        body = ttk.Frame(outer, style="Dark.TFrame")
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, style="Dark.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = ttk.LabelFrame(body, text="Select Save to View", padding=8, width=320, style="Dark.TLabelframe")
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        table_frame = ttk.LabelFrame(left, text="Gameplay Totals — Persistent Save Record (updated upon each game save; recommend save as soon as possible after each load/start.)", padding=8, style="Dark.TLabelframe")
        table_frame.pack(fill="both", expand=True, anchor="n")
        table_text_frame = ttk.Frame(table_frame, style="Panel.TFrame")
        table_text_frame.pack(fill="both", expand=True)
        self.table_text = tk.Text(table_text_frame, height=16, wrap="none", font=("Consolas", 10), cursor="hand2",
                                  bg="#0d1118", fg="#e6edf5", insertbackground="white", relief="flat",
                                  selectbackground="#263a54", selectforeground="white")
        self.table_text.grid(row=0, column=0, sticky="nsew")
        self.table_text.bind("<Button-1>", self._on_gameplay_table_click)
        self.table_text.bind("<Motion>", self._on_gameplay_table_motion)
        self.table_text.bind("<Leave>", self._hide_mat_info)

        self._feature_overlay_frame = tk.Frame(
            table_text_frame,
            bg="#111720",
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#586575",
        )

        tk.Label(
            self._feature_overlay_frame,
            text="MegaTech",
            bg="#111720",
            fg="#5fd7ff",
            font=("Segoe UI", 10, "bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=6,
            sticky="w",
            padx=8,
            pady=(4, 3),
        )

        # v0.90: two-column MegaTech layout to keep all five rows visible
        # at the normal startup window size.
        mega_positions = {
            "DLS": (1, 0),
            "Intermodal Platform": (2, 0),
            "Biodome": (3, 0),
            "Museum": (1, 3),
            "Orbital Platform": (2, 3),
        }

        for mega_name in MEGATECH_ROWS:
            row_index, base_col = mega_positions[mega_name]

            name_label = tk.Label(
                self._feature_overlay_frame,
                text=mega_name,
                bg="#111720",
                fg="#e6edf5",
                font=("Segoe UI", 9),
                anchor="w",
            )
            name_label.grid(
                row=row_index,
                column=base_col,
                sticky="w",
                padx=(8, 4),
                pady=1,
            )
            self._megatech_name_labels[mega_name] = name_label

            count_label = tk.Label(
                self._feature_overlay_frame,
                text="0",
                bg="#111720",
                fg="#e6edf5",
                font=("Consolas", 9, "bold"),
                width=3,
                anchor="e",
            )
            count_label.grid(
                row=row_index,
                column=base_col + 1,
                sticky="e",
                padx=(2, 4),
                pady=1,
            )
            self._megatech_count_labels[mega_name] = count_label

            info_label = tk.Label(
                self._feature_overlay_frame,
                text="i",
                bg="#263a54",
                fg="#ffffff",
                font=("Segoe UI", 8, "bold"),
                width=2,
                cursor="hand2",
                relief="groove",
                bd=1,
            )
            info_label.grid(
                row=row_index,
                column=base_col + 2,
                sticky="e",
                padx=(2, 8),
                pady=1,
            )
            info_label.bind(
                "<Enter>",
                lambda event, name=mega_name:
                    self._show_megatech_info(event, name),
            )
            info_label.bind("<Leave>", self._hide_megatech_info)

        self._feature_overlay_frame.columnconfigure(0, weight=1)
        self._feature_overlay_frame.columnconfigure(3, weight=1)
        self._feature_overlay_frame.place_forget()

        # v0.63: the summary is compact enough to display without scrollbars.
        table_text_frame.columnconfigure(0, weight=1)
        table_text_frame.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(right, style="Panel.TFrame")
        list_frame.pack(fill="both", expand=True)
        self.save_listbox = tk.Listbox(
            list_frame,
            exportselection=False,
            height=8,
            font=("Segoe UI", 10),
            bg="#0d1118", fg="#e8edf4", selectbackground="#245b86",
                                       selectforeground="white", relief="flat", highlightthickness=1,
                                       highlightbackground="#293343")
        self.save_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.save_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.save_listbox.configure(yscrollcommand=scrollbar.set)
        self.save_listbox.bind("<<ListboxSelect>>", self._on_view_save_selected)

        button_grid = ttk.Frame(right, style="Panel.TFrame")
        button_grid.pack(fill="x", pady=(8, 0))
        button_grid.columnconfigure(0, weight=1); button_grid.columnconfigure(1, weight=1)
        def dash_button(parent, text, command, bg="#202936", fg="#e8edf4"):
            return tk.Button(
                parent,
                text=text,
                command=command,
                bg=bg,
                fg=fg,
                activebackground="#303c4d",
                activeforeground="white",
                font=("Segoe UI", 8, "bold"),
                relief="flat",
                padx=6,
                pady=4,
            )
        # v0.95: Open Diagnostics removed. Move the frequently used tracker
        # maintenance controls upward and reserve the new slot for manual
        # correction of persistent tracker data.
        dash_button(button_grid, "Refresh Saves", self._sync_and_refresh_saves, "#d8a928", "#111111").grid(row=0,column=0,sticky="ew",padx=(0,3),pady=(0,5))
        dash_button(button_grid, "Open Last 10 Saves", self._open_last_10_saves).grid(row=0,column=1,sticky="ew",padx=(3,0),pady=(0,5))
        dash_button(button_grid, "Copy Stored Data", self._open_copy_stored_data_dialog).grid(row=1,column=0,sticky="ew",padx=(0,3),pady=(0,5))
        dash_button(button_grid, "Astroneer's Saves", self._open_save_folder).grid(row=1,column=1,sticky="ew",padx=(3,0),pady=(0,5))
        dash_button(button_grid, "Manual Data Input", self._open_manual_data_input).grid(row=2,column=0,sticky="ew",padx=(0,3))
        dash_button(button_grid, "Clear ALL Data", self._clear_all_data, "#a92d3b", "white").grid(row=2,column=1,sticky="ew",padx=(3,0))

        tk.Label(outer, text="This is not for sale or distribution.", bg="#0b0d12", fg="#758194",
                 font=("Segoe UI", 8)).pack(anchor="center", pady=(6, 0))
        self._refresh_save_list()
        self._update_selected_location_details(force=True)

    def _show_megatech_info(self, event, mega_name: str) -> None:
        self._hide_megatech_info()
        tip = tk.Toplevel(self.root)
        self._megatech_tooltip = tip
        tip.wm_overrideredirect(True)
        try:
            tip.wm_attributes("-topmost", True)
        except Exception:
            pass

        tk.Label(
            tip,
            text=MEGATECH_INFO.get(mega_name, mega_name),
            justify="left",
            anchor="w",
            bg="#fffbe8",
            fg="#111111",
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=6,
            wraplength=430,
        ).pack()

        x = event.widget.winfo_rootx() + event.widget.winfo_width() + 8
        y = event.widget.winfo_rooty() - 8
        tip.wm_geometry(f"+{x}+{y}")

    def _hide_megatech_info(self, event=None) -> None:
        tip = self._megatech_tooltip
        self._megatech_tooltip = None
        if tip is not None:
            try:
                tip.destroy()
            except Exception:
                pass

    def _update_feature_overlay(
        self,
        view_name: str | None,
        visits: dict,
        gateway_progress: dict,
        core_progress: dict,
        galastropod_progress: dict,
        total_deaths: int,
        unidentified_satellite_state: str,
        sun_room_state: str,
    ) -> None:
        frame = self._feature_overlay_frame
        if frame is None:
            return
        if not view_name:
            frame.place_forget()
            return

        saves_map = self.data.get("saves", {})
        selected_entry = (
            saves_map.get(view_name, {})
            if isinstance(saves_map, dict)
            else {}
        )
        counts = (
            selected_entry.get("megatech_counts", {})
            if isinstance(selected_entry, dict)
            else {}
        )
        if not isinstance(counts, dict):
            counts = {}

        for name in MEGATECH_ROWS:
            try:
                value = max(0, int(counts.get(name, 0)))
            except Exception:
                value = 0
            label = self._megatech_count_labels.get(name)
            if label is not None:
                label.configure(
                    text=str(value),
                    fg="#00c853" if value >= 1 else "#e6edf5",
                )

            name_label = self._megatech_name_labels.get(name)
            if name_label is not None:
                display_name = name

                try:
                    selected = self.data.get("saves", {}).get(view_name, {})
                except Exception:
                    selected = {}

                highest_stage = 0
                if isinstance(selected, dict):
                    stage_key = None
                    if name == "Biodome":
                        stage_key = "biodome_stage_by_actor"
                    elif name == "Museum":
                        stage_key = "museum_stage_by_actor"
                    elif name == "Orbital Platform":
                        stage_key = "orbital_platform_stage_by_actor"

                    if stage_key:
                        stage_map = selected.get(stage_key, {})
                        if isinstance(stage_map, dict):
                            try:
                                highest_stage = max(
                                    [int(v) for v in stage_map.values()] or [0]
                                )
                            except Exception:
                                highest_stage = 0

                if value > 0 and highest_stage > 0:
                    display_name = f"{name} (S{highest_stage})"

                if isinstance(selected, dict) and value > 0:
                    if name == "DLS":
                        dls_locations = selected.get("dls_locations", [])
                        if isinstance(dls_locations, list) and dls_locations:
                            display_name = (
                                "DLS - "
                                + ", ".join(str(x) for x in dls_locations)
                            )

                    elif name == "Biodome":
                        biodome_locations = selected.get(
                            "biodome_locations", []
                        )
                        if value > 1:
                            display_name = display_name + " - Multiple"
                        elif (
                            isinstance(biodome_locations, list)
                            and biodome_locations
                        ):
                            display_name = (
                                display_name + " - "
                                + str(biodome_locations[0])
                            )

                    elif name == "Museum":
                        museum_locations = selected.get(
                            "museum_locations", []
                        )
                        if (
                            isinstance(museum_locations, list)
                            and museum_locations
                        ):
                            display_name = (
                                display_name
                                + " - "
                                + ", ".join(
                                    str(x) for x in museum_locations
                                )
                            )

                    elif name == "Orbital Platform":
                        op_locations = selected.get(
                            "orbital_platform_orbiting_planets", []
                        )
                        if isinstance(op_locations, list) and op_locations:
                            display_name = (
                                display_name + " - "
                                + ", ".join(str(x) for x in op_locations)
                            )

                name_label.configure(
                    text=display_name,
                    fg="#00c853" if value >= 1 else "#e6edf5",
                )

        # v1.14: add bottom clearance without moving the MegaTech top edge.
        # Old: bottom .985 - height .34 = top .645
        # New: bottom .995 - height .35 = top .645
        frame.place(
            relx=0.985,
            rely=0.995,
            anchor="se",
            relwidth=0.62,
            relheight=0.35,
        )


    def _render_gameplay_table(self, lines: list[str]) -> None:
        """
        Render gameplay totals with selective status colors.

        Deaths:
        - 0 normal
        - >0 red

        Gateway:
        - 0/x entire fraction red
        - partial: unlocked count only green
        - complete x/x entire fraction green

        Core:
        - Locked red
        - Active green
        """
        widget = self.table_text
        widget.configure(state="normal")
        widget.delete("1.0", "end")

        # Fit the widget to the data instead of consuming unused vertical space.
        widget.configure(height=max(1, len(lines)))

        widget.tag_configure("status_green", foreground="#008000")
        widget.tag_configure("status_red", foreground="#c00000")
        widget.tag_configure("location_selected", background="#263a54")

        for line in lines:
            line_start = widget.index("end-1c")
            widget.insert("end", line + "\n")
            line_end = widget.index("end-1c")

            location_name = next(
                (
                    loc for loc in TRACKED_LOCATIONS
                    if line.startswith(loc)
                ),
                None,
            )
            if location_name:
                tag_name = "location_row_" + re.sub(
                    r"[^A-Za-z0-9]+", "_", location_name
                )
                widget.tag_add(tag_name, line_start, line_end)
                if self._selected_location_row == location_name:
                    widget.tag_add("location_selected", line_start, line_end)

            # Planet data rows begin with one of the tracked planet names.
            planet_match = re.match(
                r"^(Sylva|Desolo|Calidor|Vesania|Novus|Glacio|Atrox)\s+",
                line,
            )

            if line.startswith("Desolo"):
                mat_pos = line.find("M.A.T.")
                if mat_pos >= 0:
                    widget.tag_add(
                        "status_green"
                        if self._desolo_mat_complete_for_render
                        else "status_red",
                        f"{line_start}+{mat_pos}c",
                        f"{line_start}+{mat_pos + len('M.A.T.')}c",
                    )
            elif line.startswith("Vesania"):
                mat_pos = line.find("M.A.T.")
                if mat_pos >= 0:
                    widget.tag_add(
                        "status_green"
                        if self._vesania_mat_complete_for_render
                        else "status_red",
                        f"{line_start}+{mat_pos}c",
                        f"{line_start}+{mat_pos + len('M.A.T.')}c",
                    )

            # Core Active / Success / Locked
            for green_word in ("Active", "Success", "Unlocked"):
                pos = 0
                while True:
                    found = line.find(green_word, pos)
                    if found < 0:
                        break
                    widget.tag_add(
                        "status_green",
                        f"{line_start}+{found}c",
                        f"{line_start}+{found + len(green_word)}c",
                    )
                    pos = found + len(green_word)

            pos = 0
            while True:
                found = line.find("Locked", pos)
                if found < 0:
                    break
                widget.tag_add(
                    "status_red",
                    f"{line_start}+{found}c",
                    f"{line_start}+{found + len('Locked')}c",
                )
                pos = found + len("Locked")

            # Gateway fraction.
            match = re.search(r"\b(\d+)/(\d+)\b", line)
            if match:
                unlocked = int(match.group(1))
                maximum = int(match.group(2))

                if unlocked == 0:
                    widget.tag_add(
                        "status_red",
                        f"{line_start}+{match.start()}c",
                        f"{line_start}+{match.end()}c",
                    )
                elif unlocked >= maximum:
                    widget.tag_add(
                        "status_green",
                        f"{line_start}+{match.start()}c",
                        f"{line_start}+{match.end()}c",
                    )
                else:
                    widget.tag_add(
                        "status_green",
                        f"{line_start}+{match.start(1)}c",
                        f"{line_start}+{match.end(1)}c",
                    )

            # Deaths column: parse using the fixed planet-row formatting.
            if planet_match:
                # Columns are whitespace-separated and stable:
                # Location Visits Time PlanetDays Deaths Gateway Core Galastropod
                parts = line.split()
                if len(parts) >= 6:
                    # Deaths is the fifth logical field after location,
                    # but Time/PlanetDays are single tokens as well.
                    # Example:
                    # Sylva 2 00:01:00 0.08 3 6/6 Active Sylvie
                    try:
                        death_value = int(parts[4])
                    except Exception:
                        death_value = 0

                    if death_value > 0:
                        # Find the exact deaths token occurrence after the planet-day token.
                        # Safer than coloring any identical number elsewhere.
                        search_pos = 0
                        token_occurrences = []
                        token = str(death_value)
                        while True:
                            idx = line.find(token, search_pos)
                            if idx < 0:
                                break
                            token_occurrences.append(idx)
                            search_pos = idx + len(token)

                        # In the formatted row, deaths is the last numeric token before gateway.
                        if token_occurrences:
                            death_pos = token_occurrences[-1]
                            gateway_pos = match.start() if match else len(line)
                            candidates = [
                                x for x in token_occurrences if x < gateway_pos
                            ]
                            if candidates:
                                death_pos = candidates[-1]

                            widget.tag_add(
                                "status_red",
                                f"{line_start}+{death_pos}c",
                                f"{line_start}+{death_pos + len(token)}c",
                            )

        try:
            widget.tag_raise("status_red")
            widget.tag_raise("status_green")
        except Exception:
            pass

        # v0.85 Feature coloring: Sylva Xeno Lab.
        # The label is always present; red means the lab wreck signature has
        # not been found in the selected save, green means it has.
        try:
            sylva_line = None
            line_count = int(widget.index("end-1c").split(".", 1)[0])
            for line_no in range(1, line_count + 1):
                text = widget.get(f"{line_no}.0", f"{line_no}.end")
                if text.startswith("Sylva"):
                    sylva_line = line_no
                    break

            if sylva_line is not None:
                text = widget.get(f"{sylva_line}.0", f"{sylva_line}.end")
                pos = text.rfind("Xeno Lab")
                if pos >= 0:
                    tag = (
                        "status_green"
                        if bool(self._xeno_lab_present_for_render)
                        else "status_red"
                    )
                    widget.tag_add(
                        tag,
                        f"{sylva_line}.0+{pos}c",
                        f"{sylva_line}.0+{pos + len('Xeno Lab')}c",
                    )
        except Exception:
            pass

        widget.configure(state="disabled")

    def _show_mat_info(self, event, planet: str) -> None:
        self._hide_mat_info()
        text = MAT_INFO.get(planet)
        if not text:
            return

        tip = tk.Toplevel(self.root)
        self._mat_tooltip = tip
        tip.wm_overrideredirect(True)
        try:
            tip.wm_attributes("-topmost", True)
        except Exception:
            pass

        tk.Label(
            tip,
            text=text,
            justify="left",
            anchor="w",
            bg="#fffbe8",
            fg="#111111",
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=6,
            wraplength=430,
        ).pack()

        x = event.widget.winfo_rootx() + event.x + 12
        y = event.widget.winfo_rooty() + event.y + 12
        tip.wm_geometry(f"+{x}+{y}")

    def _hide_mat_info(self, event=None) -> None:
        tip = self._mat_tooltip
        self._mat_tooltip = None
        if tip is not None:
            try:
                tip.destroy()
            except Exception:
                pass

    def _on_gameplay_table_motion(self, event) -> None:
        try:
            index = self.table_text.index(f"@{event.x},{event.y}")
            line_no = int(index.split(".", 1)[0])
            col_no = int(index.split(".", 1)[1])
            line = self.table_text.get(
                f"{line_no}.0",
                f"{line_no}.end",
            )
        except Exception:
            self._hide_mat_info()
            return

        planet = None
        if line.startswith("Desolo"):
            planet = "Desolo"
        elif line.startswith("Vesania"):
            planet = "Vesania"

        if planet is None:
            self._hide_mat_info()
            return

        info_pos = line.rfind("ⓘ")
        if info_pos >= 0 and abs(col_no - info_pos) <= 1:
            if self._mat_tooltip is None:
                self._show_mat_info(event, planet)
        else:
            self._hide_mat_info()

    def _on_gameplay_table_click(self, event=None) -> None:
        if event is None:
            return

        try:
            index = self.table_text.index(f"@{event.x},{event.y}")
            line_no = int(index.split(".", 1)[0])
            line = self.table_text.get(f"{line_no}.0", f"{line_no}.end")
        except Exception:
            return

        selected = next(
            (
                loc for loc in TRACKED_LOCATIONS
                if line.startswith(loc)
            ),
            None,
        )
        if selected is None:
            return

        self._selected_location_row = selected
        self._update_selected_location_details(force=True)
        self._update_ui(
            self._game_was_running,
            self.detector.state.active_save if self._detector_primed else None,
        )

    def _detail_location_target(self) -> str | None:
        """
        The planet identified from the current save always wins.

        Manual planet selection is only used as a fallback when there is no
        currently detected planet.
        """
        if self._last_detected_location in PLANETS:
            return self._last_detected_location

        if self._selected_location_row in PLANETS:
            return self._selected_location_row

        return None

    def _hide_core_hover_preview(self, event=None) -> None:
        popup = self._core_hover_window
        self._core_hover_window = None
        self._core_hover_image = None
        self._core_hover_planet = None
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    def _show_core_hover_preview(self, planet: str, event=None) -> None:
        try:
            self._hide_core_hover_preview()
            source = Path(__file__).resolve().parent / "assets" / "gateway_symbols" / f"{planet}.png"
            if not source.exists():
                return

            image = tk.PhotoImage(file=str(source))
            while image.width() > 240 or image.height() > 240:
                image = image.subsample(2, 2)

            self._core_hover_image = image
            self._core_hover_planet = planet

            popup = tk.Toplevel(self.root)
            self._core_hover_window = popup
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)
            popup.configure(bg="#0b0d12")

            frame = tk.Frame(
                popup, bg="#11151d", bd=1, relief="solid",
                highlightthickness=1,
                highlightbackground="#55d7ff",
                highlightcolor="#55d7ff",
            )
            frame.pack()

            tk.Label(
                frame, text=f"{planet} Core",
                bg="#11151d", fg="#5fd7ff",
                font=("Segoe UI", 10, "bold"),
            ).pack(padx=8, pady=(6, 2))

            tk.Label(
                frame, image=self._core_hover_image,
                bg="#11151d", bd=0,
            ).pack(padx=8, pady=(0, 8))

            self._move_core_hover_preview(event)
        except Exception:
            self._hide_core_hover_preview()

    def _move_core_hover_preview(self, event=None) -> None:
        popup = self._core_hover_window
        if popup is None:
            return
        try:
            if event is not None:
                x = int(event.x_root) + 18
                y = int(event.y_root) + 18
            else:
                x = self.root.winfo_pointerx() + 18
                y = self.root.winfo_pointery() + 18

            popup.update_idletasks()
            pw = popup.winfo_reqwidth()
            ph = popup.winfo_reqheight()
            sw = popup.winfo_screenwidth()
            sh = popup.winfo_screenheight()

            if x + pw > sw - 8:
                x = max(8, x - pw - 36)
            if y + ph > sh - 8:
                y = max(8, y - ph - 36)

            popup.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _update_selected_location_details(self, force: bool = False) -> None:
        # v0.70: seven-planet dashboard with vertically aligned category rows.
        # Each planet uses the same fixed row heights so Gateway lines up with
        # Gateway, Core with Core, Terrarium with Terrarium, and so on.
        target = self._detail_location_target()
        if (
            not force
            and target == self._last_rendered_detail_target
            and self.location_cards_frame.winfo_children()
        ):
            return

        self._last_rendered_detail_target = target
        for child in self.location_cards_frame.winfo_children():
            child.destroy()

        base = Path(__file__).resolve().parent / "assets"

        def load_cached(cache, key, path):
            image = cache.get(key)
            if image is None:
                image = tk.PhotoImage(file=str(path))
                while image.width() > 48 or image.height() > 48:
                    image = image.subsample(2, 2)
                cache[key] = image
            return image

        def load_single(attr_name, path):
            image = getattr(self, attr_name)
            if image is None:
                image = tk.PhotoImage(file=str(path))
                while image.width() > 48 or image.height() > 48:
                    image = image.subsample(2, 2)
                setattr(self, attr_name, image)
            return image

        # Same heights for every planet.  The taller rows accommodate the
        # longest descriptions while keeping every category aligned.
        category_heights = {
            "Key Resources": 50,
            "Gateway": 40,
            "Core": 40,
            "Terrarium": 50,
            "Galastropods": 54,
            "EXO Aids": 78,
            "Circuit(s)": 40,
        }

        for col, planet in enumerate(PLANETS):
            selected = planet == target
            panel = tk.Frame(
                self.location_cards_frame,
                bg="#151a23",
                bd=1,
                relief="solid",
                highlightthickness=1 if selected else 0,
                highlightbackground="#55d7ff",
                highlightcolor="#55d7ff",
            )
            panel.grid(row=0, column=col, sticky="nsew", padx=2, pady=1)
            self.location_cards_frame.columnconfigure(col, weight=1, uniform="planet")

            # Planet heading occupies an identical fixed row in each column.
            panel.grid_columnconfigure(0, weight=1)
            panel.grid_rowconfigure(0, minsize=21)

            tk.Label(
                panel,
                text=planet,
                bg="#151a23",
                fg="#73ddff" if selected else "#f1f5f9",
                font=("Segoe UI", 10, "bold"),
            ).grid(row=0, column=0, sticky="ew", pady=(0, 0))

            cards = PLANET_DETAIL_CARDS.get(planet, [])

            planet_img = None
            try:
                planet_img = load_cached(
                    self._planet_sky_images,
                    planet,
                    base / "planet_ui" / f"{planet}.png",
                )
            except Exception:
                pass

            rows = []
            if cards:
                rows.append(("Key Resources", cards[0][1], cards[0][2], planet_img))

            for title, value, secondary in cards[1:]:
                icon = None
                try:
                    if title == "Gateway":
                        icon = load_single(
                            "_gateway_chamber_image",
                            base / "gateway_chamber" / "Gateway_Chamber.png",
                        )
                    elif title == "Core":
                        icon = load_cached(
                            self._gateway_symbol_images,
                            planet,
                            base / "gateway_symbols" / f"{planet}.png",
                        )
                    elif title == "Terrarium":
                        icon = load_cached(
                            self._shell_images,
                            planet,
                            base / "galastropod_shells" / f"{planet}.png",
                        )
                    elif title == "Galastropods":
                        icon = load_cached(
                            self._galastropod_images,
                            planet,
                            base / "galastropods" / f"{planet}.png",
                        )
                    elif title.startswith("EXO Aids"):
                        icon = load_single(
                            "_exo_aid_image",
                            base / "exo_aid" / "EXO_Aid.png",
                        )
                    elif title == "Circuit(s)":
                        icon = load_single(
                            "_circuit_image",
                            base / "circuit" / "Circuit.png",
                        )
                except Exception:
                    icon = None

                rows.append((title, value, secondary, icon))

            for row_index, (title, value, secondary, icon) in enumerate(rows, start=1):
                row_height = category_heights.get(title, 64)
                panel.grid_rowconfigure(row_index, minsize=row_height)

                row = tk.Frame(
                    panel,
                    bg="#151a23",
                    height=row_height,
                )
                row.grid(
                    row=row_index,
                    column=0,
                    sticky="nsew",
                    padx=2,
                    pady=0,
                )
                row.grid_propagate(False)
                row.grid_columnconfigure(1, weight=1)

                icon_box = tk.Frame(
                    row,
                    bg="#151a23",
                    width=48,
                    height=row_height,
                )
                icon_box.grid(row=0, column=0, sticky="nsw", padx=(0, 4))
                icon_box.grid_propagate(False)

                if icon is not None:
                    icon_label = tk.Label(
                        icon_box,
                        image=icon,
                        bg="#151a23",
                        bd=0,
                    )
                    icon_label.place(relx=0.5, rely=0.5, anchor="center")
                    if title == "Core":
                        icon_label.configure(cursor="hand2")
                        icon_label.bind("<Enter>", lambda e, p=planet: self._show_core_hover_preview(p, e))
                        icon_label.bind("<Motion>", self._move_core_hover_preview)
                        icon_label.bind("<Leave>", self._hide_core_hover_preview)
                else:
                    tk.Label(
                        icon_box,
                        text="•",
                        bg="#151a23",
                        fg="#566579",
                        font=("Segoe UI", 18),
                    ).place(relx=0.5, rely=0.5, anchor="center")

                text_box = tk.Frame(row, bg="#151a23")
                text_box.grid(row=0, column=1, sticky="nsew")
                text_box.grid_columnconfigure(0, weight=1)

                tk.Label(
                    text_box,
                    text=title,
                    bg="#151a23",
                    fg="#5fd7ff",
                    font=("Segoe UI", 8, "bold"),
                    anchor="w",
                    justify="left",
                ).grid(row=0, column=0, sticky="ew", pady=(1, 0))

                display_text = value
                if secondary:
                    display_text = (display_text + "\n" if display_text else "") + secondary
                if not display_text:
                    display_text = "—"

                tk.Label(
                    text_box,
                    text=display_text,
                    bg="#151a23",
                    fg="#e7ecf2",
                    font=("Segoe UI", 8),
                    anchor="nw",
                    justify="left",
                    wraplength=102,
                ).grid(row=1, column=0, sticky="new", pady=(0, 0))

    def _set_initial_window_geometry(self) -> None:
        """
        Open at a normal resizable size that shows the full gameplay table,
        save browser, and Planet Information panel.
        """
        try:
            self.root.update_idletasks()
            self._update_selected_location_details(force=True)
            self.root.update_idletasks()

            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            left_req = max(
                self.table_text.winfo_reqwidth(),
                self.location_detail_frame.winfo_reqwidth(),
                820,
            )
            right_req = 340
            horizontal_chrome = 90

            width = left_req + right_req + horizontal_chrome
            width = min(width, max(1000, screen_w - 60))
            width = max(width, 1120)

            requested_h = self.root.winfo_reqheight()
            # v0.73: use more of the available laptop-height while leaving
            # room for the Windows taskbar/title bar at 125% scaling.
            height = requested_h + 8
            height = min(height, max(650, screen_h - 40))
            height = max(height, 720)

            x = max(0, (screen_w - width) // 2)
            y = max(0, (screen_h - height) // 2)

            self.root.geometry(f"{width}x{height}+{x}+{y}")
            self.root.minsize(950, 650)
            self.root.resizable(True, True)
        except Exception:
            pass

    def _set_initial_table_split(self) -> None:
        """
        Give the bottom gameplay totals table a guaranteed useful share of the
        available space.  The user can drag the divider afterward.
        """
        try:
            paned = self._vertical_table_paned
            height = max(1, paned.winfo_height())
            # Roughly 38% diagnostic / 62% gameplay totals.
            paned.sashpos(0, int(height * 0.38))
        except Exception:
            pass

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    @staticmethod
    def _fmt(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def _fmt_table_time(seconds: float) -> str:
        """Display-only gameplay-table time as hours:minutes."""
        total_minutes = max(0, int(seconds)) // 60
        hours, minutes = divmod(total_minutes, 60)
        return f"{hours:02d}:{minutes:02d}"

    def _latest_diagnostic_save(self, logical_name: str) -> Path | None:
        root = self._diagnostics_autosaves_root()
        folder = root / logical_name
        if not folder.exists() or not folder.is_dir():
            return None

        try:
            saves = [
                p for p in folder.iterdir()
                if p.is_file() and p.suffix.lower() == ".savegame"
            ]
            saves.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return saves[0] if saves else None
        except Exception:
            return None

    @staticmethod
    def _physical_save_suffix(filename: str) -> str | None:
        """
        Return the physical Astroneer save suffix after '$', excluding extension.

        Example:
            SAVE_4$2026.08.20-11.55.01.savegame
            TEST GATEWAY STATUS$2026.08.20-11.55.01.savegame

        Both return:
            2026.08.20-11.55.01

        Astroneer's in-game rename changes the descriptive name before '$'
        while preserving the current physical suffix for the rename event.
        """
        name = filename
        if name.lower().endswith(".savegame"):
            name = name[:-9]
        if "$" not in name:
            return None
        return name.split("$", 1)[1].strip() or None

    @staticmethod
    def _file_sha256(path: Path) -> str | None:
        try:
            h = hashlib.sha256()
            with path.open("rb") as f:
                while True:
                    block = f.read(1024 * 1024)
                    if not block:
                        break
                    h.update(block)
            return h.hexdigest()
        except Exception:
            return None

    def _latest_diagnostic_hash(self, logical_name: str) -> str | None:
        root = self._diagnostics_autosaves_root()
        folder = root / logical_name
        if not folder.exists() or not folder.is_dir():
            return None

        try:
            saves = [
                p for p in folder.iterdir()
                if p.is_file() and p.suffix.lower() == ".savegame"
            ]
            saves.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception:
            return None

        if not saves:
            return None

        return self._file_sha256(saves[0])

    def _merge_tracker_records(self, dst: dict, src: dict) -> None:
        """Merge only if a transient new-name tracker record already exists."""
        dst["total_seconds"] = float(dst.get("total_seconds", 0.0)) + float(
            src.get("total_seconds", 0.0)
        )
        dst["deaths"] = int(dst.get("deaths", 0)) + int(src.get("deaths", 0))

        for field in ("visits", "deaths_by_location", "location_seconds"):
            src_map = src.get(field, {})
            if not isinstance(src_map, dict):
                continue
            dst_map = dst.setdefault(field, {})
            if not isinstance(dst_map, dict):
                dst_map = {}
                dst[field] = dst_map
            for key, value in src_map.items():
                if field == "location_seconds":
                    dst_map[key] = float(dst_map.get(key, 0.0)) + float(value)
                else:
                    dst_map[key] = int(dst_map.get(key, 0)) + int(value)

        # Prefer meaningful current/new metadata only where the destination lacks it.
        for key, value in src.items():
            if key in {
                "total_seconds", "deaths", "visits",
                "deaths_by_location", "location_seconds"
            }:
                continue
            if key not in dst or dst.get(key) in (None, "", [], {}):
                dst[key] = value

    def _detect_and_migrate_rename(self, saves: list[SaveInfo]) -> bool:
        """
        Detect an Astroneer in-game rename before gone-retirement.

        Primary proof:
          exactly one logical save disappears,
          exactly one logical save appears,
          and the physical '$...' suffix is unchanged.

        Fallback:
          internal world fingerprint match.
        """
        current: dict[str, SaveInfo] = {}
        for save in saves:
            prior = current.get(save.display_name)
            if prior is None or save.modified_time > prior.modified_time:
                current[save.display_name] = save

        old_names = set(self._previous_physical_saves)
        new_names = set(current)

        gone = [n for n in (old_names - new_names) if not self._is_gone_name(n)]
        added = [n for n in (new_names - old_names) if not self._is_gone_name(n)]

        migrated = False

        if len(gone) == 1 and len(added) == 1:
            old_name = gone[0]
            new_name = added[0]
            old_info = self._previous_physical_saves[old_name]
            new_info = current[new_name]

            tracked = self.data.get("saves", {})
            old_rec = tracked.get(old_name) if isinstance(tracked, dict) else None

            if isinstance(old_rec, dict):
                old_suffix = self._physical_save_suffix(old_info.filename)
                new_suffix = self._physical_save_suffix(new_info.filename)

                suffix_match = bool(
                    old_suffix and new_suffix and old_suffix == new_suffix
                )

                fingerprint_match = False
                if not suffix_match:
                    old_sig = old_rec.get("_rename_world_signature")
                    if not old_sig:
                        old_diag = self._latest_diagnostic_save(old_name)
                        if old_diag is not None:
                            old_sig = get_rename_fingerprint(old_diag).signature

                    new_sig = get_rename_fingerprint(new_info.path).signature
                    fingerprint_match = bool(
                        old_sig and new_sig and old_sig == new_sig
                    )

                if suffix_match or fingerprint_match:
                    new_rec = tracked.get(new_name)
                    if isinstance(new_rec, dict) and new_rec is not old_rec:
                        self._merge_tracker_records(old_rec, new_rec)
                        tracked.pop(new_name, None)

                    tracked.pop(old_name, None)
                    tracked[new_name] = old_rec

                    # Refresh internal fingerprint after rename when possible.
                    new_fp = get_rename_fingerprint(new_info.path)
                    if new_fp.signature:
                        old_rec["_rename_world_signature"] = new_fp.signature

                    # Preserve every live reference.
                    if self.timing.state.active_save == old_name:
                        self.timing.state.active_save = new_name

                    if (
                        self.detector.state.active_save is not None
                        and self.detector.state.active_save.display_name == old_name
                    ):
                        self.detector.state.active_save = new_info

                    if self._pending_logical_name == old_name:
                        self._pending_logical_name = new_name

                    if self._selected_view_save == old_name:
                        self._selected_view_save = new_name

                    # Carry Last 10 Saves folder forward.
                    diag_root = self._diagnostics_autosaves_root()
                    old_folder = diag_root / old_name
                    new_folder = diag_root / new_name

                    if old_folder.exists():
                        if new_folder.exists():
                            try:
                                for p in old_folder.iterdir():
                                    target = new_folder / p.name
                                    if not target.exists():
                                        p.rename(target)
                                old_folder.rmdir()
                            except Exception:
                                pass
                        else:
                            try:
                                old_folder.rename(new_folder)
                            except Exception:
                                pass

                    self.storage.save(self.data)
                    migrated = True

        self._previous_physical_saves = current
        return migrated

    @staticmethod
    def _is_gone_name(name: str) -> bool:
        """Recognize all legacy and canonical retired-save name formats."""
        return bool(re.match(r"^\(gone(?:\s*\d+)?\)\s+", name, flags=re.IGNORECASE))

    def _retire_missing_tracker_records(self) -> None:
        """
        Retire missing physical saves using one canonical sequential scheme:
            (gone1) SAVE_4
            (gone2) SAVE_4
            ...
        Legacy gone names are recognized as already retired and are never
        wrapped a second time.
        """
        tracked = self.data.get("saves", {})
        if not isinstance(tracked, dict):
            return

        physical = find_savegames(self.save_directory)
        physical_names = {s.display_name for s in physical}

        changed = False

        for name in list(tracked.keys()):
            # Critical: never retire an already-retired record, regardless of
            # whether it uses legacy "(gone)" / "(gone 2)" or canonical "(gone2)".
            if self._is_gone_name(name):
                continue

            if name in physical_names:
                continue

            suffix = 1
            while True:
                canonical = f"(gone{suffix}) {name}"
                legacy_spaced = f"(gone {suffix}) {name}"
                legacy_plain = f"(gone) {name}" if suffix == 1 else None

                collision = (
                    canonical in tracked
                    or legacy_spaced in tracked
                    or (legacy_plain is not None and legacy_plain in tracked)
                )
                if not collision:
                    retired = canonical
                    break
                suffix += 1

            tracked[retired] = tracked.pop(name)
            changed = True

            if self._selected_view_save == name:
                self._selected_view_save = retired

            if self.timing.state.active_save == name:
                self.timing.state.active_save = None
                self.timing.state.session = 0.0
                self.timing.state.pending_location_time = 0.0

            if (
                self.detector.state.active_save is not None
                and self.detector.state.active_save.display_name == name
            ):
                self.detector.state.active_save = None

            if self._pending_logical_name == name:
                self._pending_logical_name = None

            root = self._diagnostics_autosaves_root()
            normal = root / name
            retired_folder = root / retired

            if normal.exists() and not retired_folder.exists():
                try:
                    normal.rename(retired_folder)
                except Exception:
                    pass

        if changed:
            self.storage.save(self.data)

    def _all_save_names(self) -> list[str]:
        # First retire any tracked records whose physical save disappeared.
        # This is the critical separation that prevents a new SAVE_1 from
        # inheriting an old deleted SAVE_1's tracker history.
        self._retire_missing_tracker_records()

        tracked = self.data.get("saves", {})
        tracked_names = set(tracked.keys()) if isinstance(tracked, dict) else set()

        physical = find_savegames(self.save_directory)
        self._physical_save_map = {}

        for save in physical:
            existing = self._physical_save_map.get(save.display_name)
            if existing is None or save.modified_time > existing.modified_time:
                self._physical_save_map[save.display_name] = save

        names = tracked_names | set(self._physical_save_map.keys())

        def key(name: str):
            # Keep retired/gone records grouped at the bottom.
            if name.startswith("(gone"):
                return (0, 0, name.lower())

            physical_save = self._physical_save_map.get(name)
            physical_mtime = physical_save.modified_time if physical_save else 0
            return (1, physical_mtime, name.lower())

        return sorted(names, key=key, reverse=True)

    def _refresh_save_list(self) -> None:
        names = self._all_save_names()
        selected = self._selected_view_save

        # Preserve the user's current scroll position. Rebuilding the Listbox
        # used to reset the view and .see(selected) then jumped back to the
        # active save every refresh.
        try:
            yview = self.save_listbox.yview()
            y_fraction = yview[0] if yview else 0.0
        except Exception:
            y_fraction = 0.0

        self.save_listbox.delete(0, "end")

        for name in names:
            self.save_listbox.insert("end", name)

        if not names:
            self._selected_view_save = None
            self._update_save_info_label()
            return

        if selected not in names:
            selected = names[0]

        self._selected_view_save = selected
        index = names.index(selected)
        self.save_listbox.selection_clear(0, "end")
        self.save_listbox.selection_set(index)

        # Restore where the user was browsing. Auto-scroll to a live save is
        # handled only by _auto_select_live_save(), on a real live-save edge.
        try:
            self.save_listbox.yview_moveto(y_fraction)
        except Exception:
            pass

        self._update_save_info_label()

    def _auto_select_live_save(self, save_name: str) -> None:
        """
        Select/scroll to a live save only once when it is newly identified.

        Repeated one-second UI refreshes and ordinary game saves do not move
        the user's list position. When the game stops, the edge marker resets,
        so the next game launch can auto-select its active save once.
        """
        if not self._game_was_running:
            return
        if not save_name:
            return
        if save_name == self._last_auto_selected_live_save:
            return

        names = self._all_save_names()
        if save_name not in names:
            return

        self._last_auto_selected_live_save = save_name
        self._selected_view_save = save_name

        try:
            index = names.index(save_name)
            self.save_listbox.selection_clear(0, "end")
            self.save_listbox.selection_set(index)
            self.save_listbox.activate(index)
            self.save_listbox.see(index)
        except Exception:
            pass

        self._update_save_info_label()


    def _update_save_info_label(self) -> None:
        name = self._selected_view_save
        if not name:
            self.save_info_label.configure(text="")
            return

        physical = self._physical_save_map.get(name)
        tracked = self.data.get("saves", {}).get(name)

        lines = []
        if physical is not None:
            try:
                from datetime import datetime
                modified = datetime.fromtimestamp(physical.modified_time).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                modified = str(physical.modified_time)

            lines.append(f"File: {physical.path.name}")
            lines.append(f"Modified: {modified}")
        else:
            lines.append("Save file: not currently found on disk")
            if self._is_gone_name(name) and isinstance(tracked, dict):
                lines.append("Status: GONE — retired/ignored by live tracker")
                lines.append("Refresh Saves permanently removes this recovery record.")

        lines.append(
            "Tracker record: "
            + ("Yes" if isinstance(tracked, dict) else "No")
        )

        self.save_info_label.configure(text="\n".join(lines))

    def _diagnostics_autosaves_root(self) -> Path:
        root = tracker_data_file().parent / "Diagnostics" / "Autosaves"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _open_last_10_saves(self) -> None:
        """
        Open the diagnostics/autosave folder for the save selected in the
        right-hand save list. Fall back to the overall Autosaves root only
        when no save is selected.
        """
        try:
            import os

            selected = self._selected_view_save
            root = self._diagnostics_autosaves_root()

            if selected:
                candidates = [
                    root / selected,
                    root / self._safe_diag_name(selected),
                ]
                folder = next((p for p in candidates if p.exists() and p.is_dir()), None)

                if folder is None:
                    folder = root / self._safe_diag_name(selected)
                    folder.mkdir(parents=True, exist_ok=True)

                os.startfile(str(folder))
            else:
                os.startfile(str(root))
        except Exception:
            pass

    @staticmethod
    def _safe_diag_name(name: str) -> str:
        return "".join(
            ch if ch.isalnum() or ch in " _$.-" else "_"
            for ch in name
        ).strip()

    def _remove_diagnostics_for_save(self, save_name: str) -> None:
        root = self._diagnostics_autosaves_root()
        safe = self._safe_diag_name(save_name)

        candidates = {save_name, safe}

        # Also tolerate legacy pre-v0.34 naming.
        if not self._is_gone_name(save_name):
            candidates.add(f"(gone) {save_name}")
            candidates.add(f"(gone) {safe}")

        for child in list(root.iterdir()):
            if not child.is_dir():
                continue
            if child.name in candidates:
                try:
                    import shutil
                    shutil.rmtree(child)
                except Exception:
                    pass

    def _sync_and_refresh_saves(self) -> None:
        """
        Deliberate destructive sync:
        - removes retired '(gone)' tracker records
        - removes their matching diagnostics/autosave folders
        - removes any other tracker record with no physical save
        """
        physical = find_savegames(self.save_directory)
        active_names = {s.display_name for s in physical}

        saves = self.data.get("saves", {})
        removed = []

        if isinstance(saves, dict):
            for name in list(saves.keys()):
                retired = self._is_gone_name(name)
                physically_missing = name not in active_names

                if retired or physically_missing:
                    removed.append(name)
                    saves.pop(name, None)
                    self._remove_diagnostics_for_save(name)

                    if self._selected_view_save == name:
                        self._selected_view_save = None

                    # Live tracker names can never be retired '(gone)' names.
                    if self.timing.state.active_save == name:
                        self.timing.state.active_save = None

        if removed:
            self.storage.save(self.data)

        self._refresh_save_list()

    def _open_research_list(self) -> None:
        def selected_save_name():
            if self._selected_view_save:
                return self._selected_view_save
            if self._detector_primed and self.detector.state.active_save:
                return self.detector.state.active_save
            return None

        if self._research_list_window is None:
            self._research_list_window = ResearchListWindow(
                self.root,
                self.data,
                self.storage,
                tracker_data_file().parent,
                selected_save_name,
            )
        self._research_list_window.show()

    def _play_now(self) -> None:
        # PLAY NOW is a timing start edge. Begin Pending Startup immediately,
        # before Steam/Astroneer has necessarily appeared in the process list.
        if not self._startup_timer_armed and self.timing.state.active_save is None:
            self.timing.game_started()
            self._startup_timer_armed = True
            self._last_tick = time.monotonic()
            self.timing.trace_external(
                "PLAY NOW — STARTUP TIMER ARMED",
                (
                    "User pressed PLAY NOW. Pending Startup begins immediately "
                    "from this point, before Astroneer process detection."
                ),
            )

        try:
            import os
            os.startfile("steam://rungameid/361420")
        except Exception:
            pass

    def _clear_all_data(self) -> None:
        answer = messagebox.askyesno(
            "Clear All Tracker Data?",
            (
                "Are you sure you want to clear ALL Astroneer Gameplay Tracker data?\\n\\n"
                "This will permanently erase tracked play time, visits, deaths, "
                "sessions, and diagnostic snapshots.\\n\\n"
                "Your actual Astroneer save games will NOT be deleted."
            ),
            icon="warning",
        )

        if not answer:
            return

        try:
            # Reset persistent tracker data only.
            self.data.clear()
            self.data["saves"] = {}

            # Reset helper objects that hold references/live state.
            self.location_state.data = self.data
            self.timing.data = self.data
            self.deaths.data = self.data

            self.timing.game_stopped()
            self.deaths.reset_session()
            self._last_auto_selected_live_save = None

            self._selected_view_save = None
            self._last_auto_selected_live_save = None
            self._last_detected_location = None
            self._last_xyz = None
            self._last_death_detected = False
            self._last_backpack_signature = None

            # Clear Diagnostics content, but never Astroneer's SaveGames.
            diagnostics_root = tracker_data_file().parent / "Diagnostics"
            if diagnostics_root.exists():
                import shutil
                for child in diagnostics_root.iterdir():
                    try:
                        if child.is_dir():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
                    except Exception:
                        pass

            self._diagnostics_autosaves_root()
            self.storage.save(self.data)
            self._refresh_save_list()

            messagebox.showinfo(
                "Tracker Data Cleared",
                (
                    "All tracker data has been cleared.\\n\\n"
                    "Your Astroneer save games were not changed."
                ),
            )
        except Exception as exc:
            messagebox.showerror(
                "Clear Data Error",
                f"The tracker could not clear all data.\\n\\n{exc}",
            )

    def _open_timer_trace(self) -> None:
        try:
            import os
            self._timer_trace_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._timer_trace_path.exists():
                self._timer_trace_path.write_text(
                    "Timer trace has not recorded any events yet.\n",
                    encoding="utf-8",
                )
            os.startfile(str(self._timer_trace_path))
        except Exception:
            pass

    def _copy_timer_trace(self) -> None:
        try:
            text = self._timer_trace_path.read_text(encoding="utf-8")
        except Exception:
            text = "Timer trace is not available yet."

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception:
            pass

    def _open_death_trace(self) -> None:
        try:
            import os
            self._death_trace_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._death_trace_path.exists():
                self._death_trace_path.write_text(
                    "Death trace has not recorded any save events yet.\n",
                    encoding="utf-8",
                )
            os.startfile(str(self._death_trace_path))
        except Exception:
            pass

    def _copy_death_trace(self) -> None:
        try:
            text = self._death_trace_path.read_text(encoding="utf-8")
        except Exception:
            text = "Death trace is not available yet."

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception:
            pass

    def _append_gateway_core_trace(
        self,
        *,
        save_name: str,
        location: str,
        gateway_total: int | None,
        previous_total: int | None,
        delta: int | None,
        assigned_planet: str | None,
        planet_gateway_count: int | None,
        core_planet: str | None,
        core_found: bool,
        core_active: bool | None,
        core_note: str,
        note: str,
    ) -> None:
        try:
            self._gateway_core_trace_path.parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
            with self._gateway_core_trace_path.open("a", encoding="utf-8") as f:
                f.write("\n" + "=" * 88 + "\n")
                f.write(f"GATEWAY / CORE TRACE  {stamp}\n")
                f.write(f"Save: {save_name}\n")
                f.write(f"Detected Location: {location}\n")
                f.write(f"Gateway Object Total: {gateway_total if gateway_total is not None else '—'}\n")
                f.write(f"Previous Gateway Total: {previous_total if previous_total is not None else '—'}\n")
                f.write(f"Gateway Delta: {delta if delta is not None else '—'}\n")
                f.write(f"Assigned Planet: {assigned_planet or '—'}\n")
                f.write(
                    f"Stored Planet Gateway Count: "
                    f"{planet_gateway_count if planet_gateway_count is not None else '—'}\n"
                )
                f.write(f"Core Planet: {core_planet or '—'}\n")
                f.write(f"Core Engine Found: {'YES' if core_found else 'No'}\n")
                f.write(
                    f"Core Active: "
                    f"{'YES' if core_active is True else 'No' if core_active is False else '—'}\n"
                )
                f.write(f"Core Probe Note: {core_note}\n")
                f.write(f"Note: {note}\n")
                f.write("=" * 88 + "\n")
        except Exception:
            pass

    def _copy_gateway_core_trace(self) -> None:
        try:
            text = self._gateway_core_trace_path.read_text(encoding="utf-8")
        except Exception:
            text = "Gateway/Core trace is not available yet."

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception:
            pass

    def _open_diagnostics_folder(self) -> None:
        try:
            import os
            diagnostics_root = tracker_data_file().parent / "Diagnostics"
            diagnostics_root.mkdir(parents=True, exist_ok=True)
            os.startfile(str(diagnostics_root))
        except Exception:
            pass

    def _open_save_folder(self) -> None:
        try:
            import os
            os.startfile(str(self.save_directory))
        except Exception:
            pass

    def _open_manual_data_input(self) -> None:
        """Manually correct persistent tracker visit counts for a selected save."""
        save_name = self._selected_view_save
        if not save_name:
            messagebox.showinfo(
                "Manual Data Input",
                "Select the save you want to correct in the right-hand list first.",
            )
            return

        saves_map = self.data.setdefault("saves", {})
        entry = saves_map.get(save_name)
        if not isinstance(entry, dict):
            messagebox.showinfo(
                "Manual Data Input",
                "The selected save does not have a tracker record yet.",
            )
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Manual Data Input")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Manual Data Input",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(
            frame,
            text=f"Save: {save_name}",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 10))

        ttk.Label(
            frame,
            text="Persistent Planet / Location Visits",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 5))

        # LocationStateTracker stores persistent visit counts under
        # entry["visits"]. visits_for() returns a copy, so the editor must read
        # and write the underlying persistent map directly.
        visit_map = entry.setdefault("visits", {})
        if not isinstance(visit_map, dict):
            visit_map = {}
            entry["visits"] = visit_map

        visit_vars = {}
        row = 3
        for location in TRACKED_LOCATIONS:
            ttk.Label(frame, text=location).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=1
            )
            current = 0
            try:
                current = int(visit_map.get(location, 0))
            except Exception:
                current = 0
            var = tk.StringVar(value=str(max(0, current)))
            visit_vars[location] = var
            spin = ttk.Spinbox(
                frame,
                from_=0,
                to=999,
                textvariable=var,
                width=7,
            )
            spin.grid(row=row, column=1, sticky="e", pady=1)
            row += 1

        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(9, 8)
        )
        row += 1

        ttk.Label(
            frame,
            text="Persistent Deaths",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 4))
        row += 1

        ttk.Label(frame, text="Total Deaths").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=1
        )
        try:
            current_deaths = max(0, int(entry.get("deaths", 0)))
        except Exception:
            current_deaths = 0
        death_var = tk.StringVar(value=str(current_deaths))
        ttk.Spinbox(
            frame,
            from_=0,
            to=999,
            textvariable=death_var,
            width=7,
        ).grid(row=row, column=1, sticky="e", pady=1)
        row += 1

        ttk.Label(
            frame,
            text=(
                "Use this only to correct tracker history. "
                "It does not modify the Astroneer savegame."
            ),
            wraplength=390,
            justify="left",
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 10))
        row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=3, sticky="e")

        def save_manual_data() -> None:
            corrected = {}
            try:
                for location, var in visit_vars.items():
                    value = int(var.get().strip())
                    if value < 0:
                        raise ValueError
                    corrected[location] = value

                corrected_deaths = int(death_var.get().strip())
                if corrected_deaths < 0:
                    raise ValueError
            except Exception:
                messagebox.showerror(
                    "Manual Data Input",
                    "Visit and death counts must be whole numbers of 0 or greater.",
                    parent=dialog,
                )
                return

            # LocationStateTracker reads this exact persistent map.
            save_entry = self.data.setdefault("saves", {}).setdefault(
                save_name, {}
            )
            save_entry["visits"] = dict(corrected)

            # DeathTracker.deaths_for() reads entry["deaths"]. Manual correction
            # changes only this persistent tracker count; automatic death
            # detection logic remains completely unchanged.
            save_entry["deaths"] = corrected_deaths

            # Remove the mistaken v0.95/v0.96 key if it exists so there is only
            # one source of truth for manual and automatic visit tracking.
            save_entry.pop("location_visits", None)

            self.storage.save(self.data)

            # Close first, then run the same UI path used during normal tracker
            # refreshes so the corrected count appears immediately.
            dialog.destroy()
            self._update_ui(
                self._game_was_running,
                self.detector.state.active_save
                if self._detector_primed
                else None,
            )

        ttk.Button(
            buttons,
            text="Cancel",
            command=dialog.destroy,
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            buttons,
            text="Save Changes",
            command=save_manual_data,
        ).pack(side="right")

    def _open_copy_stored_data_dialog(self) -> None:
        source_name = self._selected_view_save
        if not source_name:
            messagebox.showinfo(
                "Copy Stored Data",
                "Select the source save in the right-hand list first.",
            )
            return

        names = [
            name for name in self._all_save_names()
            if name != source_name and not self._is_gone_name(name)
        ]

        if not names:
            messagebox.showinfo(
                "Copy Stored Data",
                "There is no other destination save available yet.",
            )
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Copy Stored Tracker Data")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Copy all stored tracker data",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            frame,
            text=f"Source: {source_name}",
        ).pack(anchor="w", pady=(8, 10))

        ttk.Label(
            frame,
            text="Destination save:",
        ).pack(anchor="w")

        destination_var = tk.StringVar(value=names[0])
        combo = ttk.Combobox(
            frame,
            textvariable=destination_var,
            values=names,
            state="readonly",
            width=42,
        )
        combo.pack(fill="x", pady=(4, 12))
        combo.focus_set()

        ttk.Label(
            frame,
            text=(
                "This replaces the destination's tracker record with a copy "
                "of the source record. The Astroneer save file itself is not changed."
            ),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x")

        def perform_copy() -> None:
            destination_name = destination_var.get().strip()
            if not destination_name or destination_name == source_name:
                return

            source_record = self.data.get("saves", {}).get(source_name)
            if not isinstance(source_record, dict):
                messagebox.showerror(
                    "Copy Stored Data",
                    f"{source_name} does not have a tracker record to copy.",
                    parent=dialog,
                )
                return

            answer = messagebox.askyesno(
                "Copy Stored Data?",
                (
                    f"Copy ALL stored tracker data from:\\n\\n"
                    f"    {source_name}\\n\\n"
                    f"to:\\n\\n"
                    f"    {destination_name}\\n\\n"
                    "Any existing tracker data for the destination will be replaced.\\n"
                    "The actual Astroneer savegame will not be changed."
                ),
                icon="warning",
                parent=dialog,
            )
            if not answer:
                return

            saves_map = self.data.setdefault("saves", {})
            destination_existing = saves_map.get(destination_name)
            destination_identity = None
            destination_death_baseline = None
            destination_pending_live = 0

            # Internal save-identity fields must belong to the destination,
            # not the source record being copied.
            if isinstance(destination_existing, dict):
                destination_identity = destination_existing.get(
                    "_rename_world_signature"
                )
                destination_death_baseline = copy.deepcopy(
                    destination_existing.get("_death_baseline")
                )
                destination_pending_live = int(
                    destination_existing.get(
                        "_death_pending_live_count", 0
                    )
                )

            copied = copy.deepcopy(source_record)

            # v0.82: Gateway counts copied from another tracker record are
            # explicitly marked non-authoritative. The next processed physical
            # save replaces them with direct save-file decoding.
            copied["gateway_progress_source"] = "copied_stored_data"
            copied.pop("gateway_direct_counts", None)
            copied.pop("gateway_direct_actor_count", None)

            copied.pop("_death_baseline", None)
            copied.pop("_death_pending_live_count", None)

            if destination_identity:
                copied["_rename_world_signature"] = destination_identity
            if destination_death_baseline is not None:
                copied["_death_baseline"] = destination_death_baseline
            if destination_pending_live:
                copied["_death_pending_live_count"] = destination_pending_live

            saves_map[destination_name] = copied

            # All helper objects share self.data, so persistence + UI refresh
            # is enough for the copied record to become immediately visible.
            self.storage.save(self.data)
            self._selected_view_save = destination_name
            self._refresh_save_list()
            self._update_ui(
                self._game_was_running,
                self.detector.state.active_save if self._detector_primed else None,
            )

            dialog.destroy()
            messagebox.showinfo(
                "Stored Data Copied",
                (
                    f"Tracker data copied from {source_name} to "
                    f"{destination_name}.\\n\\n"
                    "The Astroneer save file was not modified."
                ),
            )

        ttk.Button(
            button_row,
            text="Copy Data",
            command=perform_copy,
        ).pack(side="left")

        ttk.Button(
            button_row,
            text="Cancel",
            command=dialog.destroy,
        ).pack(side="right")

        dialog.update_idletasks()
        try:
            x = self.root.winfo_rootx() + max(
                0, (self.root.winfo_width() - dialog.winfo_width()) // 2
            )
            y = self.root.winfo_rooty() + max(
                0, (self.root.winfo_height() - dialog.winfo_height()) // 2
            )
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_view_save_selected(self, event=None) -> None:
        selection = self.save_listbox.curselection()
        if not selection:
            return

        self._selected_view_save = self.save_listbox.get(selection[0])
        self._update_save_info_label()
        self._update_selected_location_details(force=True)
        self._update_ui(
            self._game_was_running,
            self.detector.state.active_save if self._detector_primed else None,
        )

    def _view_save_name(self) -> str | None:
        if self._selected_view_save:
            return self._selected_view_save
        if self.timing.state.active_save:
            return self.timing.state.active_save
        names = self._all_save_names()
        return names[0] if names else None

    def _copy_captured_diagnostic(self) -> None:
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self._last_captured_diagnostic)
            self.root.update()
        except Exception:
            pass

    def _resolve_current_physical_save(
        self, logical_name: str, saves: list[SaveInfo]
    ) -> SaveInfo | None:
        matches = [s for s in saves if s.display_name == logical_name]
        if not matches:
            return None
        matches.sort(key=lambda s: s.modified_time, reverse=True)
        return matches[0]

    def _detect_location(self, path: Path):
        result = parse_player_actor_candidates(path)
        self._last_player_candidate_lines = []

        if result.error:
            self._last_player_candidate_lines = [f"Parser error: {result.error}"]
            return None, None

        usable = [
            c for c in result.candidates
            if (abs(c.x) + abs(c.y) + abs(c.z)) > 1.0
            and (
                "/Game/Character/DesignAstro.DesignAstro_C" in c.object_type
                or "PlayControllerInstance.PlayControllerInstance_C" in c.object_type
            )
        ]

        if not usable:
            self._last_player_candidate_lines = ["No usable player candidates."]
            return None, None

        def kind(c):
            if "/Game/Character/DesignAstro.DesignAstro_C" in c.object_type:
                return "DesignAstro"
            if "PlayControllerInstance.PlayControllerInstance_C" in c.object_type:
                return "PlayController"
            return "Other"

        # Record a compact candidate list for the frozen diagnostic.
        ordered = sorted(usable, key=lambda c: c.actor_record_index)
        for c in ordered[:12]:
            self._last_player_candidate_lines.append(
                f"#{c.actor_record_index} {kind(c):14} "
                f"X={c.x:,.1f} Y={c.y:,.1f} Z={c.z:,.1f}"
            )

        # Build coordinate clusters. The live player was proven in earlier
        # parser tests by DesignAstro and PlayController sharing the same
        # translation. Use a generous 5,000-unit agreement tolerance.
        clusters = []
        tolerance = 5000.0

        for c in usable:
            placed = False
            for cluster in clusters:
                cx, cy, cz = cluster["center"]
                d = math.sqrt(
                    (c.x - cx) ** 2 +
                    (c.y - cy) ** 2 +
                    (c.z - cz) ** 2
                )
                if d <= tolerance:
                    cluster["members"].append(c)
                    n = len(cluster["members"])
                    cluster["center"] = (
                        sum(m.x for m in cluster["members"]) / n,
                        sum(m.y for m in cluster["members"]) / n,
                        sum(m.z for m in cluster["members"]) / n,
                    )
                    placed = True
                    break

            if not placed:
                clusters.append({
                    "center": (c.x, c.y, c.z),
                    "members": [c],
                })

        def cluster_score(cluster):
            kinds = {kind(m) for m in cluster["members"]}
            has_design = "DesignAstro" in kinds
            has_controller = "PlayController" in kinds

            # Primary preference: both independent player representations agree.
            agreement = 2 if (has_design and has_controller) else 1

            # Prefer more supporting members, then newer/higher actor record
            # index when two clusters are otherwise equally supported.
            max_actor = max(m.actor_record_index for m in cluster["members"])
            return (agreement, len(cluster["members"]), max_actor)

        clusters.sort(key=cluster_score, reverse=True)
        chosen = clusters[0]
        cx, cy, cz = chosen["center"]

        # Prefer the exact DesignAstro coordinate from the winning cluster when
        # available; otherwise use PlayController; otherwise cluster center.
        chosen_members = chosen["members"]
        exact = next(
            (m for m in chosen_members if kind(m) == "DesignAstro"),
            None,
        )
        if exact is None:
            exact = next(
                (m for m in chosen_members if kind(m) == "PlayController"),
                None,
            )

        if exact is not None:
            x, y, z = exact.x, exact.y, exact.z
            selected_kind = kind(exact)
            selected_actor = exact.actor_record_index
        else:
            x, y, z = cx, cy, cz
            selected_kind = "cluster"
            selected_actor = -1

        self._last_player_candidate_lines.insert(
            0,
            f"SELECTED #{selected_actor} {selected_kind}: "
            f"X={x:,.1f} Y={y:,.1f} Z={z:,.1f}"
        )

        planet = classify_planet(x, y, z).planet
        return planet, (x, y, z)

    def _process_changed_save(self, saves: list[SaveInfo]) -> None:
        if self._pending_logical_name is None:
            return

        current = self._resolve_current_physical_save(
            self._pending_logical_name, saves
        )
        if current is None:
            return

        archived = self.diagnostics.archive_if_changed(current)
        if archived is None:
            return

        coordinate_location, xyz = self._detect_location(archived.destination)

        if coordinate_location:
            tracked_before_processing = (
                current.display_name in self.data.get("saves", {})
            )

            self.timing.trace_external(
                "GUI SAVE PROCESSING — BEFORE TRACKER MUTATIONS",
                (
                    "A changed save file has been parsed and location identified. "
                    "Capture timer state before visit/location/save processing."
                ),
                focus_save=current.display_name,
                details=[
                    f"Save={current.display_name}",
                    f"Detected coordinate location={coordinate_location}",
                    f"Tracker record existed before processing="
                    f"{tracked_before_processing}",
                ],
            )

            entry = self.data.setdefault("saves", {}).setdefault(
                current.display_name, {}
            )

            evidence = inspect_special_location(
                archived.destination,
                entry,
                coordinate_location,
            )
            location = evidence.detected or coordinate_location

            self._last_detected_location = location

            # v0.56: the planet identified by the processed save also becomes
            # the selected/highlighted planet row in the gameplay table.
            # This overrides any earlier manual planet selection.
            if location in PLANETS:
                self._selected_location_row = location

            self._last_xyz = xyz
            self._last_orbital_refs = evidence.orbital_refs
            self._last_landing_markers = evidence.landing_markers
            self._last_satellite_baseline = evidence.baseline
            self._last_sun_room_mesh = evidence.sun_room_mesh

            if xyz is not None:
                offprobe = probe_position(*xyz)
                self._last_nearest_planet = offprobe.nearest_planet
                self._last_nearest_distance = offprobe.nearest_distance

            # v0.81: Gateway counts are reconstructed DIRECTLY from this
            # physical save. No prior save, player location, or historical
            # gateway delta is required.
            #
            # The decoder parses live TeleporterControlPanel actor records,
            # reads each actor Transform, and assigns that surface Gateway to
            # the nearest packed-planet center.
            gateway_probe = get_gateway_activation_total(archived.destination)
            self._last_gateway_total = gateway_probe.total

            previous_gateway_total = entry.get("gateway_probe_last_total")
            self._last_gateway_previous = (
                int(previous_gateway_total)
                if previous_gateway_total is not None
                else None
            )

            if (
                gateway_probe.total is not None
                and self._last_gateway_previous is not None
            ):
                self._last_gateway_delta = (
                    int(gateway_probe.total) - self._last_gateway_previous
                )
            else:
                self._last_gateway_delta = None

            gateway_progress = entry.setdefault(
                "gateway_progress_by_planet", {}
            )
            core_progress = entry.setdefault(
                "core_progress_by_planet", {}
            )

            for _planet in GATEWAY_MAX_BY_PLANET:
                gateway_progress.setdefault(_planet, 0)
                core_progress.setdefault(_planet, False)

            assigned_gateway_planet = None

            direct_gateway_probe = probe_gateways_by_planet(
                archived.destination
            )

            if direct_gateway_probe.error is None:
                for _planet, _maximum in GATEWAY_MAX_BY_PLANET.items():
                    gateway_progress[_planet] = min(
                        _maximum,
                        max(
                            0,
                            int(
                                direct_gateway_probe.counts.get(
                                    _planet, 0
                                )
                            ),
                        ),
                    )

                entry["gateway_progress_initialized"] = True
                entry["gateway_progress_source"] = "direct_save_decode"
                entry["gateway_direct_actor_count"] = len(
                    direct_gateway_probe.actors
                )
                entry["gateway_direct_counts"] = {
                    p: int(gateway_progress[p])
                    for p in GATEWAY_MAX_BY_PLANET
                }
                gateway_note = (
                    "DIRECT SAVE DECODE: "
                    + ", ".join(
                        f"{p}={gateway_progress[p]}"
                        for p in GATEWAY_MAX_BY_PLANET
                    )
                )
            else:
                # Keep previously stored counts if a particular save cannot be
                # parsed. Never fall back to the old location/delta assignment.
                entry["gateway_progress_source"] = "decode_failed_retained"
                gateway_note = (
                    "DIRECT SAVE DECODE FAILED; retained previous stored "
                    f"Gateway counts: {direct_gateway_probe.error}"
                )

            if gateway_probe.total is not None:
                entry["gateway_probe_last_total"] = int(
                    gateway_probe.total
                )

            # v0.46e: scan every CONFIRMED Core engine mapping on every
            # recognized save, regardless of current player location. This
            # backfills already-completed Cores when a tracker version was
            # skipped or the user is now saving somewhere else.
            core_scan_results = {}
            for core_planet_name in GATEWAY_MAX_BY_PLANET:
                core_probe = probe_core_activation(
                    archived.destination,
                    core_planet_name,
                )
                core_scan_results[core_planet_name] = core_probe

                if core_probe.active is True:
                    core_progress[core_planet_name] = True
                elif core_probe.active is False:
                    # Never erase a previously proven activation.
                    core_progress.setdefault(core_planet_name, False)

            # Keep the compact diagnostic/trace focused on the current planet,
            # while the stored Core table above is updated globally.
            core_planet = location if location in GATEWAY_MAX_BY_PLANET else None
            if core_planet is not None:
                current_core_probe = core_scan_results.get(core_planet)
                core_found = bool(
                    current_core_probe and current_core_probe.found
                )
                core_active = (
                    current_core_probe.active
                    if current_core_probe is not None else None
                )
                core_note = (
                    current_core_probe.note
                    if current_core_probe is not None
                    else "no core probe result"
                )
            else:
                core_found = False
                core_active = None
                active_names = [
                    planet_name
                    for planet_name, result in core_scan_results.items()
                    if result.active is True
                ]
                core_note = (
                    "all confirmed Core mappings scanned; active="
                    + (", ".join(active_names) if active_names else "none")
                )

            # v0.47d: derive Unidentified Satellite progression from the
            # DECOMPRESSED save during the existing save-processing pass.
            # Nothing is added to GUI startup/table refresh.
            us_state = str(
                entry.get("unidentified_satellite_state", "Locked")
            )

            try:
                us_file_bytes = archived.destination.read_bytes()

                try:
                    us_bytes = zlib.decompress(us_file_bytes[16:])
                except Exception:
                    us_bytes = None
                    for _sig in (b"\x78\x01", b"\x78\x9c", b"\x78\xda"):
                        _pos = us_file_bytes.find(_sig)
                        while _pos >= 0:
                            try:
                                us_bytes = zlib.decompress(
                                    us_file_bytes[_pos:]
                                )
                                break
                            except Exception:
                                _pos = us_file_bytes.find(_sig, _pos + 1)
                        if us_bytes is not None:
                            break

                if us_bytes is not None:
                    # Confirmed by first-US-visit PRE/POST pair.
                    us_station_active = (
                        b"GateStationActivated" in us_bytes
                    )

                    if not us_station_active:
                        us_state = "Locked"
                    else:
                        # v1.15: Success is persistent once established.
                        prior_us_state = str(
                            entry.get(
                                "unidentified_satellite_state",
                                "Locked",
                            )
                        )
                        us_state = (
                            "Success"
                            if prior_us_state == "Success"
                            else "Active"
                        )

                        all_confirmed_cores_active = all(
                            bool(core_progress.get(p, False))
                            for p in PLANETS
                        )

                        # Count only actual numbered live GatewayKey actors,
                        # not class/schema names. Extra triptychs may remain
                        # in a player's possession or museum display.
                        _key_re = re.compile(
                            rb"GatewayKey_(?:Terran|TerranMoon|Arid|Exotic|"
                            rb"ExoticMoon|Tundra|Radiated)_C_[0-9]+"
                        )
                        live_gateway_keys = set(
                            _key_re.findall(us_bytes)
                        )
                        current_gateway_key_count = len(
                            live_gateway_keys
                        )

                        previous_gateway_key_count = entry.get(
                            "gateway_key_count"
                        )
                        try:
                            previous_gateway_key_count = (
                                int(previous_gateway_key_count)
                                if previous_gateway_key_count is not None
                                else None
                            )
                        except Exception:
                            previous_gateway_key_count = None

                        # Controlled completion sequence:
                        # 12 -> 5 with five extra museum triptychs retained.
                        # Normal players may produce 7 -> 0. The invariant is
                        # that the seven required triptychs disappear between
                        # consecutive saves after all seven cores are active.
                        if (
                            us_state != "Success"
                            and all_confirmed_cores_active
                            and previous_gateway_key_count is not None
                            and (
                                previous_gateway_key_count
                                - current_gateway_key_count
                            ) == 7
                        ):
                            us_state = "Success"

                        # Store the current count for the next consecutive save.
                        entry["gateway_key_count"] = (
                            current_gateway_key_count
                        )

            except Exception:
                # A probe error must never erase a previously established
                # state or interfere with normal tracker processing.
                pass

            entry["unidentified_satellite_state"] = us_state

            # v0.76: Sun Room availability is explicitly stored as a Core
            # state. Confirmed by the supplied PRE/POST pair:
            # ChronosSunRoomFound is absent before availability and present
            # immediately once the Sun Room becomes available to land on.
            sun_room_state = str(
                entry.get("sun_room_state", "Locked")
            )
            try:
                if us_bytes is not None:
                    if (
                        b"ChronosDatalogFinal" in us_bytes
                        or b"Chronos_MissionData_Chronos013_Objective1" in us_bytes
                        or b"Chronos_MissionData_Chronos013_Objective2" in us_bytes
                    ):
                        sun_room_state = "Success"
                    elif b"ChronosSunRoomFound" in us_bytes:
                        sun_room_state = "Unlocked"
                    else:
                        sun_room_state = "Locked"
            except Exception:
                # Never erase a previously known state because of a probe error.
                pass
            entry["sun_room_state"] = sun_room_state

            # v0.85: Xenobiology Lab wreck presence.
            #
            # Controlled save comparison showed the instantiated lab wreck uses
            # the specific Wreck_SnailMissionHub_Base class/name signature.
            # Once seen, persist the state so the Feature cell remains green.
            xeno_lab_present = bool(entry.get("xeno_lab_present", False))
            try:
                if us_bytes is not None and b"Wreck_SnailMissionHub_Base" in us_bytes:
                    xeno_lab_present = True
            except Exception:
                pass
            entry["xeno_lab_present"] = xeno_lab_present

            eva_acquired = bool(entry.get("eva_acquired", False))
            try:
                if us_bytes is not None and b"TerrariumFox_Eva_C" in us_bytes:
                    eva_acquired = True
            except Exception:
                pass
            entry["eva_acquired"] = eva_acquired

            # v0.94: durable M.A.T. completion markers.
            #
            # Later completed saves can remove the transient Mission A/B
            # class/instance strings entirely. Vehicle4 and Vehicle10 remain.
            #
            # Desolo complete:
            #   Vehicle4 present AND Mission A lineage absent.
            #
            # Vesania complete:
            #   Vehicle10 present AND Mission B lineage absent.
            desolo_mat_complete = bool(
                entry.get("desolo_mat_complete", False)
            )
            vesania_mat_complete = bool(
                entry.get("vesania_mat_complete", False)
            )

            try:
                if us_bytes is not None:
                    if (
                        b"Vehicle4" in us_bytes
                        and b"PuzzleCommTower_Request_MissionA" not in us_bytes
                    ):
                        desolo_mat_complete = True

                    if (
                        b"Vehicle10" in us_bytes
                        and b"PuzzleCommTower_Request_MissionB" not in us_bytes
                    ):
                        vesania_mat_complete = True
            except Exception:
                pass

            entry["desolo_mat_complete"] = desolo_mat_complete
            entry["vesania_mat_complete"] = vesania_mat_complete

            # v1.01: DLS printed/built state.
            # The controlled pre/post print pair shows the completed DLS save
            # contains both REP_MegastructureStage and a live BP_MS_Wreck_C_
            # actor, while the placed-but-unprinted save contains neither.
            # DLS is unique, so its MegaTech count is 0 or 1.
            dls_printed = bool(entry.get("dls_printed", False))
            try:
                if us_bytes is not None:
                    if (
                        b"REP_MegastructureStage" in us_bytes
                        and b"BP_MS_Wreck_C_" in us_bytes
                    ):
                        dls_printed = True
            except Exception:
                pass

            entry["dls_printed"] = dls_printed

            megatech_counts = entry.setdefault("megatech_counts", {})
            if not isinstance(megatech_counts, dict):
                megatech_counts = {}
                entry["megatech_counts"] = megatech_counts

            # DLS can only exist once.
            megatech_counts["DLS"] = 1 if dls_printed else 0

            # v1.02: printed Intermodal Platforms.
            #
            # The controlled Sylva pre/post pair identifies the completed
            # Intermodal structure as the Logistics Complex. A printed
            # structure creates a live BP_LogisticsComplex_C_<id> actor.
            intermodal_count = 0
            try:
                if us_bytes is not None:
                    intermodal_ids = set(
                        re.findall(
                            rb"BP_LogisticsComplex_C_(\d+)",
                            us_bytes,
                        )
                    )
                    intermodal_count = len(intermodal_ids)
            except Exception:
                intermodal_count = 0

            try:
                previous_intermodal = int(
                    megatech_counts.get("Intermodal Platform", 0)
                )
            except Exception:
                previous_intermodal = 0

            megatech_counts["Intermodal Platform"] = max(
                previous_intermodal,
                intermodal_count,
            )

            # v1.03: printed Biodomes.
            #
            # Controlled Sylva pre/post Stage-1 pair:
            #   pre  -> no live BP_MS_Biodome_C_<id> actor
            #   post -> one live BP_MS_Biodome_C_<id> actor
            #
            # Count unique live Biodome actors. Persist the highest count ever
            # seen so unloaded/streamed regions cannot reduce tracker progress.
            biodome_count = 0
            try:
                if us_bytes is not None:
                    biodome_ids = set(
                        re.findall(
                            rb"BP_MS_Biodome_C_(\d+)",
                            us_bytes,
                        )
                    )
                    biodome_count = len(biodome_ids)
            except Exception:
                biodome_count = 0

            # v1.05: Biodome represents CURRENT physical structures, not
            # historical maximum progress. Destroying a Biodome removes its live
            # BP_MS_Biodome_C_<id> actor, so the count is allowed to decrease.
            megatech_counts["Biodome"] = biodome_count

            # Preserve Stage 1 confirmation separately from count. This does
            # not increment the number of Biodomes.
            biodome_stage_by_actor = entry.setdefault(
                "biodome_stage_by_actor",
                {},
            )
            if not isinstance(biodome_stage_by_actor, dict):
                biodome_stage_by_actor = {}
                entry["biodome_stage_by_actor"] = biodome_stage_by_actor

            try:
                if us_bytes is not None:
                    live_biodome_ids = {
                        _bid.decode("ascii", errors="ignore")
                        for _bid in set(
                            re.findall(
                                rb"BP_MS_Biodome_C_(\d+)",
                                us_bytes,
                            )
                        )
                    }

                    # v1.10: MegaTech is current-state reporting.
                    # Remove stage history for Biodomes that no longer exist.
                    biodome_stage_by_actor = {
                        str(k): int(v)
                        for k, v in biodome_stage_by_actor.items()
                        if str(k) in live_biodome_ids
                    }
                    entry["biodome_stage_by_actor"] = biodome_stage_by_actor

                    # v1.13: Biodome stage progression confirmed from
                    # controlled S1 -> S2 -> S3 saves.
                    biodome_stage = 0
                    if live_biodome_ids:
                        biodome_stage = 1
                    if b"Megatech_Biodome002_1" in us_bytes:
                        biodome_stage = max(biodome_stage, 2)
                    if b"Megatech_Biodome003_1" in us_bytes:
                        biodome_stage = max(biodome_stage, 3)

                    for _key in live_biodome_ids:
                        biodome_stage_by_actor[_key] = biodome_stage
            except Exception:
                pass

            # v1.06: launched Orbital Platforms.
            orbital_platform_probe = probe_orbital_platforms(
                archived.destination
            )
            if orbital_platform_probe.error is None:
                megatech_counts["Orbital Platform"] = (
                    orbital_platform_probe.count
                )
                entry["orbital_platform_actor_ids"] = list(
                    orbital_platform_probe.actor_ids
                )
                entry["orbital_platform_orbiting_planets"] = list(
                    orbital_platform_probe.orbiting_planets
                )
                entry["orbital_platform_stage_by_actor"] = dict(
                    orbital_platform_probe.stages_by_actor
                )
            else:
                # Never erase a previously readable state because of a probe
                # failure on one save.
                megatech_counts.setdefault("Orbital Platform", 0)
                entry.setdefault("orbital_platform_actor_ids", [])
                entry.setdefault("orbital_platform_orbiting_planets", [])
                entry.setdefault("orbital_platform_stage_by_actor", {})

            # v1.12: DLS location + Museum current state.
            megatech_actor_probe = probe_megatech_actors(
                archived.destination
            )
            if megatech_actor_probe.error is None:
                entry["dls_locations"] = list(
                    megatech_actor_probe.dls_locations
                )
                entry["biodome_locations"] = list(
                    megatech_actor_probe.biodome_locations
                )

                museum_count = len(
                    megatech_actor_probe.museum_actor_ids
                )
                megatech_counts["Museum"] = museum_count
                entry["museum_actor_ids"] = list(
                    megatech_actor_probe.museum_actor_ids
                )
                entry["museum_locations"] = list(
                    megatech_actor_probe.museum_locations
                )
                entry["museum_stage_by_actor"] = dict(
                    megatech_actor_probe.museum_stage_by_actor
                )
            else:
                entry.setdefault("dls_locations", [])
                entry.setdefault("biodome_locations", [])
                megatech_counts.setdefault("Museum", 0)
                entry.setdefault("museum_actor_ids", [])
                entry.setdefault("museum_locations", [])
                entry.setdefault("museum_stage_by_actor", {})

            galastropod_probe = probe_galastropods(
                archived.destination
            )
            galastropod_progress = entry.setdefault(
                "galastropods_by_planet", {}
            )
            galastropod_ids = entry.setdefault(
                "galastropod_ids_by_planet", {}
            )

            for _planet in GATEWAY_MAX_BY_PLANET:
                # Once acquired, retain the historical tracker achievement
                # even if a later save does not serialize the actor in a
                # currently loaded region.
                if galastropod_probe.present_by_planet.get(_planet, False):
                    galastropod_progress[_planet] = True
                    galastropod_ids[_planet] = (
                        galastropod_probe.ids_by_planet.get(_planet, [])
                    )
                else:
                    galastropod_progress.setdefault(_planet, False)

            self._append_gateway_core_trace(
                save_name=current.display_name,
                location=location,
                gateway_total=gateway_probe.total,
                previous_total=self._last_gateway_previous,
                delta=self._last_gateway_delta,
                assigned_planet=assigned_gateway_planet,
                planet_gateway_count=(
                    int(gateway_progress.get(assigned_gateway_planet, 0))
                    if assigned_gateway_planet else None
                ),
                core_planet=core_planet,
                core_found=core_found,
                core_active=core_active,
                core_note=core_note,
                note=gateway_note,
            )

            # Capture exact visit-transition state for diagnostics.
            visits_before_map = self.location_state.visits_for(current.display_name)
            self._last_visit_previous = self.location_state.current_location(
                current.display_name
            )
            self._last_visit_before = int(visits_before_map.get(location, 0))

            visit_changed, visit_after = self.location_state.update_location(
                current.display_name,
                location,
            )
            self._last_visit_changed = visit_changed
            self._last_visit_after = int(visit_after)

            # Exact destination-based PowerShell interval flush.
            self.timing.trace_external(
                "GUI CALLING TIMING SAVE IDENTIFICATION",
                (
                    "GUI is about to call PowerShellTimingModel.on_save_identified(). "
                    "Visit tracking has already run; timer arithmetic has not yet run "
                    "for this save event."
                ),
                focus_save=current.display_name,
                details=[
                    f"Save={current.display_name}",
                    f"Final detected location={location}",
                    f"Tracker record existed before processing="
                    f"{tracked_before_processing}",
                ],
            )

            self.timing.on_save_identified(
                current.display_name,
                location,
                tracked_before_processing=tracked_before_processing,
            )

            self.timing.trace_external(
                "GUI RETURNED FROM TIMING SAVE IDENTIFICATION",
                (
                    "Timing save-identification arithmetic is complete. "
                    "Next steps are selection, death detection, diagnostics, and persistence."
                ),
                focus_save=current.display_name,
            )

            # v0.84: auto-select the live save only on a real identity edge.
            # Normal saves/refreshes must not keep pulling the right-side list
            # back to this row while the user is scrolling.
            self._auto_select_live_save(current.display_name)

            # Hybrid death probe: explicit live log events count immediately;
            # new player corpse IDs provide a save-time fallback.
            death_probe = self.deaths.observe_save(
                current.display_name,
                archived.destination,
                location,
            )
            self._last_death_detected = death_probe.death_detected
            self._last_backpack_signature = death_probe.backpack_signature
            self._last_corpse_count = death_probe.corpse_discovery_count
            self._last_backpack_rail_ids = death_probe.backpack_rail_ids
            self._last_new_backpack_rail_ids = death_probe.new_backpack_rail_ids
            self._last_removed_backpack_rail_ids = death_probe.removed_backpack_rail_ids
            self._last_new_death_tokens = death_probe.new_evidence_tokens
            self._last_removed_death_tokens = death_probe.removed_evidence_tokens
            self._last_respawn_snapshot_change_count = death_probe.respawn_snapshot_change_count
            self._last_respawn_snapshot_all_changed = death_probe.respawn_snapshot_all_changed
            self._last_respawn_snapshot_changed_fields = death_probe.respawn_snapshot_changed_fields
            self._last_death_probe_status = death_probe.probe_status

            # Save-content fingerprint used to distinguish a real rename from
            # delete + unrelated new save.
            rename_fp = get_rename_fingerprint(archived.destination)
            if rename_fp.signature:
                entry["_rename_world_signature"] = rename_fp.signature

            # Freeze the exact save-time diagnostic so the user can copy it
            # even while live timing continues to refresh elsewhere.
            x_text = f"{xyz[0]:,.6f}" if xyz is not None else "—"
            y_text = f"{xyz[1]:,.6f}" if xyz is not None else "—"
            z_text = f"{xyz[2]:,.6f}" if xyz is not None else "—"

            self._last_captured_diagnostic = (
                f"Save:                    {current.display_name}\n"
                f"Detected Location:       {location}\n"
                f"Player X:                {x_text}\n"
                f"Player Y:                {y_text}\n"
                f"Player Z:                {z_text}\n"
                f"Nearest Planet Center:   {self._last_nearest_planet or '—'}\n"
                f"Center Distance:         "
                f"{self._last_nearest_distance:,.2f}\n"
                if self._last_nearest_distance is not None
                else
                f"Save:                    {current.display_name}\n"
                f"Detected Location:       {location}\n"
                f"Player X:                {x_text}\n"
                f"Player Y:                {y_text}\n"
                f"Player Z:                {z_text}\n"
                f"Nearest Planet Center:   {self._last_nearest_planet or '—'}\n"
                f"Center Distance:         —\n"
            )

            self._last_captured_diagnostic += (
                f"Orbital References:      "
                f"{self._last_orbital_refs if self._last_orbital_refs is not None else '—'}\n"
                f"LandingPad Markers:      "
                f"{self._last_landing_markers if self._last_landing_markers is not None else '—'}\n"
                f"Satellite Baseline:      "
                f"{self._last_satellite_baseline if self._last_satellite_baseline is not None else '—'}\n"
                f"ControlRoomMesh Count:   "
                f"{self._last_sun_room_mesh if self._last_sun_room_mesh is not None else '—'}\n"
                f"Previous Stored Loc:     {self._last_visit_previous or '—'}\n"
                f"Visit Count Before:      "
                f"{self._last_visit_before if self._last_visit_before is not None else '—'}\n"
                f"Visit Transition:        "
                f"{'CHANGED' if self._last_visit_changed else 'same location'}\n"
                f"Visit Count After:       "
                f"{self._last_visit_after if self._last_visit_after is not None else '—'}\n"
                f"Gateway Object Total:    "
                f"{self._last_gateway_total if self._last_gateway_total is not None else '—'}\n"
                f"Previous Gateway Total:  "
                f"{self._last_gateway_previous if self._last_gateway_previous is not None else '—'}\n"
                f"Gateway Delta:           "
                f"{self._last_gateway_delta if self._last_gateway_delta is not None else '—'}\n"
                f"Gateway Probe Status:    "
                f"{('NEW GATEWAY OBJECT(S)' if self._last_gateway_delta is not None and self._last_gateway_delta > 0 else 'no increase' if self._last_gateway_delta == 0 else 'baseline')}\n"
                f"Core Probe Planet:       {core_planet or '—'}\n"
                f"Core Engine Found:       {'YES' if core_found else 'No'}\n"
                f"Core Active:             {'YES' if core_active is True else 'No' if core_active is False else '—'}\n"
                f"Core Probe Note:         {core_note}\n"
                f"Confirmed Active Cores:  "
                f"{', '.join(p for p, r in core_scan_results.items() if r.active is True) or 'none'}\n"
                f"Galastropods Present:    "
                f"{', '.join(p for p in GATEWAY_MAX_BY_PLANET if galastropod_probe.present_by_planet.get(p, False)) or 'none'}\n"
                f"Backpack Signature:      "
                f"{self._last_backpack_signature or '—'}\n"
                f"Corpse Discovery Count:  "
                f"{self._last_corpse_count if self._last_corpse_count is not None else '—'}\n"
                f"BackpackRail IDs:        "
                f"{', '.join(str(x) for x in self._last_backpack_rail_ids) if self._last_backpack_rail_ids else 'none'}\n"
                f"New BackpackRail IDs:    "
                f"{', '.join(str(x) for x in self._last_new_backpack_rail_ids) if self._last_new_backpack_rail_ids else 'none'}\n"
                f"Removed BackpackRail IDs:"
                f" {', '.join(str(x) for x in self._last_removed_backpack_rail_ids) if self._last_removed_backpack_rail_ids else 'none'}\n"
                f"New Death-Evidence Tokens: "
                f"{' | '.join(self._last_new_death_tokens[:12]) if self._last_new_death_tokens else 'none'}\n"
                f"Removed Death-Evidence Tokens: "
                f"{' | '.join(self._last_removed_death_tokens[:12]) if self._last_removed_death_tokens else 'none'}\n"
                f"Death Probe Status:      "
                f"{self._last_death_probe_status}\n"
                f"Live Death Watch:        "
                f"{self._last_live_death_status}\n"
                f"Respawn Snapshots:       "
                f"{self._last_respawn_snapshot_change_count}/11 changed\n"
                f"All 11 Respawn Changed:  "
                f"{'YES' if self._last_respawn_snapshot_all_changed else 'No'}\n"
                f"Death Change:            "
                f"{'YES' if self._last_death_detected else 'No'}"
            )

            if self._last_player_candidate_lines:
                self._last_captured_diagnostic += (
                    "\n\nPLAYER POSITION CANDIDATES\n"
                    "--------------------------\n"
                    + "\n".join(self._last_player_candidate_lines)
                )

            self._set_text(
                self.capture_text,
                self._last_captured_diagnostic,
            )

            self.timing.trace_external(
                "SAVE EVENT — BEFORE TRACKER PERSISTENCE",
                (
                    "Save event processing is complete. Persist all tracker data. "
                    "No timer arithmetic is intentionally applied by this write."
                ),
                focus_save=current.display_name,
            )
            self.storage.save(self.data)
            self.timing.trace_external(
                "SAVE EVENT — AFTER TRACKER PERSISTENCE",
                "Tracker persistence completed.",
                focus_save=current.display_name,
            )
            self._refresh_save_list()
            self._last_save_flush = time.monotonic()

        self._pending_logical_name = None

    def _refresh(self) -> None:
        now = time.monotonic()
        delta = max(0.0, min(now - self._last_tick, 5.0))
        self._last_tick = now

        saves = find_savegames(self.save_directory)
        running = is_astroneer_running()

        # Rename migration must happen before the right-side browser's gone
        # retirement pass. A proven rename is the same tracker identity.
        self._detect_and_migrate_rename(saves)

        if not self._detector_primed:
            self.detector.prime(saves)
            self._detector_primed = True

        # Startup timing edge.
        #
        # If PLAY NOW already armed the startup timer, do NOT reset it when the
        # Astroneer process finally appears. Otherwise, if the tracker discovers
        # Astroneer already running, arm the timing model at that discovery edge.
        if running and not self._game_was_running:
            if not self._startup_timer_armed:
                self.timing.game_started()
                self._startup_timer_armed = True
                self.timing.trace_external(
                    "ASTRONEER PROCESS DISCOVERED — STARTUP TIMER ARMED",
                    (
                        "Tracker detected Astroneer already running. Pending Startup "
                        "begins from this detection edge."
                    ),
                )
            else:
                self.timing.trace_external(
                    "ASTRONEER PROCESS DISCOVERED — EXISTING STARTUP TIMER PRESERVED",
                    (
                        "PLAY NOW had already armed Pending Startup. Do not reset "
                        "Pending Startup when Astroneer becomes visible."
                    ),
                )
            self.deaths.reset_session()
            self.live_death_monitor.reset_session()

        # Count startup time from either explicit PLAY NOW or actual process
        # detection. Once a save is identified, the normal active-save tick path
        # continues while Astroneer is running.
        timing_running = running or (
            self._startup_timer_armed
            and self.timing.state.active_save is None
        )
        self.timing.tick(timing_running, delta)

        if self._detector_primed:
            self.detector.update(saves)

        active = self.detector.state.active_save
        detected_change = self.detector.state.last_change_detected_at

        if (
            running
            and active is not None
            and detected_change is not None
            and detected_change != self._last_change_seen
        ):
            self._last_change_seen = detected_change
            self._pending_logical_name = active.display_name

        if running:
            active_name_for_live = (
                self.timing.state.active_save
                or (active.display_name if active is not None else None)
            )
            self.live_death_monitor.set_context(active_name_for_live, self._last_detected_location)
            live_events = self.live_death_monitor.poll()
            self._last_live_death_status = self.live_death_monitor.last_candidate
            live_counted = False
            for event in live_events:
                if event.counted and active_name_for_live:
                    self.deaths.record_live_death(
                        active_name_for_live, self._last_detected_location,
                        event.line, event.timestamp,
                    )
                    self._last_live_death_counted_line = event.line
                    live_counted = True
            if live_counted:
                self._last_death_detected = True
                self.storage.save(self.data)
            self._process_changed_save(saves)

        # Process exit edge.
        if self._game_was_running and not running:
            self.timing.trace_external(
                "GAME EXIT — BEFORE FINAL PERSISTENCE",
                (
                    "Astroneer process stopped. Persist tracker data before "
                    "resetting live timing state."
                ),
                focus_save=self.timing.state.active_save,
            )
            self.storage.save(self.data)
            self.timing.game_stopped()
            self.deaths.reset_session()
            self.live_death_monitor.reset_session()
            self.detector.reset_active_session()
            self._pending_logical_name = None
            self._last_detected_location = None
            self._last_xyz = None
            self._startup_timer_armed = False

        self._game_was_running = running

        # Periodic persistence for total time. Per-location time only changes on save.
        if running and now - self._last_save_flush >= 5.0:
            self.timing.trace_external(
                "PERIODIC TRACKER PERSISTENCE",
                (
                    "Write current tracker data to disk. No timer values are "
                    "intentionally changed by persistence itself."
                ),
                focus_save=self.timing.state.active_save,
            )
            self.storage.save(self.data)
            self._last_save_flush = now

        self._refresh_save_list()
        self._update_ui(running, active)
        self.root.after(1000, self._refresh)

    def _update_ui(self, running: bool, active: SaveInfo | None) -> None:
        state = self.timing.state

        if not running:
            self.playing_label.configure(
                text="Astroneer not running",
                fg="#b00020",
            )
        elif state.active_save:
            self.playing_label.configure(
                text=f"Playing: {state.active_save}",
                fg="#17823b",
            )
        else:
            self.playing_label.configure(
                text="Playing: Waiting for save identification...",
                fg="#b00020",
            )

        live_name = state.active_save
        view_name = self._view_save_name()
        total = self.timing.total_seconds(view_name) if view_name else 0.0

        tracked_entry = self.data.get("saves", {}).get(view_name) if view_name else None
        record_status = "Tracked" if isinstance(tracked_entry, dict) else "Save found — no tracker data yet"

        # Startup timing exists before any logical save is identified, so it
        # must not depend on the right-side selected save for visibility.
        startup_waiting = (
            self._startup_timer_armed
            and state.active_save is None
        )

        if startup_waiting:
            session_display = self._fmt(state.session)
            pending_startup_display = self._fmt(state.pending)
            pending_location_display = self._fmt(state.pending_location_time)
            timing_mode_display = "STARTUP — waiting for save identification"
        else:
            session_display = (
                self._fmt(state.session)
                if live_name == view_name
                else '—'
            )
            pending_startup_display = (
                self._fmt(state.pending)
                if live_name == view_name
                else '—'
            )
            pending_location_display = (
                self._fmt(state.pending_location_time)
                if live_name == view_name
                else '—'
            )
            timing_mode_display = (
                "ACTIVE SAVE"
                if state.active_save
                else "IDLE"
            )

        timing_lines = [
            f"Viewing Save:            {view_name or '—'}",
            f"Record Status:           {record_status}",
            f"Live Active Save:        {live_name or '—'}",
            f"Timing State:            {timing_mode_display}",
            f"Persistent Total Time:   {self._fmt(total)}",
            f"Current Session Time:    {session_display}",
            f"Pending Startup Time:    {pending_startup_display}",
            f"Pending Location Time:   {pending_location_display}",
            f"Startup Timer Armed:     {'YES' if self._startup_timer_armed else 'No'}",
            "",
            f"Current Location:        {self.location_state.current_location(view_name) if view_name else '—'}",
            f"Player X:                {self._last_xyz[0]:,.6f}" if live_name == view_name and self._last_xyz is not None else "Player X:                —",
            f"Player Y:                {self._last_xyz[1]:,.6f}" if live_name == view_name and self._last_xyz is not None else "Player Y:                —",
            f"Player Z:                {self._last_xyz[2]:,.6f}" if live_name == view_name and self._last_xyz is not None else "Player Z:                —",
            f"Nearest Planet Center:   {self._last_nearest_planet if live_name == view_name and self._last_nearest_planet else '—'}",
            f"Center Distance:         {self._last_nearest_distance:,.2f}" if live_name == view_name and self._last_nearest_distance is not None else "Center Distance:         —",
            f"Orbital References:      {self._last_orbital_refs if live_name == view_name and self._last_orbital_refs is not None else '—'}",
            f"LandingPad Markers:      {self._last_landing_markers if live_name == view_name and self._last_landing_markers is not None else '—'}",
            f"Satellite Baseline:      {self._last_satellite_baseline if live_name == view_name and self._last_satellite_baseline is not None else '—'}",
            f"ControlRoomMesh Count:   {self._last_sun_room_mesh if live_name == view_name and self._last_sun_room_mesh is not None else '—'}",
            f"Previous Stored Loc:     {self._last_visit_previous if live_name == view_name and self._last_visit_previous else '—'}",
            f"Visit Count Before:      {self._last_visit_before if live_name == view_name and self._last_visit_before is not None else '—'}",
            f"Visit Transition:        {'CHANGED' if live_name == view_name and self._last_visit_changed else 'same location'}",
            f"Visit Count After:       {self._last_visit_after if live_name == view_name and self._last_visit_after is not None else '—'}",
            f"Gateway Object Total:    {self._last_gateway_total if live_name == view_name and self._last_gateway_total is not None else '—'}",
            f"Previous Gateway Total:  {self._last_gateway_previous if live_name == view_name and self._last_gateway_previous is not None else '—'}",
            f"Gateway Delta:           {self._last_gateway_delta if live_name == view_name and self._last_gateway_delta is not None else '—'}",
            f"Backpack Signature:      {self._last_backpack_signature if live_name == view_name and self._last_backpack_signature else '—'}",
            f"Corpse Discovery Count:  {self._last_corpse_count if live_name == view_name and self._last_corpse_count is not None else '—'}",
            f"BackpackRail Count:      {len(self._last_backpack_rail_ids) if live_name == view_name else '—'}",
            f"Death Probe Status:      {self._last_death_probe_status if live_name == view_name else '—'}",
            f"Live Death Watch:        {self._last_live_death_status if live_name == view_name else '—'}",
            f"Respawn Snapshots:       {self._last_respawn_snapshot_change_count}/11 changed" if live_name == view_name else "Respawn Snapshots:       —",
            f"All 11 Respawn Changed:  {'YES' if live_name == view_name and self._last_respawn_snapshot_all_changed else 'No'}",
            f"Last Death Change:       {'YES' if live_name == view_name and self._last_death_detected else 'No'}",
        ]

        if not view_name and running:
            timing_lines.append(
                "Before identification, startup time is buffered rather than lost."
            )

        self._set_text(self.timing_text, "\n".join(timing_lines))

        visits = (
            self.location_state.visits_for(view_name)
            if view_name else {}
        )

        selected_entry = (
            self.data.get("saves", {}).get(view_name, {})
            if view_name else {}
        )
        gateway_progress = (
            selected_entry.get("gateway_progress_by_planet", {})
            if isinstance(selected_entry, dict) else {}
        )
        gateway_progress_source = (
            str(selected_entry.get("gateway_progress_source", "legacy"))
            if isinstance(selected_entry, dict)
            else "legacy"
        )
        core_progress = (
            selected_entry.get("core_progress_by_planet", {})
            if isinstance(selected_entry, dict) else {}
        )
        galastropod_progress = (
            selected_entry.get("galastropods_by_planet", {})
            if isinstance(selected_entry, dict) else {}
        )
        xeno_lab_present = (
            bool(selected_entry.get("xeno_lab_present", False))
            if isinstance(selected_entry, dict)
            else False
        )
        eva_acquired = (
            bool(selected_entry.get("eva_acquired", False))
            if isinstance(selected_entry, dict)
            else False
        )
        desolo_mat_complete = (
            bool(selected_entry.get("desolo_mat_complete", False))
            if isinstance(selected_entry, dict)
            else False
        )
        vesania_mat_complete = (
            bool(selected_entry.get("vesania_mat_complete", False))
            if isinstance(selected_entry, dict)
            else False
        )
        unidentified_satellite_state = (
            str(selected_entry.get("unidentified_satellite_state", "Locked"))
            if isinstance(selected_entry, dict)
            else "Locked"
        )
        if unidentified_satellite_state not in ("Locked", "Active", "Success"):
            unidentified_satellite_state = "Locked"

        sun_room_state = (
            str(selected_entry.get("sun_room_state", "Locked"))
            if isinstance(selected_entry, dict)
            else "Locked"
        )
        if sun_room_state not in ("Locked", "Unlocked", "Success"):
            sun_room_state = "Locked"

        megatech_counts_display = (
            selected_entry.get("megatech_counts", {})
            if isinstance(selected_entry, dict)
            else {}
        )

        biodome_stage_map = (
            selected_entry.get("biodome_stage_by_actor", {})
            if isinstance(selected_entry, dict)
            else {}
        )
        if not isinstance(biodome_stage_map, dict):
            biodome_stage_map = {}

        try:
            highest_biodome_stage = max(
                [int(v) for v in biodome_stage_map.values()] or [0]
            )
        except Exception:
            highest_biodome_stage = 0

        museum_stage_map = (
            selected_entry.get("museum_stage_by_actor", {})
            if isinstance(selected_entry, dict)
            else {}
        )
        if not isinstance(museum_stage_map, dict):
            museum_stage_map = {}
        try:
            highest_museum_stage = max(
                [int(v) for v in museum_stage_map.values()] or [0]
            )
        except Exception:
            highest_museum_stage = 0

        orbital_stage_map = (
            selected_entry.get("orbital_platform_stage_by_actor", {})
            if isinstance(selected_entry, dict)
            else {}
        )
        if not isinstance(orbital_stage_map, dict):
            orbital_stage_map = {}
        try:
            highest_orbital_stage = max(
                [int(v) for v in orbital_stage_map.values()] or [0]
            )
        except Exception:
            highest_orbital_stage = 0
        if not isinstance(megatech_counts_display, dict):
            megatech_counts_display = {}
        try:
            orbital_platform_count = max(
                0,
                int(megatech_counts_display.get("Orbital Platform", 0)),
            )
        except Exception:
            orbital_platform_count = 0

        orbital_platform_planets = (
            selected_entry.get("orbital_platform_orbiting_planets", [])
            if isinstance(selected_entry, dict)
            else []
        )
        if not isinstance(orbital_platform_planets, list):
            orbital_platform_planets = []
        orbital_platform_planets = [
            str(p) for p in orbital_platform_planets if str(p)
        ]

        # Hide special destinations until they are actually available.
        visible_locations = list(PLANETS)
        if orbital_platform_count > 0:
            visible_locations.append("Orbital Platform")
        if unidentified_satellite_state in ("Active", "Success"):
            visible_locations.append("Unidentified Satellite")
        if sun_room_state in ("Unlocked", "Success"):
            visible_locations.append("Sun Room")

        # v1.11: one authoritative fixed-width layout for Gameplay Totals.
        # Location is wide enough for "Orbital Platform (Desolo)".
        loc_w = 27
        visits_w = 8
        time_w = 12
        days_w = 12
        died_w = 8
        gateway_w = 10
        core_w = 10
        snail_w = 14
        feature_w = 12

        lines = [
            (
                f"{'Location':<{loc_w}} {'Visits':>{visits_w}} "
                f"{'Time (hh:mm)':>{time_w}} {'Planet Days':>{days_w}} "
                f"{'Died':>{died_w}} {'Gateway':>{gateway_w}} "
                f"{'Core':>{core_w}} {'Galastropod':>{snail_w}} "
                f"{'Feature':>{feature_w}}"
            ),
            (
                f"{'-'*loc_w} {'-'*visits_w} {'-'*time_w} "
                f"{'-'*days_w} {'-'*died_w} {'-'*gateway_w} "
                f"{'-'*core_w} {'-'*snail_w} {'-'*feature_w}"
            ),
        ]

        for planet in visible_locations:
            seconds = (
                self.timing.location_seconds(view_name, planet)
                if view_name else 0.0
            )

            if planet in PLANET_DAY_SECONDS:
                day_text = f"{seconds / PLANET_DAY_SECONDS[planet]:.1f}"
            else:
                day_text = "-"

            if planet in GATEWAY_MAX_BY_PLANET:
                gateway_text = (
                    f"{int(gateway_progress.get(planet, 0))}/"
                    f"{GATEWAY_MAX_BY_PLANET[planet]}"
                )
                core_text = (
                    "Active"
                    if bool(core_progress.get(planet, False))
                    else "Locked"
                )
                galastropod_text = (
                    GALASTROPOD_NAME_BY_PLANET.get(planet, "Yes")
                    if bool(galastropod_progress.get(planet, False))
                    else "-"
                )
                if planet == "Sylva":
                    feature_text = "Xeno Lab"
                elif planet in ("Desolo", "Vesania"):
                    feature_text = "M.A.T. ⓘ"
                else:
                    feature_text = ""
            else:
                gateway_text = "-"
                core_text = (
                    unidentified_satellite_state
                    if planet == "Unidentified Satellite"
                    else sun_room_state
                    if planet == "Sun Room"
                    else "-"
                )
                galastropod_text = (
                    "EVA"
                    if planet == "Sun Room" and eva_acquired
                    else "-"
                )
                feature_text = ""

            display_location = planet
            if planet == "Orbital Platform" and orbital_platform_planets:
                display_location = (
                    "Orbital Platform "
                    f"({', '.join(orbital_platform_planets)})"
                )

            lines.append(
                f"{display_location:<{loc_w}} "
                f"{visits.get(planet, 0):>{visits_w}} "
                f"{self._fmt_table_time(seconds):>{time_w}} "
                f"{day_text:>{days_w}} "
                f"{self.deaths.deaths_at(view_name, planet) if view_name else 0:>{died_w}} "
                f"{gateway_text:>{gateway_w}} "
                f"{core_text:>{core_w}} "
                f"{galastropod_text:>{snail_w}} "
                f"{feature_text:>{feature_w}}"
            )

        lines.append("")
        total_visits = sum(visits.get(p, 0) for p in TRACKED_LOCATIONS)
        total_deaths = self.deaths.deaths_for(view_name) if view_name else 0
        earth_days = total / 86400.0 if total > 0 else 0.0

        lines.append(f"Total Planet Visits: {total_visits}")
        total_gateways = sum(
            int(gateway_progress.get(p, 0))
            for p in GATEWAY_MAX_BY_PLANET
        )
        total_cores = sum(
            1 for p in GATEWAY_MAX_BY_PLANET
            if bool(core_progress.get(p, False))
        )
        total_galastropods = sum(
            1 for p in GATEWAY_MAX_BY_PLANET
            if bool(galastropod_progress.get(p, False))
        )

        lines.append(f"Total Deaths: {total_deaths}")
        lines.append(f"Total Gateways Activated: {total_gateways} / 34")
        lines.append(f"Cores Activated: {total_cores} / 7")
        lines.append(f"Earth Time play: {self._fmt(total)}")
        lines.append(f"Earth Days play: {earth_days:.2f}")

        self._xeno_lab_present_for_render = xeno_lab_present
        self._desolo_mat_complete_for_render = desolo_mat_complete
        self._vesania_mat_complete_for_render = vesania_mat_complete
        self._render_gameplay_table(lines)
        self._update_feature_overlay(
            view_name,
            visits,
            gateway_progress,
            core_progress,
            galastropod_progress,
            total_deaths,
            unidentified_satellite_state,
            sun_room_state,
        )
        self._update_selected_location_details()

    def run(self) -> None:
        self.root.mainloop()
