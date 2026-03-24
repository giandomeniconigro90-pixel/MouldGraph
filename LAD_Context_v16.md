# LogAnalyzer Desktop — Contesto Completo per Nuova Chat

**Data ultimo aggiornamento:** 23 marzo 2026  
**Versione corrente del file:** `log_analyzer_desktop_live.py` (6979 righe)  
**Linguaggio:** Python 3.10+ · CustomTkinter · Matplotlib  
**Piattaforma target:** Windows 11 · PyInstaller  
**Sviluppatore:** Giandomenico Nigro — Bologna, Emilia-Romagna, IT

---

## ⚠️ Regola Operativa Assoluta

Questa regola ha la precedenza su tutto il resto e va rispettata **senza eccezioni**:

> **Sarà l'utente a decidere se e quando applicare una modifica.**  
> L'assistente propone, discute, analizza — ma **non tocca nulla** finché l'utente non dice esplicitamente "procedi" o "modifica".  
> Quando la modifica è autorizzata, si applica **soltanto e unicamente** ciò che è stato richiesto.  
> Qualsiasi altra parte del codice rimane **invariata**.

**Workflow corretto:**
1. Utente descrive il problema o la feature
2. Assistente analizza e propone opzioni (senza scrivere codice)
3. Utente sceglie e dà il via libera esplicito
4. Assistente applica **solo quella modifica**, nient'altro
5. Salva con versione incrementale: `log_analyzer_desktop_live.py` (il file è sempre quello)

**Esempi corretti:**
- ✅ "Modifica solo il tooltip in `_on_motion`"
- ✅ "Cambia solo il colore del pulsante Export PDF"
- ❌ Mai toccare metodi/variabili/layout non menzionati esplicitamente
- ❌ Mai "migliorare", "ottimizzare" o "rifattorizzare" di propria iniziativa

---

## Cos'è LogAnalyzer Desktop

Applicazione desktop Python per l'analisi di dati industriali provenienti da **presse Cannon 5000T** e **Persico 2500T**. Carica file CSV esportati dalle macchine, li visualizza su grafici interattivi e genera report PDF per l'ufficio tecnico.

**Funzionalità principali:**
- Grafici interattivi multi-serie con zoom, pan, crosshair e tooltip
- Confronto visuale tra due CSV sovrapposti (overlay linee tratteggiate)
- Lettura dati live da porta seriale con allarmi configurabili
- Export PNG e PDF con tabelle statistiche adattive al contenuto
- Rilevamento anomalie statistiche (soglia 2.5σ)

---

## Interfaccia — 4 Tab

### Tab: Grafici
Caricamento CSV tramite bottone o drag-drop. Selezione colonna X (tempo/contatore) e serie Y da visualizzare. Grafico matplotlib interattivo incorporato.

### Tab: Dati CSV ← tab principale di sviluppo
Layout pannello sinistro + grafico + toggle bar sotto:

**Pannello sinistro (scrollabile):**
- **Asse X** — dropdown per scegliere la colonna X
- **Serie Y** — checkbox per ogni colonna numerica CSV① con bottoni Tutti/Nessuno
- **Confronto CSV ②** — pannello checkbox indipendente per le colonne del secondo CSV (appare dopo caricamento, con bottoni Tutti/Nessuno)
- **Stati digitali** — visualizzazione colonne booleane
- **Statistiche** — card espandibili per ogni colonna
- **Range personalizzati** — aggiunta di bande colorate sul grafico

**Grafico centrale:**
- Crosshair verticale animato (blit) — segue il cursore in modo continuo (`xm`)
- Tooltip flottante con valori CSV① e CSV② se overlay attivo — snap al dato più vicino (`x_snap`)
- Info bar in cima con tutti i valori correnti

**Toggle bar sotto il grafico:**
- Bottoni colorati per mostrare/nascondere serie CSV①
- Bottoni ② per le serie CSV② attive

**Bottoni in alto:**
- `Apri CSV` — carica CSV principale
- `Confronta CSV` — carica CSV di confronto (overlay ②)
- `Reset Zoom` — ripristina vista
- `Export Report` — salva report .txt
- `Export PNG` — salva grafico corrente (con overlay se attivo)
- `Export PDF` — genera PDF multi-pagina con grafici + tabella statistiche

