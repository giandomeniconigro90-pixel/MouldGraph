# Struttura del codice

Tutta l'app è nel monolite `log_analyzer_desktop_live.py` (~7.200 righe), che **non si
tocca mai**: resta identico a main (`a5d62b3`) e continua a funzionare da solo.

Accanto al monolite c'è il package `mouldgraph/`, con lo stesso codice diviso in moduli.
Ogni funzione, classe e metodo è stato copiato **senza modifiche**. È stato verificato
confrontando l'albero sintattico di ogni pezzo con quello del monolite.

## Avvio

| Versione | Comando |
|---|---|
| Monolite (intatto) | `python log_analyzer_desktop_live.py` |
| Modulare | `python avvia_mouldgraph.py` |

`MouldGraph.spec` costruisce ancora l'exe dal monolite. Per costruire l'exe della
versione modulare:

```
pyinstaller --noconfirm --onefile --windowed --name MouldGraph --collect-all customtkinter --collect-all matplotlib avvia_mouldgraph.py
```

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
