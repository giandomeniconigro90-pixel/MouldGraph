# -*- coding: utf-8 -*-
"""Tab "CSV": grafico interattivo, confronto, range, anomalie ed export."""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import os
from datetime import datetime
import threading
import tkinter.simpledialog as simpledialog
from ..constants import COLORS
from ..csv_parsers import _is_long_cycle_csv, _parse_long_cycle_csv, _uc_build_series, _uc_parse_dt, parse_universal_csv
from ..log_analysis import detect_anomalies
from ..pdf_plant import generate_plant_pdf
from ..plot_canvas import InteractivePlotCanvas, _UC_SERIES_PALETTE
from ..ui_utils import _isolate_scroll


class CsvMixin:
    
    # =========================================================
    #  TAB: DATI CSV  (Universal Plant CSV Analyzer)
    # =========================================================

    def build_csv_tab(self, parent):
        self._csv_rows          = []
        self._csv_rows2         = []   # secondo CSV per confronto
        self._csv_col_meta2     = {}   # col_meta del secondo CSV
        self._csv_num_cols2     = []   # colonne numeriche del secondo CSV
        self._csv_y_vars2       = {}   # checkbox vars colonne CSV2
        self._csv_filepath2     = None
        self._csv_colors2       = {}
        self._csv_headers       = []
        self._csv_col_meta      = {}
        self._csv_numeric_cols  = []
        self._csv_datetime_cols = []
        self._csv_binary_cols   = []
        self._csv_sep           = ","
        self._csv_enc           = "utf-8"
        self._csv_filepath      = None
        self._csv_xcol_var      = tk.StringVar(value="-")
        self._csv_y_vars        = {}
        self._csv_y2_vars       = {}
        self._csv_colors        = {}

        tb = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8, height=44)
        tb.pack(fill="x", pady=(0, 6))
        tb.pack_propagate(False)
        ctk.CTkButton(tb, text="Apri CSV", width=100, height=30,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"],
                      command=self._csv_open).pack(side="left", padx=10, pady=7)
        self._csv_info_lbl = ctk.CTkLabel(
            tb, text="Nessun file caricato",
            font=("Segoe UI", 11), text_color=COLORS["text2"])
        self._csv_info_lbl.pack(side="left", padx=8)

        # ── badge anomalie ────────────────────────────────────────────
        self._csv_anomaly_badge = ctk.CTkLabel(
            tb, text="",
            font=("Segoe UI", 10, "bold"),
            text_color=COLORS["text"],
            fg_color=COLORS["error"], corner_radius=6)
        # non pakkato finché non ci sono anomalie

        for txt, cmd, fg in [
            ("Export PDF",    self._csv_export_pdf,    "#7c3aed"),
            ("Export PNG",    self._csv_export_png,    COLORS["surface2"]),
            ("Export Report", self._csv_export_report, COLORS["surface2"]),
            ("Reset Zoom",    self._csv_reset_zoom,    COLORS["surface2"]),
            ("Confronta CSV", self._csv_open_compare,  COLORS["surface2"]),
        ]:
            ctk.CTkButton(tb, text=txt, width=115, height=30,
                          fg_color=fg, hover_color=COLORS["border"],
                          text_color=COLORS["text"],
                          command=cmd).pack(side="right", padx=4, pady=7)

        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True)
        lw = ctk.CTkFrame(body, fg_color=COLORS["bg"], width=294)
        lw.pack(side="left", fill="y", padx=(0, 6))
        lw.pack_propagate(False)
        left = ctk.CTkScrollableFrame(
            lw, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        left.pack(fill="both", expand=True)
        _isolate_scroll(left)

        # ── Asse X (evidenziato) ──────────────────────────────────────
        self._sec(left, "Asse X")
        self._csv_xcard = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_xcard.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(self._csv_xcard, text="Colonna X",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=10, pady=(8, 2))
        self._csv_xcol_menu = ctk.CTkOptionMenu(
            self._csv_xcard, variable=self._csv_xcol_var, values=["-"],
            width=256, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"],
            command=self._csv_on_xcol_change)
        self._csv_xcol_menu.pack(padx=10, pady=(0, 6))

        # filtro temporale (Dal / Al) — visibile solo se X è datetime
        self._csv_tfilter_frame = ctk.CTkFrame(self._csv_xcard, fg_color="transparent")
        ctk.CTkLabel(self._csv_tfilter_frame, text="Filtra intervallo",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=10, pady=(2, 2))
        tf_row = ctk.CTkFrame(self._csv_tfilter_frame, fg_color="transparent")
        tf_row.pack(fill="x", padx=8, pady=(0, 6))
        self._csv_from_var = tk.StringVar()
        self._csv_to_var   = tk.StringVar()
        ctk.CTkLabel(tf_row, text="Dal", font=("Segoe UI", 9),
                     text_color=COLORS["text2"]).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(tf_row, textvariable=self._csv_from_var,
                     placeholder_text="HH:MM:SS",
                     width=80, height=24,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"]
                     ).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tf_row, text="Al", font=("Segoe UI", 9),
                     text_color=COLORS["text2"]).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(tf_row, textvariable=self._csv_to_var,
                     placeholder_text="HH:MM:SS",
                     width=80, height=24,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"]
                     ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(tf_row, text="✓", width=28, height=24,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 10),
                      command=self._csv_refresh_plot).pack(side="left")

        self._sec(left, "Serie Y")
        self._csv_series_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_series_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_series_card,
                     text="Carica un CSV per vedere le colonne",
                     font=("Segoe UI", 10),
                     text_color=COLORS["text2"]).pack(padx=10, pady=10)

        self._sec(left, "Confronto CSV ②")
        self._csv_series2_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_series2_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_series2_card,
                     text="Carica un CSV di confronto (pulsante sopra)",
                     font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(padx=10, pady=6)

        self._sec(left, "Stati digitali")
        self._csv_digital_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_digital_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_digital_card, text="—",
                     font=("Segoe UI", 10),
                     text_color=COLORS["text2"]).pack(padx=10, pady=6)

        # ── Statistiche come card ──────────────────────────────────────
        self._sec(left, "Statistiche")
        self._csv_stats_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_stats_container.pack(fill="x", pady=(0, 8))
        # mantengo anche il textbox originale (nascosto) per compatibilità export
        self._csv_statsbox = ctk.CTkTextbox(
            left, height=1, font=("Courier New", 10),
            fg_color=COLORS["bg"], text_color=COLORS["bg"], border_width=0)
        self._csv_statsbox.pack_forget()  # nascosto, solo per export report

        # ── Range personalizzati ──────────────────────────────────────
        self._csv_ranges = []   # [{col, lo, hi}]
        self._sec(left, "Range personalizzati")
        range_hdr = ctk.CTkFrame(left, fg_color="transparent")
        range_hdr.pack(fill="x", pady=(0, 2))
        ctk.CTkButton(range_hdr, text="+ Aggiungi range", width=130, height=24,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._csv_add_range).pack(side="left")
        ctk.CTkButton(range_hdr, text="Azzera", width=70, height=24,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=self._csv_clear_ranges).pack(side="left", padx=6)
        self._csv_ranges_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_ranges_container.pack(fill="x", pady=(0, 8))

        self._sec(left, "Anomalie rilevate")
        self._csv_anomaly_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_anomaly_container.pack(fill="x", pady=(0, 8))

        right = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        right.pack(side="left", fill="both", expand=True)
        self._csv_iplot = InteractivePlotCanvas(right, height=430)


    def _csv_on_xcol_change(self, val):
        """Chiamato al cambio colonna X: mostra filtro temporale se datetime."""
        is_dt = val in self._csv_datetime_cols
        if is_dt:
            self._csv_xcard.configure(border_width=2, border_color=COLORS["accent"])
            self._csv_tfilter_frame.pack(fill="x", pady=(0, 4))
        else:
            self._csv_xcard.configure(border_width=0)
            self._csv_tfilter_frame.pack_forget()
        self._csv_refresh_plot()


    def _csv_get_filtered_rows(self):
        """Ritorna le righe filtrate per intervallo temporale (se impostato)."""
        rows = self._csv_rows
        x_col = self._csv_xcol_var.get()
        if x_col not in self._csv_datetime_cols:
            return rows
        from_s = self._csv_from_var.get().strip()
        to_s   = self._csv_to_var.get().strip()
        if not from_s and not to_s:
            return rows
        filtered = []
        for r in rows:
            ts = _uc_parse_dt(r.get(x_col, ""))
            if ts is None:
                filtered.append(r)
                continue
            t = ts.strftime("%H:%M:%S")
            if from_s and t < from_s:
                continue
            if to_s and t > to_s:
                continue
            filtered.append(r)
        return filtered


    def _csv_open_compare(self):
        """Carica un secondo CSV e sovrappone le curve al grafico corrente."""
        if not self._csv_rows:
            messagebox.showwarning("Confronta", "Carica prima il CSV principale.")
            return
        path = filedialog.askopenfilename(
            title="Seleziona CSV da confrontare",
            filetypes=[("CSV / TSV / TXT", "*.csv *.tsv *.txt"), ("Tutti i file", "*.*")])
        if not path:
            return
        self.set_status("Caricamento CSV confronto...")
        def run():
            try:
                if _is_long_cycle_csv(path):
                    rows2, headers2, col_meta2, num_cols2, _, _, _, _ = \
                        _parse_long_cycle_csv(path)
                else:
                    rows2, headers2, col_meta2, num_cols2, _, _, _, _ = \
                        parse_universal_csv(path)
                palette2 = ["#ff6b6b","#ffd93d","#6bcb77","#4d96ff",
                            "#c77dff","#f9844a","#90e0ef","#f15bb5"]
                colors2 = {col: palette2[i % len(palette2)]
                           for i, col in enumerate(num_cols2)}
                def _apply():
                    self._csv_rows2     = rows2
                    self._csv_col_meta2 = col_meta2
                    self._csv_num_cols2 = list(num_cols2)
                    self._csv_filepath2 = path
                    self._csv_colors2.update(colors2)
                    self._csv_rebuild_series2_panel()
                    self._csv_refresh_plot()
                    self.set_status(
                        f"Confronto: {os.path.basename(path)} ({len(rows2)} righe)")
                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore CSV confronto", str(e)))
        threading.Thread(target=run, daemon=True).start()


    def _csv_rebuild_series2_panel(self):
        """Ricostruisce il pannello checkbox per le colonne del secondo CSV."""
        for w in self._csv_series2_card.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_rows2 or not self._csv_num_cols2:
            ctk.CTkLabel(self._csv_series2_card,
                         text="Carica un CSV di confronto (pulsante sopra)",
                         font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(padx=10, pady=6)
            return
        # bottoni Tutti / Nessuno
        hf = ctk.CTkFrame(self._csv_series2_card, fg_color="transparent")
        hf.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkButton(hf, text="Tutti", width=62, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"],
                      command=lambda: self._csv_sel_all_2(True)).pack(side="left", padx=2)
        ctk.CTkButton(hf, text="Nessuno", width=72, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"],
                      command=lambda: self._csv_sel_all_2(False)).pack(side="left", padx=2)
        # ricrea vars preservando stato precedente
        prev2 = {c: v.get() for c, v in self._csv_y_vars2.items()}
        self._csv_y_vars2 = {}
        for col in self._csv_num_cols2:
            var = tk.BooleanVar(value=prev2.get(col, True))
            self._csv_y_vars2[col] = var
            color = self._csv_colors2.get(col, COLORS["accent"])
            row = ctk.CTkFrame(self._csv_series2_card, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=1)
            dot = tk.Canvas(row, width=12, height=12,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=(4, 2), pady=4)
            ctk.CTkCheckBox(
                row, text=col, variable=var,
                font=("Segoe UI", 10), text_color=COLORS["text"],
                fg_color=COLORS["accent"], hover_color="#5a52e0",
                checkmark_color=COLORS["text"],
                border_color=COLORS["border"],
                command=self._csv_refresh_plot
            ).pack(side="left", fill="x", expand=True)


    def _csv_sel_all_2(self, val):
        """Seleziona/deseleziona tutte le colonne del secondo CSV."""
        for v in self._csv_y_vars2.values():
            v.set(val)
        self._csv_refresh_plot()


    def _csv_update_stats_cards(self, y_cols):
        """Rende le statistiche come card colorate invece di un textbox."""
        for w in self._csv_stats_container.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_rows or not y_cols:
            return
        # aggiorna anche il textbox nascosto per l'export report
        self._csv_statsbox.configure(state="normal")
        self._csv_statsbox.delete("1.0", "end")
        rows = self._csv_get_filtered_rows()
        for col in y_cols:
            vals = []
            for r in rows:
                try:
                    vals.append(float(r.get(col, "").replace(",", ".")))
                except Exception:
                    pass
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            unit = self._csv_col_meta.get(col, {}).get("unit", "")
            u    = f" {unit}" if unit else ""
            color = self._csv_colors.get(col, COLORS["accent"])
            # card
            card = ctk.CTkFrame(self._csv_stats_container,
                                fg_color=COLORS["surface"], corner_radius=8)
            card.pack(fill="x", pady=2)
            # intestazione colorata
            hdr_f = ctk.CTkFrame(card, fg_color=color, corner_radius=6, height=22)
            hdr_f.pack(fill="x", padx=4, pady=(4, 2))
            hdr_f.pack_propagate(False)
            ctk.CTkLabel(hdr_f, text=col, font=("Segoe UI", 9, "bold"),
                         text_color="#fff").pack(side="left", padx=8)
            ctk.CTkLabel(hdr_f, text=f"N={len(vals)}",
                         font=("Segoe UI", 8), text_color="#ffffff99").pack(side="right", padx=6)
            # valori in griglia 2×2
            grid = ctk.CTkFrame(card, fg_color="transparent")
            grid.pack(fill="x", padx=6, pady=(2, 6))
            for i, (lbl, val) in enumerate([
                ("min", f"{min(vals):.4g}{u}"),
                ("max", f"{max(vals):.4g}{u}"),
                ("μ",   f"{mean:.4g}{u}"),
                ("σ",   f"{std:.4g}"),
            ]):
                col_f = ctk.CTkFrame(grid, fg_color="transparent")
                col_f.grid(row=i//2, column=i%2, sticky="w", padx=4, pady=1)
                ctk.CTkLabel(col_f, text=lbl, font=("Segoe UI", 8),
                             text_color=COLORS["text2"]).pack(side="left")
                ctk.CTkLabel(col_f, text=f"  {val}", font=("Segoe UI", 9, "bold"),
                             text_color=COLORS["text"]).pack(side="left")
            # aggiorna textbox nascosto
            self._csv_statsbox.insert("end",
                f"▸ {col[:24]}\n"
                f"  min={min(vals):.4g}{u}  max={max(vals):.4g}{u}\n"
                f"  μ={mean:.4g}{u}  σ={std:.4g}  N={len(vals)}\n\n")
        self._csv_statsbox.configure(state="disabled")


    def _csv_add_range(self):
        """Dialogo per aggiungere un range personalizzato su una colonna."""
        if not self._csv_numeric_cols:
            messagebox.showinfo("Range", "Carica prima un CSV.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Nuovo range")
        win.geometry("340x280")
        win.resizable(False, False)
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()

        ctk.CTkLabel(win, text="Colonna", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 2))
        col_var = ctk.StringVar(value=self._csv_numeric_cols[0])
        ctk.CTkOptionMenu(win, variable=col_var,
                          values=self._csv_numeric_cols, width=290,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(padx=20)

        ctk.CTkLabel(win, text="Minimo (Lo) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(12, 2))
        lo_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=lo_var, placeholder_text="es. 0.5",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=290).pack(padx=20)

        ctk.CTkLabel(win, text="Massimo (Hi) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(10, 2))
        hi_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=hi_var, placeholder_text="es. 150.0",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=290).pack(padx=20)

        def _confirm():
            col = col_var.get()
            lo = None; hi = None
            try: lo = float(lo_var.get().replace(",", "."))
            except Exception: pass
            try: hi = float(hi_var.get().replace(",", "."))
            except Exception: pass
            if lo is None and hi is None:
                messagebox.showwarning("Range", "Inserisci almeno un valore Lo o Hi.")
                return
            self._csv_ranges.append({"col": col, "lo": lo, "hi": hi})
            self._csv_rebuild_range_cards()
            self._csv_refresh_plot()
            win.destroy()

        ctk.CTkButton(win, text="Aggiungi", width=140, height=32,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], command=_confirm).pack(pady=16)


    def _csv_clear_ranges(self):
        self._csv_ranges.clear()
        self._csv_rebuild_range_cards()
        self._csv_refresh_plot()


    def _csv_rebuild_range_cards(self):
        for w in self._csv_ranges_container.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_ranges:
            ctk.CTkLabel(self._csv_ranges_container,
                         text="Nessun range definito",
                         font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(
                anchor="w", padx=4, pady=2)
            return
        for idx, rule in enumerate(self._csv_ranges):
            col = rule["col"]; lo = rule.get("lo"); hi = rule.get("hi")
            parts = []
            if lo is not None: parts.append(f"Lo={lo:.4g}")
            if hi is not None: parts.append(f"Hi={hi:.4g}")
            label = f"{col}  [{',  '.join(parts)}]"
            card = ctk.CTkFrame(self._csv_ranges_container,
                                fg_color=COLORS["surface"], corner_radius=6)
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 9),
                         text_color=COLORS["text"]).pack(side="left", padx=8, pady=4)
            ctk.CTkButton(card, text="✕", width=22, height=22,
                          fg_color="transparent", hover_color=COLORS["border"],
                          text_color=COLORS["text2"], font=("Segoe UI", 9),
                          command=lambda i=idx: self._csv_remove_range(i)
                          ).pack(side="right", padx=4)


    def _csv_remove_range(self, idx):
        if 0 <= idx < len(self._csv_ranges):
            self._csv_ranges.pop(idx)
        self._csv_rebuild_range_cards()
        self._csv_refresh_plot()


    def _csv_open(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV / TSV / TXT", "*.csv *.tsv *.txt"), ("Tutti i file", "*.*")])
        if not path:
            return
        self.set_status("Caricamento CSV in corso...")
        def run():
            try:
                rows, headers, col_meta, num_cols, dt_cols, bin_cols, sep, enc = \
                    parse_universal_csv(path)
                def _apply():
                    self._csv_rows          = rows
                    self._csv_headers       = headers
                    self._csv_col_meta      = col_meta
                    self._csv_numeric_cols  = num_cols
                    self._csv_datetime_cols = dt_cols
                    self._csv_binary_cols   = bin_cols
                    self._csv_sep           = sep
                    self._csv_enc           = enc
                    self._csv_filepath      = path
                    self._csv_populate_controls()
                    self.set_status(
                        f"CSV caricato: {len(rows)} righe · {len(headers)} colonne · "
                        f"sep='{sep}' · enc={enc}")
                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore CSV", str(e)))
                self.after(0, lambda: self.set_status("Errore caricamento CSV."))
        threading.Thread(target=run, daemon=True).start()


    def _csv_populate_controls(self):
        basename = os.path.basename(self._csv_filepath or "")
        self._csv_info_lbl.configure(
            text=f"{basename}  │  {len(self._csv_rows)} righe  │  "
                 f"sep='{self._csv_sep}'  enc={self._csv_enc}")
        x_choices = self._csv_datetime_cols + self._csv_numeric_cols
        if not x_choices:
            x_choices = ["-"]
        self._csv_xcol_menu.configure(values=x_choices)
        self._csv_xcol_var.set(x_choices[0])
        palette = list(_UC_SERIES_PALETTE)
        for i, col in enumerate(self._csv_numeric_cols):
            if col not in self._csv_colors:
                self._csv_colors[col] = palette[i % len(palette)]
        for w in self._csv_series_card.winfo_children():
            w.destroy()
        self._csv_y_vars  = {}
        self._csv_y2_vars = {}
        if not self._csv_numeric_cols:
            ctk.CTkLabel(self._csv_series_card,
                         text="Nessuna colonna numerica trovata",
                         font=("Segoe UI", 10),
                         text_color=COLORS["text2"]).pack(padx=10, pady=8)
        else:
            hf = ctk.CTkFrame(self._csv_series_card, fg_color="transparent")
            hf.pack(fill="x", padx=8, pady=(6, 2))
            ctk.CTkButton(hf, text="Tutti", width=62, height=22,
                          fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                          text_color=COLORS["text2"],
                          command=lambda: self._csv_sel_all(True)).pack(side="left", padx=2)
            ctk.CTkButton(hf, text="Nessuno", width=72, height=22,
                          fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                          text_color=COLORS["text2"],
                          command=lambda: self._csv_sel_all(False)).pack(side="left", padx=2)
            for col in self._csv_numeric_cols:
                var  = tk.BooleanVar(value=True)
                var2 = tk.BooleanVar(value=False)
                self._csv_y_vars[col]  = var
                self._csv_y2_vars[col] = var2
                color = self._csv_colors[col]
                meta  = self._csv_col_meta.get(col, {})
                unit  = meta.get("unit", "")
                label = meta.get("label", col)
                disp = col if col == label else f"{col} [{label}]"
                if unit:
                    disp += f" {unit}"
                row_f = ctk.CTkFrame(self._csv_series_card, fg_color="transparent")
                row_f.pack(fill="x", padx=6, pady=1)
                dot = tk.Canvas(row_f, width=12, height=12,
                                bg=COLORS["surface"], highlightthickness=0)
                dot.create_oval(1, 1, 11, 11, fill=color, outline="")
                dot.pack(side="left", padx=(4, 2), pady=4)
                ctk.CTkCheckBox(
                    row_f, text=disp, variable=var,
                    font=("Segoe UI", 10), text_color=COLORS["text"],
                    fg_color=COLORS["accent"], hover_color="#5a52e0",
                    checkmark_color=COLORS["text"],
                    border_color=COLORS["border"],
                    command=self._csv_refresh_plot
                ).pack(side="left", fill="x", expand=True)
                btn_holder = {}
                def _make_toggle(c=col, bv=var2, bh=btn_holder):
                    def _toggle():
                        bv.set(not bv.get())
                        bh["b"].configure(
                            text="Y2" if bv.get() else "Y1",
                            fg_color="#7c3aed" if bv.get() else COLORS["surface2"])
                        self._csv_refresh_plot()
                    return _toggle
                y2b = ctk.CTkButton(
                    row_f, text="Y1", width=34, height=22,
                    fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                    text_color=COLORS["text2"], font=("Segoe UI", 9),
                    command=_make_toggle())
                y2b.pack(side="right", padx=(2, 6))
                btn_holder["b"] = y2b
        for w in self._csv_digital_card.winfo_children():
            w.destroy()
        if not self._csv_binary_cols:
            ctk.CTkLabel(self._csv_digital_card, text="—",
                         font=("Segoe UI", 10),
                         text_color=COLORS["text2"]).pack(padx=10, pady=6)
        else:
            for col in self._csv_binary_cols:
                ctk.CTkLabel(self._csv_digital_card,
                             text=f"⚡  {col}",
                             font=("Segoe UI", 10),
                             text_color=COLORS["accent2"],
                             anchor="w").pack(anchor="w", padx=10, pady=2)
        self._csv_refresh_plot()


    def _csv_refresh_plot(self):
        if not self._csv_rows:
            return
        x_col  = self._csv_xcol_var.get()
        if x_col == "-":
            x_col = None
        y_cols  = [c for c, v in self._csv_y_vars.items() if v.get()]
        y2_cols = {c for c, v in self._csv_y2_vars.items() if v.get()}

        # usa righe filtrate per intervallo temporale
        rows = self._csv_get_filtered_rows()
        xs_raw, series, x_type = _uc_build_series(
            rows, x_col, y_cols, self._csv_col_meta)
        colors  = {c: self._csv_colors[c] for c in y_cols if c in self._csv_colors}
        x_label = x_col or "Indice"

        # serie principali CSV1
        self._csv_iplot.set_data(
            xs_raw, series, x_type, self._csv_col_meta,
            y2_cols=y2_cols, colors=colors, x_label=x_label)

        # ── bande range personalizzati sul grafico ─────────────────────
        self._csv_iplot.set_ranges(getattr(self, "_csv_ranges", []))

        # ── overlay ② DOPO set_ranges: colonne spuntate nel pannello CSV2 ──
        if self._csv_rows2:
            cols_ov = [c for c, v in self._csv_y_vars2.items() if v.get()]
            if cols_ov:
                self._csv_iplot._overlay_second_csv(
                    self._csv_rows2, x_col, cols_ov,
                    self._csv_colors2,
                    getattr(self, "_csv_col_meta2", self._csv_col_meta))

        self._csv_update_stats_cards(y_cols)
        self._csv_update_anomalies()


    def _csv_sel_all(self, val):
        for v in self._csv_y_vars.values():
            v.set(val)
        self._csv_refresh_plot()


    def _csv_update_stats(self, y_cols):
        # alias per compatibilità export — usa il nuovo metodo con card
        self._csv_update_stats_cards(y_cols)


    def _csv_update_anomalies(self):
        for w in self._csv_anomaly_container.winfo_children():
            w.destroy()
        if not self._csv_rows:
            self._csv_anomaly_badge.pack_forget()
            return
        x_col = self._csv_xcol_var.get()
        rows = self._csv_get_filtered_rows()
        anomalies = []

        # ── Range personalizzati (priorità assoluta) ──────────────────
        for rule in self._csv_ranges:
            col = rule["col"]; lo = rule.get("lo"); hi = rule.get("hi")
            violations = []
            for i, r in enumerate(rows):
                try:
                    val = float(r.get(col, "").replace(",", "."))
                except Exception:
                    continue
                ts = _uc_parse_dt(r.get(x_col, "")) if x_col and x_col != "-" else None
                ts_str = ts.strftime("%H:%M:%S") if ts else f"riga {i+1}"
                if lo is not None and val < lo:
                    violations.append((ts_str, val, f"< {lo:.4g}"))
                elif hi is not None and val > hi:
                    violations.append((ts_str, val, f"> {hi:.4g}"))
            if violations:
                # raggruppa: mostra prima e ultima violazione + conteggio
                cnt = len(violations)
                first_ts, first_val, first_dir = violations[0]
                last_ts,  last_val,  last_dir  = violations[-1]
                desc = (f"{cnt} campion{'e' if cnt==1 else 'i'} fuori range. "
                        f"Primo: {first_val:.4g} {first_dir} @ {first_ts}. "
                        f"Ultimo: {last_val:.4g} {last_dir} @ {last_ts}.")
                anomalies.append(("RANGE", f"{col} — {cnt} violazion{'e' if cnt==1 else 'i'}",
                                  desc, COLORS["error"]))

        # ── Rilevamento automatico (solo se nessun range manuale definito) ──
        if not self._csv_ranges:
            all_cols = self._csv_numeric_cols + self._csv_binary_cols
            num_rows = []
            for i, r in enumerate(rows):
                d = {"_ts": _uc_parse_dt(r.get(x_col, "")) if x_col != "-" else None}
                for col in all_cols:
                    try:
                        d[col] = float(r.get(col, "").replace(",", "."))
                    except Exception:
                        d[col] = 0.0
                num_rows.append(d)
            try:
                auto_anomalies, _ = detect_anomalies(num_rows, all_cols)
                anomalies.extend(auto_anomalies)
            except Exception:
                pass

        # aggiorna badge
        if anomalies:
            self._csv_anomaly_badge.configure(
                text=f"  ⚠ {len(anomalies)} anomalie  ")
            self._csv_anomaly_badge.pack(side="left", padx=6, pady=7)
        else:
            self._csv_anomaly_badge.pack_forget()

        if not anomalies:
            ctk.CTkLabel(self._csv_anomaly_container,
                         text="Nessuna anomalia rilevata",
                         font=("Segoe UI", 10),
                         text_color=COLORS["info"]).pack(anchor="w", padx=4, pady=4)
            return
        for tag, title, desc, color in anomalies[:30]:
            card = ctk.CTkFrame(self._csv_anomaly_container,
                                fg_color=COLORS["surface"], corner_radius=6)
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(card, text=f"[{tag}]  {title}",
                         font=("Segoe UI", 10, "bold"),
                         text_color=color, anchor="w").pack(anchor="w", padx=8, pady=(6, 1))
            ctk.CTkLabel(card, text=desc,
                         font=("Segoe UI", 9),
                         text_color=COLORS["text2"],
                         anchor="w", wraplength=250).pack(anchor="w", padx=8, pady=(0, 6))


    def _csv_reset_zoom(self):
        if self._csv_iplot:
            self._csv_iplot.reset_zoom()


    def _csv_export_png(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato da esportare.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
            initialfile="grafico_csv.png")
        if not path:
            return
        try:
            self._csv_iplot.export_png(path)
            self.set_status(f"PNG salvato: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Errore PNG", str(e))


    def _csv_export_report(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato caricato.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt")],
            initialfile="report_csv.txt")
        if not path:
            return
        lines = [
            f"REPORT CSV  —  {os.path.basename(self._csv_filepath or '')}",
            f"Generato:  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            f"Righe: {len(self._csv_rows)}   Colonne: {len(self._csv_headers)}",
            f"Separatore: '{self._csv_sep}'   Encoding: {self._csv_enc}",
            "", "=" * 55, "COLONNE RILEVATE:", "=" * 55,
        ]
        for col in self._csv_headers:
            m = self._csv_col_meta.get(col, {})
            lines.append(
                f"  {col:<32}  [{m.get('col_type','?'):8}]  "
                f"{m.get('unit',''):6}  {m.get('label','')}")
        lines += ["", "=" * 55, "STATISTICHE:", "=" * 55]
        for col in self._csv_numeric_cols:
            vals = []
            for r in self._csv_rows:
                try:
                    vals.append(float(r.get(col, "").replace(",", ".")))
                except Exception:
                    pass
            if vals:
                mean = sum(vals) / len(vals)
                std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
                lines.append(
                    f"  {col:<32}  min={min(vals):.4g}  max={max(vals):.4g}"
                    f"  μ={mean:.4g}  σ={std:.4g}  N={len(vals)}")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.set_status(f"Report salvato: {os.path.basename(path)}")
            messagebox.showinfo("Completato", f"Report salvato:\n{path}")
        except Exception as e:
            messagebox.showerror("Errore salvataggio", str(e))


    def _csv_export_pdf(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato caricato.")
            return
        y_cols = [c for c, v in self._csv_y_vars.items() if v.get()]
        if not y_cols:
            messagebox.showwarning("Attenzione", "Seleziona almeno una serie Y.")
            return
        plant = simpledialog.askstring(
            "Nome impianto",
            "Inserisci il nome dell'impianto (es. Forno 3, CNC-A, Pressa 5T):",
            initialvalue="Impianto")
        if plant is None:
            return
        plant = plant.strip() or "Impianto"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"report_{plant.replace(' ', '_')}.pdf")
        if not path:
            return
        y2_cols = {c for c, v in self._csv_y2_vars.items() if v.get()}
        x_col   = self._csv_xcol_var.get()
        if x_col == "-":
            x_col = None
        logo = getattr(self, "_grafici_logo_path", None)
        self.set_status("Generazione PDF impianto in corso...")
        def run():
            try:
                _cols2_exp = [c for c, v in self._csv_y_vars2.items() if v.get()]
                generate_plant_pdf(
                    rows        = self._csv_rows,
                    headers     = self._csv_headers,
                    col_meta    = self._csv_col_meta,
                    x_col       = x_col,
                    y_cols      = y_cols,
                    y2_cols     = y2_cols,
                    output_path = path,
                    plant_name  = plant,
                    logo_path   = logo,
                    notes       = "",
                    rows2       = self._csv_rows2 if (self._csv_rows2 and _cols2_exp) else None,
                    cols2       = _cols2_exp or None,
                    colors2     = self._csv_colors2,
                    col_meta2   = getattr(self, "_csv_col_meta2", {}),
                )
                self.after(0, lambda: self.set_status(
                    f"PDF salvato: {os.path.basename(path)}"))
                self.after(0, lambda: messagebox.showinfo(
                    "Completato", f"PDF salvato:\n{path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF."))
        threading.Thread(target=run, daemon=True).start()
