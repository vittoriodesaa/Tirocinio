# Home Deep Agent (`/agent/`)

Spazio **personale e persistente** dell'agente per questo corso. Tutto ciò che scrivi qui
resta tra una esecuzione e l'altra (cartella `.agent/` sul disco).

## Struttura

| Percorso virtuale | Uso |
|-------------------|-----|
| `/agent/notes/` | Markdown: piani, outline, bozze, appunti |
| `/agent/scripts/` | Script Python/shell riutilizzabili |
| `/agent/memory/` | Stato e progresso (`progress.md`, decisioni) |

## Tool

- **Lettura corso**: `read_file`, `grep`, `ls` su `/sources`, `/chunks`, `/reports` (sola lettura).
- **Corso finale**: solo `imposta_corso`, `aggiungi_modulo_corso`, `aggiungi_quiz_corso`.
- **Autoincremento**: `write_file` / `edit_file` solo sotto `/agent/`.
- **Script**: `execute` con cwd in questa home (es. `python3 scripts/estrai_titoli.py`).

Variabile d'ambiente nei script: `WORKSPACE_ROOT` = cartella del corso (per leggere sorgenti).

## Buone pratiche

1. Aggiorna `memory/progress.md` dopo ogni fase importante.
2. Salva in `notes/plan.md` la mappa lezioni prima di chiamare i tool corso.
3. Metti in `scripts/` helper ripetibili (estrazione titoli, conteggio parole, ecc.).
4. Non modificare con `write_file` i file fuori `/agent/`.
