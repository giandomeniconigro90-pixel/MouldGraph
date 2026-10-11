# Live Data: prima prova della riproduzione

Base main: 485f595680ee9e427a85bbf03504e71da337e1aa, inclusa la correzione del grafico ingrandito già provata dall’utente.

## Avvio e ripristino

Scarica lo ZIP del branch fix/live-playback-step1 ed estrailo in una cartella nuova. Avvia AVVIA_PROVA_LIVE.cmd con Python e le dipendenze già usate per la prova del grafico. Non sostituisce né ricompila l’EXE. Per tornare indietro chiudi questa prova e riapri la versione funzionante. Main non viene modificato da questa proposta.

## Cosa provare

1. Apri Live Data, scegli Simulazione CSV e carica uno dei CSV abituali. Attendi CSV pronto. Per questa prova lascia Interp disattivato.
2. Avvia a 1x. Metti in pausa: il conteggio Elaborati e la riproduzione devono fermarsi. Riprendi: deve proseguire dalla posizione raggiunta.
3. Premi Stop durante la riproduzione, anche se il prossimo campione è distante nel tempo. L’interfaccia deve rispondere e il lettore interrompersi; i campioni già in coda possono ancora essere elaborati. La lettura/parsing iniziale di un file molto grande resta non interrompibile: l’app impedisce di sovrapporre un secondo lettore.
4. Riavvia: riparte dall’inizio. Prova MAX e attendi Riproduzione completata; Play torna disponibile. Elaborati mostra il totale; In vista arriva al massimo a 500. Per i CSV long-format una misura temporale raccoglie più parametri: il totale non coincide necessariamente con il numero di righe del file.
5. Ripeti Stop/Play e Pausa/Riprendi. Non devono comparire aggiornamenti duplicati.
6. Cancella durante la lettura: attende l’arresto, azzera e rimane fermo. Premi Play per ripartire.
7. Verifica che il grafico ingrandito già corretto continui a funzionare.

La velocità MAX è limitata dalla capacità di elaborazione dell’interfaccia: la coda aspetta invece di scartare campioni. La vista continua a conservare solo gli ultimi 500 campioni. Non è ancora una registrazione completa della sessione.

## Ancora da affrontare

- Esportazione dell’intera sessione con timestamp: oggi rimangono gli ultimi 500 campioni e mancano i tempi.
- Allarmi su ciascun campione, per non perdere picchi intermedi.
- Interpolazione e aggiornamento di segnali costanti; miglioramenti allo zoom live.
- La seriale fisica non è stata collaudata; questo intervento verifica la riproduzione CSV.

I parser dei CSV industriali e i PDF sono invariati. La vecchia PR #2 non è inclusa.

## Verifiche

14 test automatici: 9 riproduzione CSV e 5 grafico ingrandito. Comando: python -m unittest discover -s tests -v . Usano callback reali, thread Python e Matplotlib Agg; manca il collaudo completo della GUI Windows con i CSV dell’utente.