### Tab: Live Data
Selettore porta seriale + baud rate configurabile. Grafici in tempo reale a finestra scorrevole (MAX_LIVE_POINTS = 500). Configurazione allarmi per soglia min/max per colonna. Badge allarmi e storico scatti in tempo reale.

### Tab: Come usare
Guida utente testuale integrata.

---

## Struttura Dati Interna Chiave

### CSV Principale ①
| Variabile | Tipo | Contenuto |
|---|---|---|
| `self._csv_rows` | `list[dict]` | Righe CSV come dizionari |
| `self._csv_headers` | `list[str]` | Nomi colonne |
| `self._csv_col_meta` | `dict` | `{col: {label, unit, type}}` |
| `self._csv_y_vars` | `dict` | `{col: BooleanVar}` checkbox CSV① |
| `self._csv_colors` | `dict` | `{col: "#RRGGBB"}` colori serie |
| `self._csv_num_cols` | `list` | Colonne numeriche CSV① |

### CSV Confronto ②
| Variabile | Tipo | Contenuto |
|---|---|---|
| `self._csv_rows2` | `list[dict]` | Righe CSV② come dizionari |
| `self._csv_col_meta2` | `dict` | Metadati colonne CSV② |
| `self._csv_y_vars2` | `dict` | `{col: BooleanVar}` **indipendente** da CSV① |
| `self._csv_colors2` | `dict` | Colori distinti (palette rossa/gialla/verde/blu) |
| `self._csv_num_cols2` | `list` | Colonne numeriche CSV② |

### Classe InteractivePlotCanvas
| Variabile | Tipo | Contenuto |
|---|---|---|
| `self._series` | `dict` | `{col: [y_vals]}` dati CSV① |
| `self._overlay_lines` | `dict` | `{col: Line2D}` linee CSV② |
| `self._lines` | `dict` | `{col: Line2D}` linee CSV① |
| `self._cross_v` | `Line2D` | Crosshair verticale animato |
| `self._dot_artists` | `list` | Marcatori punto corrente (blit) |
| `self._tooltip` | `Text` | Tooltip flottante animato |
| `self._xs_num_cache` | `list` | Cache X numerici (invalidata su cambio dati) |
| `self._pan_x_px` | `float` | Pixel X del click iniziale (per pan stabile) |

---

## Metodi Chiave da Conoscere

| Metodo | Classe | Funzione |
|---|---|---|
| `_csv_refresh_plot()` | App | Ridisegna tutto il grafico CSV |
| `_csv_rebuild_series2_panel()` | App | Ricostruisce checkbox pannello CSV② |
| `_csv_sel_all_2(val)` | App | Seleziona/deseleziona tutto CSV② |
| `_csv_open_compare()` | App | Carica CSV di confronto |
| `_csv_export_pdf()` | App | Esporta PDF con overlay se presente |
| `_csv_export_png()` | App | Salva PNG (overlay incluso automaticamente) |
| `generate_plant_pdf()` | modulo | Genera PDF multi-pagina |
| `_plant_pdf_stats_table()` | modulo | Tabella statistica adattiva |
| `_overlay_second_csv()` | InteractivePlotCanvas | Disegna linee tratteggiate CSV② |
| `_on_motion()` | InteractivePlotCanvas | Gestisce hover, crosshair, tooltip |
| `_do_pan()` | InteractivePlotCanvas | Pan stabile con coordinate pixel |
| `export_png()` | InteractivePlotCanvas | Salva figura matplotlib corrente |

---

## Modifiche Implementate (storico completo → v17)

### 1 — Pannello checkbox indipendente CSV② (Opzione D)
Sostituito il vecchio sistema di mapping dinamico CSV1↔CSV2 con un pannello checkbox completamente indipendente.

**Metodi nuovi:** `_csv_rebuild_series2_panel()`, `_csv_sel_all_2(val)`  
**Metodi rimossi:** `_csv_rebuild_mapping()`, `_on_mapping_change()`, `_csv_toggle_overlay_from_map()`, `_csv_toggle_all_overlay_from_map()`  
**Variabili rimosse:** `_csv_col_mapping2`, `_csv_mapping_vars`, `_csv_in_rebuild_mapping`

