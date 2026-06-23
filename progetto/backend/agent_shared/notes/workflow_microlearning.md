# Workflow microlearning (generico)

**Prima di tutto:** leggi `/notes/percorsi_filesystem.md` (path virtuali, cosa evitare).

## Corso multi-documento

Se il corso ha più file in `course.json` → `sources[]`, il planning produce anche `reports/corso_plan.json`: i `punti_taglio` vengono accoppiati tra libri per **similarità semantica** (embedding OpenRouter su titolo, concetti ed estratto del segmento). Ogni punto con `segmenti_fonte[]` (2+ libri) va fuso in **una sola lezione**.

1. `python3 scripts/list_sources.py` — quali markdown ci sono (evita `ls` su path assoluti).
2. `leggi_gerarchia_documento` con `/reports/*_hierarchy.json` — **una volta**.
3. Opzionale: `python3 scripts/estrai_titoli_h2.py` — mappa sezioni sul sorgente principale.
4. `imposta_corso` — titolo e descrizione in italiano.
5. Per ogni lezione: leggi **tutti** i `segmenti_fonte` del punto corrente in `corso_plan.json` (se presenti), poi `aggiungi_modulo_corso` con `fonti_aggiuntive` per i segmenti extra.
6. Ogni 2–3 lezioni: `aggiungi_quiz_corso` collegato alla lezione precedente (`dopo_modulo_id`).
7. Obiettivo: coprire la maggior parte dei `punti_taglio` del piano (tipicamente decine di lezioni, non ~10).
   Con più documenti le lezioni sono **integrate** (un punto = un racconto che collega i libri), non alternate per libro.

## Efficienza

- Dopo i passi 1–3, **passa subito** a `imposta_corso` e alle lezioni.
- Per lezione: al massimo 2–4 tool (`trova_sezione` → `read_file` → `aggiungi_modulo_corso`).
- Se il corso è già sufficiente, rispondi in testo senza altri tool.
