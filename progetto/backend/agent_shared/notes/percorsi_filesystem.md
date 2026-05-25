# Percorsi e filesystem (OBBLIGATORIO)

Leggi questo file **prima** di `ls`, `read_file`, `grep` o `execute` sul corso.

## Due radici diverse

| Radice | Cosa contiene |
|--------|----------------|
| `/`, `/notes`, `/scripts`, `/memory` | Libreria **globale** (condivisa tra tutti i corsi) |
| `/sources`, `/chunks`, `/reports`, `/uploads` | Materiale del **corso corrente** (sola lettura) |

A ogni run, `WORKSPACE_ROOT` (variabile d'ambiente) punta alla cartella del corso su disco.
I tool dominio (`leggi_gerarchia_documento`, `trova_sezione`, `leggi_indice_chunks`, …) risolvono i path **relativi al corso**.

## VIETATO: path assoluti sul disco

Non usare mai path come:

- `/home/.../workspace/ko2/sources/ko2.md`
- Path completi copiati da messaggi di errore

Usa **sempre** path virtuali del corso:

| Azione | Path corretto (esempi) |
|--------|-------------------------|
| Leggere il libro | `/sources/{source_id}.md` |
| Gerarchia | `/reports/{source_id}_hierarchy.json` |
| Chunk | `/chunks/{source_id}_chunks.json` |
| grep / glob | `/sources/...`, `/reports/...` |

Forme accettate: con o senza slash iniziale (`sources/ko2.md` ≡ `/sources/ko2.md`).

Se `read_file` su un path assoluto restituisce *not found*:

1. **Non** esplorare `/home`, `/`, la cartella del backend o path fuori dal corso.
2. Passa subito a `ls /sources`, `ls /reports` e ai path della tabella sopra.

## Esplorazione minima (3–4 tool, poi produzione)

Prima di `imposta_corso`:

1. `python3 scripts/list_sources.py` **oppure** un solo `ls` su `/sources` e `/reports`.
2. `leggi_gerarchia_documento` con `/reports/*_hierarchy.json` — **una volta**.
3. Opzionale: `leggi_indice_chunks` o `python3 scripts/estrai_titoli_h2.py`.
4. `imposta_corso` → ciclo lezioni.

Non ripetere `leggi_gerarchia_documento` se l'hai già usato nello stesso round.

## grep e titoli nel manuale

Molti manuali **non** hanno titoli `^## 1.` o `^## 2.`:

- Usano prefissi tipo `## ▌NOME SEZIONE`
- L'indice è nel frontmatter, non in H2 numerati

Strategia:

1. **`trova_sezione`** con titolo testuale (es. `"Sync & MIDI"`, `"Power Supply"`).
2. **`grep`** con parole chiave del capitolo, non solo regex numerate.
3. **`scripts/estrai_titoli_h2.py`** per la mappa rapida.
4. **`read_file`** con `offset` e `limit` dopo `trova_sezione`.

## execute vs read_file

`execute` non ha come directory di lavoro il workspace del corso.

- Usa gli script in `/scripts/` (leggono `WORKSPACE_ROOT`).
- **Non** assumere che `head /sources/foo.md` o `grep` nel shell funzionino.
- Per leggere testo: **`read_file`** su `/sources/foo.md`.

## RIPRESA corso

- Non rifare esplorazione lunga né `imposta_corso`.
- Aggiungi solo lezioni/quiz mancanti (1–3 tool per modulo).
- Path sempre virtuali come sopra.