Il pannello mostra tutti le colonne numeriche di CSV② con checkbox individuali. Lo stato viene preservato se il pannello è ricostruito. I bottoni Tutti/Nessuno sono presenti. Ogni spunta/rimozione chiama `_csv_refresh_plot()`.

---

### 2 — Export PDF con linee overlay ②
`generate_plant_pdf()` ora accetta 4 parametri aggiuntivi opzionali: `rows2`, `cols2`, `colors2`, `col_meta2`. Se presenti, disegna le linee ② (tratteggiate, alpha=0.85) su ogni pagina del PDF dopo le linee principali. Se assenti → comportamento identico a prima.

`_csv_export_pdf()` calcola `_cols2_exp = [c for c, v in self._csv_y_vars2.items() if v.get()]` e passa i dati solo se CSV② è caricato e ha colonne spuntate.

---

### 3 — Tabella statistica adattiva PDF
`_plant_pdf_stats_table()` completamente riscritta. Accetta `stats2`, `cols2`, `col_meta2` opzionali.

**Logica adattiva basata sui nomi:**
- Colonne con **stesso nome** in entrambi i CSV → tabella affiancata verde `Confronto ① vs ②` (N/Min/Max/Media per entrambi)
- Colonne **solo CSV①** → tabella grigia standard (N/Min/Max/Media/σ/Anomalie)
- Colonne **solo CSV②** → tabella blu (N/Min/Max/Media/σ)
- Caso misto → tutte e tre le sezioni presenti
- Senza CSV② → comportamento identico a prima

---

### 4 — Tooltip dual-CSV (Opzione X)
`_on_motion()` aggiornato per mostrare valori ② nel tooltip e info bar.

Dopo il loop sui dati CSV①, itera su `_overlay_lines`:
```python
for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
    if not _ln2.get_visible(): continue
    _lx2 = _ln2.get_xdata(); _ly2 = _ln2.get_ydata()
    _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
    if _li2 < len(_ly2) and _ly2[_li2] is not None:
        tip_lines.append(f"{_c2}②: {float(_ly2[_li2]):.4g}")
```

I dot per CSV② usano marker diamante `"D"` di dimensione 5, con bordo bianco.

---

### 5 — Tooltip con solo overlay ② attivo
Guard iniziale in `_on_motion()` modificato: se `self._series` è vuoto ma `_overlay_lines` ha dati, non ritorna ma usa l'X del primo overlay come ancora. Mostra crosshair, dot diamanti e tooltip con soli dati ②. Se anche `_overlay_lines` è vuoto, chiama `_clear_hover()` e ritorna.

---

### 6 — Fix allineamento dot su serie curve
**Bug:** dot T1 (curva) appariva spostato rispetto al crosshair.  
**Causa:** dot usava `lx[li], ly[li]` dalla Line2D (dati puliti, Nones rimossi) con indice `li` trovato separatamente. Se la serie aveva Nones, `li ≠ idx` del tooltip → disallineamento.  
**Fix:** dot ora usa `(x_snap, ys[idx])` — esattamente lo stesso indice del tooltip.

```python
# PRIMA (bug)
li = min(range(len(lx)), key=lambda i: abs(float(lx[i]) - float(x_snap)))
dot, = ax.plot(float(lx[li]), float(ly[li]), "o", ...)

# DOPO (corretto)
ys = self._series.get(col, [])
if idx >= len(ys) or ys[idx] is None: continue
dot, = ax.plot(x_snap, float(ys[idx]), "o", ...)
```

---

### 7 — PDF tabella statistica: altezza adattiva per dataset piccoli
**Bug:** `_draw_table()` allocava sempre tutto lo spazio verticale disponibile fino a `y=0.06`, indipendentemente dal numero di righe. Con pochi dati le tre sezioni (Confronto, Solo①, Solo②) occupavano pagine separate con grande spazio vuoto.

**Fix:** `avail_h` ora è cappato all'altezza effettivamente necessaria dai dati.

```python
# PRIMA (bug) — riga 1948
avail_h = max(0.05, y_start - 0.06)

# DOPO (corretto)
_row_h = 0.028
_needed = (len(rows_data) + 1) * _row_h
avail_h = min(max(0.05, y_start - 0.06), max(0.06, _needed))
```

