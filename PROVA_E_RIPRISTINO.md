# Prova Live Data e ritorno alla versione precedente

La base di questa modifica è il commit `681ad79c19c46d2b9d29358298978d73886b108a` di `main`.
La copia recuperabile è nel branch `backup/main-before-live-fixes-2026-10-11`.
La versione corretta si trova nel branch `fix/live-data-reliability`.

## Metodo consigliato su Windows: due cartelle separate

1. Conserva la cartella e l'EXE MouldGraph che usi attualmente.
2. Su GitHub seleziona `fix/live-data-reliability`, poi **Code → Download ZIP**.
3. Estrai lo ZIP in una nuova cartella, ad esempio `MouldGraph-Prova-Live`.
4. Apri `AVVIA_PROVA_LIVE.cmd`. Esegue il sorgente direttamente, senza wrapper ricorsivi.
   Usa il Python già presente nel PC. Se mancano dipendenze, l'errore rimane visibile;
   il comando non installa nulla e non crea un nuovo EXE.
5. Prova copie dei tuoi CSV con Play, Pausa, Riprendi, Stop e velocità MAX.
6. Controlla temperature, forza e vuoto, anche nella vista Multi, ed esporta il CSV.

**Per tornare indietro:** chiudi la prova e riapri il tuo EXE precedente.
Non occorre disinstallare nulla o modificare GitHub. Anche se la prova non si apre,
la cartella originale resta utilizzabile.

Se non hai più la cartella precedente, scarica uno ZIP dal branch di backup.
Per ora la modifica è proposta in una pull request separata da `main`.
L'EXE precedente non contiene queste correzioni: dopo la prova positiva andrà ricompilato.

## Per chi usa Git

Con modifiche locali già salvate o committate:

```powershell
git fetch origin
git switch fix/live-data-reliability
```

Per ritornare esattamente alla base precedente:

```powershell
git switch backup/main-before-live-fixes-2026-10-11
```

Se Git segnala modifiche locali, fermati e conservale: non usare reset forzati.

## Comportamenti corretti

- Pause/Stop interrompono le attese; la fine del CSV ripristina i comandi.
- MAX attende spazio nella coda: non elimina campioni del CSV per velocizzare il grafico.
- La vista mantiene fino a 500 campioni. L'intera sessione acquisita è archiviata in un
  file temporaneo su disco ed è disponibile nell'export CSV fino a nuova sessione/chiusura.
- Prima di sostituire o chiudere una sessione appare la scelta Esporta/Scarta/Annulla.
  Il file temporaneo non è un backup permanente né un recupero garantito dopo un crash:
  per conservare i dati usa Esporta.
- L'export include `_ts` (data/ora ISO), `_sim_t` (secondi) o `_sim_i` (indice).
  I nomi originali dei segnali vengono mantenuti. PNG/PDF live rappresentano la vista,
  mentre il CSV contiene tutti i campioni acquisiti della sessione.
- Gli allarmi controllano ogni campione, anche quelli fra due aggiornamenti del grafico.
- Linee collega campioni reali; non aggiunge misure sintetiche. I valori mancanti restano
  mancanti e interrompono la linea. Disattiva Linee per vedere soltanto i punti.
- Le selezioni ridisegnano anche da fermo. Lo zoom resta stabile; Torna al live riattiva
  la vista dei campioni più recenti.
- In modalità seriale Pausa congela la vista, mentre registrazione/allarmi continuano.
  Una seriale più veloce della coda può ancora saturarla: il contatore Scartati lo segnala.
- In Multi la pausa di un pannello ferma solo quel pannello. Il flusso degli altri continua.

## Verifiche e limiti

Test automatici sul codice reale con CSV sintetici numerici, datetime e long-format,
coda molto piccola, pause/stop, completamento, picchi brevi, export oltre 500 campioni,
selezione e rendering Matplotlib senza schermo.

```powershell
py -3 -m unittest discover -s tests -v
```

Le dipendenze dei test grafici sono NumPy e Matplotlib. Per l'app servono inoltre
CustomTkinter e Tkinter; pyserial è opzionale, necessario per la sorgente seriale.
Non sono stati cambiati i parser industriali o i modelli PDF della scheda Grafici.
Restano necessari una prova dell'interfaccia su Windows e il confronto con i tuoi CSV
reali: i difetti dei parser segnalati nell'analisi precedente non sono inclusi qui.
La precedente proposta sul mirino della finestra Grafici è separata da questa modifica.
