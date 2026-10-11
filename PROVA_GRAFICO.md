# Prova del grafico ingrandito

Base: allegato funzionante ripristinato su main, commit 03b337c1938b69e2ab7b9179b52c9d843863047a. Solo il metodo _grafici_open_fullscreen è modificato. CSV, PDF, Live Data e dati delle curve rimangono quelli della base.

## Avvio

1. Scarica lo ZIP del branch fix/enlarged-chart-stable ed estrailo in una nuova cartella. Conserva la cartella e l’EXE abituali.
2. Avvia AVVIA_PROVA_GRAFICO.cmd. Richiede Python con le dipendenze già usate dall’app (customtkinter, matplotlib, numpy e Pillow per le funzioni che lo usano). Il launcher non installa nulla e non aggiorna l’EXE.
3. In alternativa, dal terminale della nuova cartella: `py -3 log_analyzer_desktop_live.py`.

## Verifica pratica

1. Carica un CSV abituale nella sezione Grafici e apri il grafico Temperature ingrandito.
2. Seleziona Crosshair, ingrandisci con la rotella e sposta il mouse fuori dal grafico, sulla toolbar e fuori dalla finestra. Rientra: limiti, curve e mirino devono restare corretti senza reset.
3. Ripeti con Tooltip, Snap e Completo. Non devono restare tracce o apparire porzioni della vista precedente.
4. Usa Zoom a rettangolo e Sposta nella toolbar. Durante lo strumento il mirino è sospeso; clicca di nuovo lo stesso strumento per disattivarlo e leggere i valori.
5. Prova Home, indietro/avanti della toolbar e ridimensionamento della finestra; poi esci e rientra col mouse.
6. Premi Vista completa: ripristina entrambi gli assi e disattiva Zoom/Sposta. Esc nasconde il mirino.
7. Chiudi e riapri il grafico; verifica anche Forza o Vuoto.

Crosshair e Completo indicano valori interpolati fra campioni; Tooltip e Snap identificano i campioni. Fuori dall’intervallo di una serie non viene prolungato il suo ultimo valore.

## Ripristino

Chiudi la prova e riapri il vecchio EXE o la cartella funzionante. Main non viene modificato da questa prova. La base esatta è scaricabile da https://github.com/giandomeniconigro90-pixel/MouldGraph/archive/03b337c1938b69e2ab7b9179b52c9d843863047a.zip . Non unire le vecchie PR #1 e #2, basate sul main precedente.

## Verifiche tecniche

`python -m unittest discover -s tests -v`

I test eseguono i callback reali con Matplotlib Agg e confrontano anche i pixel dopo uscita/rientro. Non sostituiscono il collaudo della GUI Tk su Windows con i CSV reali.