Con dataset piccoli le sezioni si compattano in una sola pagina. Con dataset grandi il comportamento è identico a prima.

---

### 8 — Fix dot ② usa x_snap come coordinata X
**Bug:** il marker diamante del CSV② usava `float(_lx2[_li2])` come X — il punto dati reale del CSV②, che può differire da `x_snap` se i due CSV hanno spaziatura X diversa. Ai bordi del grafico la differenza era più visibile.

**Fix:** riga 1253 — `float(_lx2[_li2])` → `x_snap`.

```python
# PRIMA
_d2, = ax1.plot(float(_lx2[_li2]), float(_ly2[_li2]), "D", ...)

# DOPO
_d2, = ax1.plot(x_snap, float(_ly2[_li2]), "D", ...)
```

---

### 9 — Crosshair segue il cursore in continuo (xm)
**Problema:** il crosshair saltava tra i punti dati discreti (`x_snap`), creando la percezione visiva che il dot fosse disallineato dalla linea ai bordi del grafico.

**Fix:** il crosshair usa `xm` (posizione reale del cursore, continua), mentre dot e tooltip restano agganciati a `x_snap` (dato reale più vicino). Modificate 2 righe in `_on_motion()`:

```python
# PRIMA
[x_snap, x_snap], ylim          # init crosshair
self._cross_v.set_xdata([x_snap, x_snap])  # update

# DOPO
[xm, xm], ylim                  # init crosshair
self._cross_v.set_xdata([xm, xm])          # update
```

---

### 10 — Fix pan: zoom involontario durante il drag
**Bug:** trascinando il mouse a destra/sinistra sul grafico, il pan provocava zoom involontario invece di scorrere la vista.

**Causa:** `_do_pan()` calcolava `dx = self._pan_start - event.xdata`. `event.xdata` è in coordinate dati, che cambiano ad ogni `set_xlim()` eseguito durante il drag. La coordinata di riferimento iniziale (`pan_start`) e quella corrente erano in sistemi diversi → `dx` errato → span del grafico modificato.

**Fix:** usare coordinate pixel (stabili, indipendenti da `set_xlim`).

```python
# _on_press — aggiunta 1 riga
self._pan_x_px = event.x

# _do_pan — sostituite 3 righe
# PRIMA
if event.xdata is None or self._pan_xlim is None: return
dx = self._pan_start - event.xdata

# DOPO
if event.x is None or self._pan_xlim is None: return
_bbox = self._ax1.get_window_extent()
if _bbox.width == 0: return
dx = ((self._pan_x_px - event.x) / _bbox.width) * (self._pan_xlim[1] - self._pan_xlim[0])
```

---

## Stato Attuale ✅ / ❌

| Feature | Stato |
|---|---|
| Carica CSV con auto-detect tipo colonna | ✅ |
| Grafico interattivo (zoom, pan, crosshair) | ✅ |
| Pannello checkbox CSV② indipendente | ✅ |
| Overlay linee tratteggiate CSV② | ✅ |
| Toggle bar series CSV① e CSV② | ✅ |
| Tooltip/info bar dual-CSV① + ② | ✅ |
| Tooltip funziona con solo ② visibile | ✅ |
| Dot marcatori allineati con crosshair | ✅ |
| Crosshair fluido (segue cursore in continuo) | ✅ |
| Pan stabile senza zoom involontario | ✅ |
| Export PNG con overlay ② | ✅ |
| Export PDF con linee ② | ✅ |
| Tabella statistica adattiva PDF | ✅ |
| PDF tabella compatta per dataset piccoli | ✅ |
| Live data da seriale con allarmi | ✅ |

---

## Come Iniziare la Nuova Chat

**Allega questi due file:**
1. `log_analyzer_desktop_live.py` (versione v17)
2. Questo documento `LAD_Context_v17.md`

**Primo messaggio:**

> Continuo lo sviluppo di `log_analyzer_desktop_live.py`.  
> Il contesto completo è nel markdown allegato. Leggi tutto prima di rispondere.  
> Regola principale: **decido io quando e se modificare. Ogni modifica tocca solo e unicamente ciò che richiedo.**

---
