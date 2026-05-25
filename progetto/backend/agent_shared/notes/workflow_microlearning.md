# Workflow microlearning (generico)

**Prima di tutto:** leggi `/notes/percorsi_filesystem.md` (path virtuali, cosa evitare).

1. `python3 scripts/list_sources.py` — quali markdown ci sono (evita `ls` su path assoluti).
2. `leggi_gerarchia_documento` con `/reports/*_hierarchy.json` — **una volta**.
3. Opzionale: `python3 scripts/estrai_titoli_h2.py` — mappa sezioni sul sorgente principale.
4. `imposta_corso` — titolo e descrizione in italiano.
5. Per ogni lezione: `trova_sezione` + `read_file` mirato (offset/limit) → `aggiungi_modulo_corso`.
6. Ogni 2–3 lezioni: `aggiungi_quiz_corso` collegato alla lezione precedente (`dopo_modulo_id`).
7. Obiettivo tipico: 8–12 lezioni + almeno 2 quiz; non duplicare l'intero libro.

## Efficienza

- Dopo i passi 1–3, **passa subito** a `imposta_corso` e alle lezioni.
- Per lezione: al massimo 2–4 tool (`trova_sezione` → `read_file` → `aggiungi_modulo_corso`).
- Se il corso è già sufficiente, rispondi in testo senza altri tool.
