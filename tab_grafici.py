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
    generate_front_firewall_pdf,
    detect_csv_type,
    _autodetect_profile,
    _validate_csv,
    PROFILES,
    PRESSASTAMPI,
)
from csv_parser import parse_universal_csv


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
        self._gr_rows        = []
        self._gr_headers     = []
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
        stampi_init = list(PRESSASTAMPI[list(PRESSASTAMPI.keys())[0]].keys())
        self._gr_stampo_var.set(stampi_init[0] if stampi_init else "")
        self._gr_stampo_menu = ctk.CTkOptionMenu(
            tb, variable=self._gr_stampo_var,
            values=stampi_init,
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

        self._gr_placeholder = ctk.CTkLabel(
            preview_frame,
            text="Seleziona pressa e stampo, poi apri un CSV per vedere l'anteprima.",
            font=("Segoe UI", 13), text_color=COLORS["text2"])
        self._gr_placeholder.pack(expand=True)

    # ------------------------------------------------------------------
    # CAMBIO PRESSA / STAMPO
    # ------------------------------------------------------------------
    def _gr_on_pressa_change(self, _=None):
        pressa = self._gr_pressa_var.get()
        stampi = list(PRESSASTAMPI.get(pressa, {}).keys())
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
            rows, headers, _, _, _ = parse_universal_csv(path)
            self._gr_csv_path = path
            self._gr_rows     = rows
            self._gr_headers  = headers

            # autodetect profilo
            profile_key = _autodetect_profile(rows, headers)
            if profile_key:
                self._gr_profile_key = profile_key
                # allinea menu pressa/stampo
                for pressa, stampi in PRESSASTAMPI.items():
                    if profile_key in stampi:
                        self._gr_pressa_var.set(pressa)
                        sl = list(stampi.keys())
                        self._gr_stampo_menu.configure(values=sl)
                        self._gr_stampo_var.set(profile_key)
                        break

            self._gr_info_lbl.configure(
                text=f"{os.path.basename(path)}  |  {len(rows)} record",
                text_color=COLORS["text"])
            self.set_status(f"Grafici CSV: {os.path.basename(path)} ({len(rows)} record)")
            self._gr_update_preview()
        except Exception as e:
            messagebox.showerror("Errore CSV Grafici", str(e))

    # ------------------------------------------------------------------
    # ANTEPRIMA
    # ------------------------------------------------------------------
    def _gr_update_preview(self):
        if not self._gr_rows:
            return
        pressa     = self._gr_pressa_var.get()
        stampo_key = self._gr_stampo_var.get()
        profile    = PROFILES.get(stampo_key) or PROFILES.get(
            PRESSASTAMPI.get(pressa, {}).get(stampo_key))
        if not profile:
            return

        # pulizia canvas precedente
        for w in self._gr_preview_frame.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        try:
            fig = self._gr_build_preview_fig(profile)
            self._gr_fig = fig
            canvas = FigureCanvasTkAgg(fig, master=self._gr_preview_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self._gr_canvas_widget = canvas
        except Exception as e:
            ctk.CTkLabel(
                self._gr_preview_frame,
                text=f"Errore anteprima: {e}",
                font=("Segoe UI", 11), text_color=COLORS["error"]
            ).pack(expand=True)

    def _gr_build_preview_fig(self, profile):
        """Costruisce una figura matplotlib di anteprima."""
        rows    = self._gr_rows
        headers = self._gr_headers

        time_col = next(
            (h for h in headers if "time" in h.lower() or "tempo" in h.lower()), None)
        if time_col is None and headers:
            time_col = headers[0]

        time_vals = []
        for r in rows:
            v = r.get(time_col)
            if isinstance(v, (int, float)):
                time_vals.append(v)
            else:
                time_vals.append(None)

        # filtra None
        valid = [(t, r) for t, r in zip(time_vals, rows) if t is not None]
        if not valid:
            valid = [(i, r) for i, r in enumerate(rows)]
        ts   = [v[0] for v in valid]
        vrows = [v[1] for v in valid]

        # colonne temperatura
        temp_cols = [h for h in headers
                     if any(k in h.lower() for k in
                            ["temp", "zona", "zone", "temperatura"])]
        if not temp_cols:
            temp_cols = [h for h in headers
                         if h != time_col
                         and isinstance(vrows[0].get(h) if vrows else None, (int, float))][:6]

        fig, ax = plt.subplots(figsize=(10, 4), facecolor="#1a1b2e")
        ax.set_facecolor("#252535")
        ax.set_title(profile.get("title", "Anteprima"),
                     color="#c0c0e0", fontsize=11, pad=6)
        ax.set_xlabel(time_col or "Tempo", color="#a0a0c0", fontsize=9)
        ax.set_ylabel("Valore", color="#a0a0c0", fontsize=9)
        ax.tick_params(colors="#a0a0c0", labelsize=7)
        ax.grid(True, color="#3a3a5c", linewidth=0.4, linestyle="--", alpha=0.6)
        for sp in ax.spines.values():
            sp.set_edgecolor("#3a3a5c")

        palette = ["#6c63ff", "#00d4ff", "#52c41a", "#faad14",
                   "#f44322", "#e91e63", "#9c27b0", "#ff9800"]
        for i, col in enumerate(temp_cols[:8]):
            vals = [r.get(col) for r in vrows]
            yf   = [y if isinstance(y, (int, float)) else None for y in vals]
            xf   = [x for x, y in zip(ts, yf) if y is not None]
            yf2  = [y for y in yf if y is not None]
            if xf:
                ax.plot(xf, yf2, color=palette[i % len(palette)],
                        linewidth=1.2, label=col)

        if temp_cols:
            ax.legend(fontsize=7, loc="upper left",
                      facecolor="#252535", labelcolor="#c0c0e0",
                      edgecolor="#3a3a5c")
        fig.tight_layout(pad=1.0)
        return fig

    # ------------------------------------------------------------------
    # GENERA PDF
    # ------------------------------------------------------------------
    def _gr_export_pdf(self):
        if not self._gr_rows:
            messagebox.showwarning("Attenzione", "Nessun CSV caricato.")
            return

        pressa     = self._gr_pressa_var.get()
        stampo_key = self._gr_stampo_var.get()

        valid, msg = _validate_csv(self._gr_rows, self._gr_headers, stampo_key)
        if not valid:
            messagebox.showwarning("CSV non compatibile", msg)
            return

        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.splitext(
            os.path.basename(self._gr_csv_path))[0] if self._gr_csv_path else "report"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{base}_{ts}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return

        self.set_status("Generazione PDF in corso...")

        def _run():
            try:
                generate_lamborghini_pdf(
                    self._gr_rows, self._gr_headers,
                    path, stampo_key)
                self.after(0, lambda: self.set_status(
                    f"PDF salvato: {os.path.basename(path)}"))
                self.after(0, lambda: messagebox.showinfo(
                    "Completato", f"PDF salvato:\n{path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF"))

        threading.Thread(target=_run, daemon=True).start()
