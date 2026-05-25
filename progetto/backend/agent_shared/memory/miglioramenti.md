# Miglioramenti trasversali

Annota qui solo trucchi **validi per qualsiasi corso** (l'agente può appendere righe).

- Leggere sempre `/notes/percorsi_filesystem.md` all'inizio: i path del corso sono `/sources`, `/chunks`, `/reports`, mai path assoluti su disco.
- Dopo un `read_file` fallito su path assoluto, non fare `ls` su `/home` o `/` — usare subito `/sources` e `/reports`.
- `scripts/list_sources.py` + `leggi_gerarchia_documento` una volta bastano prima di `imposta_corso`.
- Preferire `trova_sezione` + `read_file` parziale invece di scorrere tutto il markdown a blocchi.
- I manuali tecnici spesso non hanno `^## 1.` — usare `trova_sezione`, grep per parole chiave o `estrai_titoli_h2.py`.
- Per leggere file: `read_file` su `/sources/...`; per shell usare solo script in `/scripts/` (non `head /sources/...` in execute).
- Non chiamare `leggi_gerarchia_documento` due volte nello stesso round se il risultato è già sufficiente.
