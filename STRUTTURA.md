# Struttura del codice

Fino al commit `a5d62b3` tutta l'app era in un unico file, `log_analyzer_desktop_live.py`
(~7.200 righe). Ora il codice è diviso nel package `mouldgraph/`. Ogni funzione, classe
e metodo è stato spostato **senza modifiche**. È stato verificato confrontando l'albero
sintattico di ogni pezzo con quello del monolite.

## Avvio

```
python log_analyzer_desktop_live.py
```

Il file è rimasto solo come punto di ingresso, e lo usa anche `MouldGraph.spec` per PyInstaller.

## Mappa

| File | Contenuto |
|---|---|
| `mouldgraph/app.py` | `LogAnalyzerApp`: finestra principale, `__init__`, `_build_ui`; compone i mixin dei tab |
| `mouldgraph/tabs/tab_analisi.py` | Tab Analisi log: apertura, filtri, statistiche, timeline, AI, export JSON/CSV |
| `mouldgraph/tabs/tab_siemens.py` | Tab Siemens |
| `mouldgraph/tabs/tab_grafici.py` | Tab Grafici: anteprima, schermo intero, note, generazione PDF |
| `mouldgraph/tabs/tab_csv.py` | Tab CSV: grafico interattivo, confronto, range, anomalie, export |
| `mouldgraph/tabs/tab_live.py` | Tab Live Data: seriale/simulazione, allarmi, multi-grafico, export |
| `mouldgraph/tabs/tab_help.py` | Tab Guida |
| `mouldgraph/plot_canvas.py` | `InteractivePlotCanvas` (grafico interattivo matplotlib) |
| `mouldgraph/widgets.py` | `TimelineCanvas`, `LineChart`, `PumpCanvas` |
| `mouldgraph/csv_parsers.py` | Parser CSV universale e ciclo lungo, serie, interpolazione |
| `mouldgraph/log_analysis.py` | Parsing log testuali, timeline, analisi AI, anomalie, CSV Siemens |
| `mouldgraph/csv_validation.py` | Validazione CSV e riconoscimento profilo |
| `mouldgraph/pdf_plant.py` | Report PDF plant (profili presse/stampi) |
| `mouldgraph/pdf_lamborghini.py` | Report PDF Lamborghini / Persico v8, pacchetti nativi |
| `mouldgraph/pdf_front_firewall.py` | Report PDF Front Firewall e riconoscimento tipo CSV |
| `mouldgraph/constants.py` | Colori e costanti condivise |
| `mouldgraph/serial_support.py` | Supporto opzionale pyserial |
| `mouldgraph/ui_utils.py` | `_isolate_scroll` |

I metodi di un tab si modificano nel file del tab: tutti finiscono comunque in
`LogAnalyzerApp`, quindi `self.` funziona come prima tra un tab e l'altro.

## Test

```
python -m unittest discover -s tests
```

`tests/_app_source.py` ricompone il codice del package come faceva il monolite, così i
test continuano a eseguire il codice reale senza aprire finestre.
