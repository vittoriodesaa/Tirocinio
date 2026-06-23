# Libreria globale Deep Agent

Questa cartella è **condivisa tra tutti i corsi**. Script e markdown qui dentro devono restare
**generici e riusabili** — non salvare piani o appunti legati a un singolo libro/corso.

## Contenuto

| Percorso | Contenuto |
|----------|-----------|
| `/notes/` | Playbook: **percorsi filesystem**, workflow, struttura lezioni, quiz |
| `/scripts/` | Helper da eseguire con `execute` (leggono `WORKSPACE_ROOT` a runtime) |
| `/memory/miglioramenti.md` | Lezioni apprese **trasversali** (cosa ha funzionato in generale) |

## Corso in elaborazione

A ogni run viene impostato `WORKSPACE_ROOT` = cartella del corso su disco.
I materiali del corso corrente sono in sola lettura: `/sources`, `/chunks`, `/reports`, …

## Cosa NON fare qui

- Nessun `plan_corso_X.md`, outline di un libro specifico, dump di capitoli.
- Il piano del corso in corso va in `write_todos` o direttamente nei tool `aggiungi_modulo_corso`.

## Cosa fare per autoincrementarsi

1. Migliora gli script in `/scripts/` quando trovi un pattern ripetibile.
2. Aggiorna `/notes/` se refine workflow o template didattici **validi per ogni corso**.
3. Aggiungi voci brevi in `/memory/miglioramenti.md` (es. pattern path o grep che funzionano su manuali tecnici).

**Ordine di lettura consigliato:** `/notes/percorsi_filesystem.md` → `workflow_microlearning.md` → `struttura_lezione.md`.

## Script nella cartella corso (attenzione)

Il Deep Agent a volte scrive file Python nella **root** di `workspace/{course_id}/` (es. `gen_all.py`) per generare lezioni in batch. Questi script:

- **non** sono parte del codice del server;
- possono usare path assoluti o modificare direttamente `microlearning_course.json`;
- spesso **falliscono** se `write_file` del sandbox non persiste su disco come previsto;
- vanno preferiti i tool ufficiali `aggiungi_modulo_corso` / `aggiungi_quiz_corso`.

Per tool riusabili, aggiungili in **`agent_shared/scripts/`**, non nel workspace del corso.
