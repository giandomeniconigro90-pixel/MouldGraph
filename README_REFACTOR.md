# MouldGraph — Refactor Phase 1

> **Branch:** `refactor/modular-structure`  
> **Stato:** Phase 1 in corso — struttura parallela, non connessa a `main.py`

---

## Obiettivo Fase 1

Creare un package Python `mouldgraph/` **parallelo** al monolite
`log_analyzer_desktop_live.py`, senza modificare né main.py né il monolite.
L’obiettivo è isolare gradualmente le responsabilità del codice esistente in
moduli testabili e riusabili, mantenendo in ogni momento la possibilità di
tornare al monolite funzionante.

---

## Mappa Moduli e Dipendenze

```
mouldgraph/
├── __init__.py       # Dichiarazione package, esportazioni, versione
├── constants.py      # Costanti UI, colori, soglie (nessuna dipendenza esterna)
├── log_parsers.py    # Parser log testuali (stdlib only)
├── csv_parsers.py    # Parser CSV Siemens / Universal / Cannon / Persico (stdlib only)
├── widgets.py        # Widget Canvas Tkinter (⚠ richiede: customtkinter)
├── pdf_reports.py    # Report PDF (⚠ richiede: matplotlib, numpy, widgets)
└── app.py            # STUB Fase 1 (⚠ LogAnalyzerApp non ancora estratta)
```

### Grafo dipendenze

```
constants ←─────────────── log_parsers
    ↑                            csv_parsers
    └─── widgets ←────────── pdf_reports
              └─ customtkinter       └─ matplotlib, numpy
```

---

## Garanzie di Reversibilità

| Garanzia | Dettaglio |
|---|---|
| `main.py` intatto | Non modificato, continua a puntare al monolite |
| `log_analyzer_desktop_live.py` intatto | Non modificato, backup funzionante |
| Nessun import circolare | `mouldgraph/` non importa nulla dalla root |
| Nessun side-effect all’import | Nessun avvio GUI, nessuna scrittura file |
| Rollback immediato | `git checkout main` per ritornare allo stato stabile |

---

## Estrazione LogAnalyzerApp (bloccata in Fase 1)

`mouldgraph/app.py` è intenzionalmente uno **stub vuoto**.
L’estrazione di `LogAnalyzerApp` dal monolite è bloccata perché richiede:

1. **Isolamento variabili globali** — il monolite usa variabili di stato globali
   (es. `self.root`, callback Tkinter) che devono essere incapsulate prima di
   poter istanziare la classe in modo autonomo.
2. **Test di compatibilità CustomTkinter** — la versione del tema e i widget
   custom devono essere verificati con la nuova struttura.
3. **Validazione backend matplotlib** — il backend deve essere forzato a `Agg`
   per la generazione headless dei PDF, senza interferire con il rendering
   interattivo dei grafici.
4. **Freeze PyInstaller** — il package deve essere validato in un bundle
   PyInstaller prima di diventare entry point.

---

## Note PyInstaller / CustomTkinter / Matplotlib

- **PyInstaller**: i file di dati di `customtkinter` (temi, font) devono essere
  inclusi esplicitamente con `--add-data`. Verificare con `pyi-makespec`.
- **CustomTkinter**: usare sempre `ctk.set_appearance_mode()` e
  `ctk.set_default_color_theme()` prima di creare la finestra principale.
- **Matplotlib**: importare con `matplotlib.use("Agg")` **prima** di qualsiasi
  `import matplotlib.pyplot` nei moduli headless (`pdf_reports.py`).

---

## Piano Fase 2

1. **Estrarre `LogAnalyzerApp`** in `mouldgraph/app.py` — classe completa con
   costruttore, metodi di parsing e rendering.
2. **Aggiornare `main.py`** per istanziare `mouldgraph.app.LogAnalyzerApp`
   invece del monolite.
3. **Test end-to-end** — confronto output PDF e CSV tra monolite e package.
4. **Bundle PyInstaller** — build e test del file `.exe` con il nuovo entry point.
5. **Archiviare il monolite** — spostare `log_analyzer_desktop_live.py` in
   `archive/` una volta validato il package.
