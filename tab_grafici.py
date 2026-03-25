# -*- coding: utf-8 -*-
"""
tab_grafici.py  —  GraficiMixin
Contiene _build_grafici_tab e tutti i metodi _grafici_* per la Tab Grafici.
Importato come mixin da LogAnalyzerApp in app_main.py.
"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from colors import COLORS
from pdf_export import (
    generate_lamborghini_pdf,
    _autodetect_profile,
    _validate_csv,
    PROFILES,
    PRESSASTAMPI,
)


class GraficiMixin:
    """Mixin con tutta la logica della tab 'Grafici'."""

    # ------------------------------------------------------------------
    # BUILD TAB
    # ------------------------------------------------------------------
    def _build_grafici_tab(self, parent):
        # stato interno
        self._gr_pressa_var  = tk.StringVar(value=list(PRESSASTAMPI.keys())[0])
        self._gr_stampo_var  = tk.StringVar()
        self._gr_csv_path    = None
        self._gr_profile_key = None
        self._gr_fig         = None
        self._gr_canvas_widget = None

        # ---- toolbar ----
        tb = ctk.CTkFrame(parent, fg_color=COLORS["surface"],
                          corner_radius=8, height=46)
        tb.pack(fill="x", pady=(0, 6))
        tb.pack_propagate(False)

        ctk.CTkLabel(tb, text="Pressa:",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]
                     ).pack(side="left", padx=(12, 4), pady=10)
        self._gr_pressa_menu = ctk.CTkOptionMenu(
            tb, variable=self._gr_pressa_var,
            values=list(PRESSASTAMPI.keys()),
            width=180, height=28,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=self._gr_on_pressa_change)
        self._gr_pressa_menu.pack(side="left", padx=(0, 12), pady=10)

        ctk.CTkLabel(tb, text="Stampo:",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]
                     ).pack(side="left", padx=(0, 4))

        # PRESSASTAMPI è { pressa: [stampo1, stampo2, ...] }  (lista, non dict)
        first_pressa = list(PRESSASTAMPI.keys())[0]
        stampi_init  = PRESSASTAMPI[first_pressa]          # lista
        self._gr_stampo_var.set(stampi_init[0] if stampi_init else "")
        self._gr_stampo_menu = ctk.CTkOptionMenu(
            tb, variable=self._gr_stampo_var,
            values=stampi_init if stampi_init else ["-"],
            width=220, height=28,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=self._gr_on_stampo_change)
        self._gr_stampo_menu.pack(side="left", padx=(0, 16))

        ctk.CTkButton(
            tb, text="Apri CSV", width=90, height=28,
            fg_color=COLORS["accent"], hover_color="#5a52e0",
            text_color=COLORS["text"], font=("Segoe UI", 10),
            command=self._gr_open_csv).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            tb, text="Genera PDF", width=100, height=28,
            fg_color="#7c3aed", hover_color="#6d28d9",
            text_color=COLORS["text"], font=("Segoe UI", 10),
            command=self._gr_export_pdf).pack(side="left", padx=(0, 6))

        self._gr_info_lbl = ctk.CTkLabel(
            tb, text="Nessun file caricato",
            font=("Segoe UI", 9), text_color=COLORS["text2"])
        self._gr_info_lbl.pack(side="left", padx=6)

        # ---- anteprima grafico ----
        preview_frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"],
                                      corner_radius=8)
        preview_frame.pack(fill="both", expand=True)
        self._gr_preview_frame = preview_frame

        ctk.CTkLabel(
            preview_frame,
            text="Seleziona pressa e stampo, poi apri un CSV per vedere l'anteprima.",
            font=("Segoe UI", 13), text_color=COLORS["text2"]
        ).pack(expand=True)

    # ------------------------------------------------------------------
    # CAMBIO PRESSA / STAMPO
    # ------------------------------------------------------------------
    def _gr_on_pressa_change(self, _=None):
        pressa = self._gr_pressa_var.get()
        # PRESSASTAMPI[pressa] è una lista
        stampi = PRESSASTAMPI.get(pressa, [])
        self._gr_stampo_menu.configure(values=stampi if stampi else ["-"])
        if stampi:
            self._gr_stampo_var.set(stampi[0])
        self._gr_update_preview()

    def _gr_on_stampo_change(self, _=None):
        self._gr_update_preview()

    # ------------------------------------------------------------------
    # APRI CSV
    # ------------------------------------------------------------------
    def _gr_open_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not path:
            return
        try:
            self._gr_csv_path = path

            # _autodetect_profile(csv_path) → (stampo_name, profili_dict, partite_list)
            profile_key, _, _ = _autodetect_profile(path)
            if profile_key:
                self._gr_profile_key = profile_key
                # allinea menu pressa/stampo
                for pressa, stampi in PRESSASTAMPI.items():
                    if profile_key in stampi:
                        self._gr_pressa_var.set(pressa)
                        self._gr_stampo_menu.configure(values=stampi)
                        self._gr_stampo_var.set(profile_key)
                        break

            # conta righe per info label
            n_rows = 0
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    n_rows = sum(1 for l in f if l.strip()) - 1
            except Exception:
                pass

            self._gr_info_lbl.configure(
                text=f"{os.path.basename(path)}  |  ~{max(0, n_rows)} record",
                text_color=COLORS["text"])
            self.set_status(
                f"Grafici CSV: {os.path.basename(path)} (~{max(0, n_rows)} record)")
            self._gr_update_preview()
        except Exception as e:
            messagebox.showerror("Errore CSV Grafici", str(e))

    # ------------------------------------------------------------------
    # ANTEPRIMA
    # ------------------------------------------------------------------
    def _gr_update_preview(self):
        if not self._gr_csv_path:
            return
        stampo_key = self._gr_stampo_var.get()
        profile    = PROFILES.get(stampo_key)
        if not profile:
            return

        for w in self._gr_preview_frame.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        try:
            fig = self._gr_build_preview_fig(stampo_key, profile)
            self._gr_fig = fig
            canvas = FigureCanvasTkAgg(fig, master=self._gr_preview_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self._gr_canvas_widget = canvas
        except Exception as e:
            ctk.CTkLabel(
                self._gr_preview_frame,
                text=f"Errore anteprima: {e}",
                font=("Segoe UI", 11), text_color=COLORS.get("error", "#ff4444")
            ).pack(expand=True)

    def _gr_build_preview_fig(self, stampo_key, profile):
        """Legge il CSV e costruisce la figura di anteprima con _pdf_parse_csv."""
        from pdf_export import _pdf_parse_csv
        data, meta = _pdf_parse_csv(self._gr_csv_path)

        palette = ["#6c63ff", "#00d4ff", "#52c41a", "#faad14",
                   "#f44322", "#e91e63", "#9c27b0", "#ff9800"]

        fig, axes = plt.subplots(2, 2, figsize=(11, 5), facecolor="#1a1b2e")
        fig.suptitle(f"{stampo_key}  —  {meta.get('idciclo','')}", 
                     color="#c0c0e0", fontsize=10)

        plot_groups = [
            ("Temperature SUP", [f"TS{i}" for i in range(1, 5)]),
            ("Temperature INF", [f"TI{i}" for i in range(1, 5)]),
            ("Forza / Posizione", ["F1", "FC", "P1", "P2"]),
            ("Vuoto", ["VS1", "VS2", "VI1", "VI2"]),
        ]

        for ax, (title, cols) in zip(axes.flat, plot_groups):
            ax.set_facecolor("#252535")
            ax.set_title(title, color="#c0c0e0", fontsize=8, pad=3)
            ax.tick_params(colors="#a0a0c0", labelsize=6)
            ax.grid(True, color="#3a3a5c", linewidth=0.3, linestyle="--", alpha=0.5)
            for sp in ax.spines.values():
                sp.set_edgecolor("#3a3a5c")
            plotted = False
            for i, col in enumerate(cols):
                if col in data:
                    pts = sorted(data[col])
                    xs  = [p[0] for p in pts]
                    ys  = [p[1] for p in pts]
                    ax.plot(xs, ys, color=palette[i % len(palette)],
                            linewidth=0.9, label=col)
                    plotted = True
            if plotted:
                ax.legend(fontsize=6, loc="upper left",
                          facecolor="#252535", labelcolor="#c0c0e0",
                          edgecolor="#3a3a5c")

        fig.tight_layout(pad=1.0)
        return fig

    # ------------------------------------------------------------------
    # GENERA PDF
    # ------------------------------------------------------------------
    def _gr_export_pdf(self):
        if not self._gr_csv_path:
            messagebox.showwarning("Attenzione", "Nessun CSV caricato.")
            return

        stampo_key = self._gr_stampo_var.get()

        # _validate_csv(csv_path) → (bool, msg)
        valid, msg = _validate_csv(self._gr_csv_path)
        if not valid:
            messagebox.showwarning("CSV non compatibile", msg)
            return

        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.splitext(os.path.basename(self._gr_csv_path))[0]
        out_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{base}_{ts}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not out_path:
            return

        self.set_status("Generazione PDF in corso...")

        csv_path   = self._gr_csv_path

        def _run():
            try:
                # generate_lamborghini_pdf(csv_path, stampo_name, output_path, ...)
                generate_lamborghini_pdf(csv_path, stampo_key, out_path)
                self.after(0, lambda: self.set_status(
                    f"PDF salvato: {os.path.basename(out_path)}"))
                self.after(0, lambda: messagebox.showinfo(
                    "Completato", f"PDF salvato:\n{out_path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF"))

        threading.Thread(target=_run, daemon=True).start()
