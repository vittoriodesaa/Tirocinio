# Pipeline didattica multi-agente

Backend che trasforma libri e documenti (PDF, Word, …) in **corsi microlearning** strutturati: lezioni in markdown, quiz interattivi, grafo del percorso e interfaccia web per avviare o riprendere la pipeline.

Ogni corso ha una cartella dedicata sotto `workspace/{course_id}/` con tutti gli artefatti intermedi e finali.

---

## Indice

1. [Requisiti](#requisiti)
2. [Avvio rapido](#avvio-rapido)
3. [Struttura del progetto](#struttura-del-progetto)
4. [Flusso della pipeline](#flusso-della-pipeline)
5. [Configurazione (.env)](#configurazione-env)
6. [Interfaccia web](#interfaccia-web)
7. [API REST](#api-rest)
8. [Workspace di un corso](#workspace-di-un-corso)
9. [Script da terminale](#script-da-terminale)
10. [Moduli Python (riferimento file)](#moduli-python-riferimento-file)
11. [Sviluppo e test agenti](#sviluppo-e-test-agenti)

---

## Requisiti

- **Python 3.11+** (consigliato 3.12)
- Chiave API **OpenRouter** e/o **Groq** per gli agenti LLM
- Opzionale: **LibreOffice** (`soffice`) per convertire vecchi file `.doc`
- Opzionale: **pandoc** come motore alternativo Word → Markdown

---

## Avvio rapido

### 1. Entra nella cartella backend

```bash
cd progetto/backend
```

### 2. Crea e attiva il virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
```

> Se nel repo esiste già la cartella `vevn/` (nome storico), puoi usarla:  
> `source vevn/bin/activate`

### 3. Installa le dipendenze

```bash
pip install -r requirements.txt
```

### 4. Configura le variabili d'ambiente

```bash
cp .env.example .env
# Modifica .env e inserisci almeno OPENROUTER_API_KEY=...
```

### 5. Avvia il server

```bash
python main.py
```

oppure:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

oppure lo script:

```bash
chmod +x scripts/run_server.sh
./scripts/run_server.sh
```

Apri il browser su **http://127.0.0.1:8000/** — carica un PDF, imposta un `course_id` (es. `mio_corso`) e avvia la pipeline.

> Esegui sempre i comandi dalla root `progetto/backend/` (dove si trovano `main.py` e `.env`), oppure imposta `PYTHONPATH` su quella cartella.

---

## Struttura del progetto

```
progetto/backend/
├── main.py                 # Punto di ingresso (re-export app FastAPI)
├── requirements.txt        # Dipendenze pip
├── .env.example            # Template variabili d'ambiente
├── .env                    # Config locale (NON committare)
│
├── pipeline/               # Codice applicativo Python
│   ├── paths.py            # Percorsi radice (workspace, static, data)
│   ├── api/
│   │   └── app.py          # FastAPI: route REST + mount static
│   ├── config/
│   │   └── settings.py     # Lettura .env e report configurazione
│   ├── core/
│   │   ├── supervisor.py   # Orchestrazione step pipeline
│   │   ├── pipeline_state.py
│   │   ├── agent_logging.py
│   │   ├── workspace_io.py
│   │   ├── course_viewer.py
│   │   └── llm_factory.py
│   ├── models/
│   │   └── schemas.py      # Modelli Pydantic (contratti dati)
│   ├── agents/             # Un agente per step (o sotto-step)
│   │   ├── acquisition_agent.py
│   │   ├── document_agent.py
│   │   ├── planning_agent.py
│   │   ├── segmentation_agent.py
│   │   ├── validation_agent.py
│   │   └── microlearning_agent.py
│   └── tools/              # Librerie di conversione/analisi testo
│       ├── pdf_to_markdown.py
│       ├── doc_to_markdown.py
│       └── markdown_analyzer.py
│
├── scripts/                # CLI eseguibili da terminale
│   ├── run_server.sh
│   ├── convert_pdf.py
│   └── convert_doc.py
│
├── static/                 # Frontend (UI pipeline + esplora corso)
│   ├── index.html
│   ├── css/main.css
│   └── js/app.js
│
├── workspace/              # Output runtime: un sottocartella = un corso
│   ├── think_python/
│   └── soft_skills/
│
├── data/
│   ├── uploads/            # PDF/file di prova da caricare manualmente
│   └── examples/           # Workspace di esempio (ex `esempi/`)
│
└── temp/                   # Legacy: vecchi upload; ancora supportato
```

---

## Flusso della pipeline

```mermaid
flowchart LR
  A[Acquisizione] --> B[Document]
  B --> C[Planning]
  C --> D[Segmentation]
  D --> E[Validation]
  E --> F[Microlearning]
  F --> G[Corso JSON + UI]
```

| Step | Agente | Cosa produce |
|------|--------|----------------|
| **acquisition** | `AcquisitionAgent` | File in `uploads/`, metadati acquisizione |
| **document** | `DocumentAgent` | Markdown, chunk, report qualità, gerarchia |
| **planning** | `PlanningAgent` | Piano strutturale (`*_plan.json`) |
| **segmentation** | `SegmentationAgent` | Moduli grezzi (`*_raw_modules.json`) |
| **validation** | `ValidationAgent` | Moduli validati (`*_validated_modules.json`) |
| **microlearning** | `MicrolearningPlanningAgent` | `reports/microlearning_course.json` (lezioni + quiz) |

Lo **Supervisor** (`pipeline/core/supervisor.py`) coordina gli step, consente la **ripresa** da uno step intermedio e scrive log narrativi in `activity.log`.

---

## Configurazione (.env)

Copia `.env.example` in `.env`. Variabili principali:

| Variabile | Descrizione |
|-----------|-------------|
| `OPENROUTER_API_KEY` | Chiave OpenRouter (provider predefinito se presente) |
| `OPENROUTER_MODEL` | Modello chat (es. `deepseek/deepseek-v4-flash`) |
| `GROQ_API_KEY` | Alternativa Groq |
| `LLM_PROVIDER` | `openrouter` o `groq` (auto se omesso) |
| `LLM_MAX_WORKERS` | Parallelismo chiamate LLM (OpenRouter: default massimo) |
| `LOG_LEVEL` | `DEBUG`, `INFO`, … |
| `VALIDATION_USE_LLM` | `off` / `flagged` / `all` — controllo qualità moduli |
| `MICRO_MIN_CONTENUTO_CHARS` | Lunghezza minima testo lezione |

Dall’UI: pulsante **Configurazione .env** → `GET /api/v1/config` (chiavi mascherate).

---

## Interfaccia web

| File | Ruolo |
|------|--------|
| `static/index.html` | Shell HTML (form upload, pipeline, log, risultati) |
| `static/css/main.css` | Stili (tema scuro, quiz, grafo, explorer) |
| `static/js/app.js` | Logica client: polling log, stato corso, grafo vis.js, quiz con riepilogo in `localStorage` |

Funzionalità principali:

- Selezione corso e visualizzazione step completati / prossimo step
- Avvio pipeline o ripresa da step
- **Esplora corso**: grafo lezioni/quiz, catalogo markdown, quiz con punteggio complessivo
- Avvisi validazione (`PASS_WITH_WARNINGS`)

---

## API REST

Base: `http://127.0.0.1:8000/api/v1`

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/health` | Stato servizio e elenco step |
| GET | `/config` | Configurazione runtime |
| GET | `/courses` | Elenco corsi in `workspace/` |
| GET | `/courses/{id}/status` | Stato pipeline + warnings |
| GET | `/courses/{id}/activity` | Log live (polling) |
| GET | `/courses/{id}/course-view` | JSON per grafo e catalogo UI |
| GET | `/courses/{id}/files` | Elenco file nel workspace |
| POST | `/pipeline/run` | Esecuzione sincrona |
| POST | `/pipeline/run-async` | Esecuzione in background |
| POST | `/courses/{id}/resume` | Ripresa da step |

La home `GET /` serve `static/index.html`.

---

## Workspace di un corso

Esempio: `workspace/think_python/`

```
think_python/
├── course.json              # Metadati corso (id, source_id, file originale)
├── activity.log             # Log narrativo persistente
├── uploads/                 # File caricato + JSON acquisizione
├── sources/                 # Markdown (raw, clean, finale)
├── chunks/                  # Chunk testuali per LLM
├── reports/                 # Piano, qualità, gerarchia, validazione, microlearning
└── modules/                 # Moduli grezzi e validati
```

File chiave finale: **`reports/microlearning_course.json`** — usato da `course_viewer` e dall’UI.

---

## Script da terminale

Tutti vanno lanciati dalla root `progetto/backend/` con il venv attivo.

```bash
# Server
./scripts/run_server.sh

# PDF → Markdown (cartella intera)
python scripts/convert_pdf.py -i data/uploads -o output_md

# Word → Markdown
python scripts/convert_doc.py documento.docx
```

Gli script sono wrapper sottili; la logica è in `pipeline/tools/`.

---

## Moduli Python (riferimento file)

### `pipeline/paths.py`
Costanti per `BACKEND_ROOT`, `WORKSPACE_ROOT`, `STATIC_DIR`, `DATA_DIR`, `ENV_FILE`, percorsi legacy `temp/`.

### `pipeline/api/app.py`
Applicazione **FastAPI**: monta `/static`, espone REST, delega al `Supervisor`.

### `pipeline/config/settings.py`
Legge `.env`, costruisce il report per `/api/v1/config`, integra `llm_factory`.

### `pipeline/core/supervisor.py`
Cuore orchestrazione: `acquisisci_ed_elabora`, `resume_pipeline`, `list_courses`, percorsi workspace.

### `pipeline/core/pipeline_state.py`
Rileva step completati, warning da file validazione/qualità, modello `CoursePipelineStatus`.

### `pipeline/core/agent_logging.py`
Log narrativi in italiano, percentuali, `RunLog` in memoria per polling, scrittura `activity.log`.

### `pipeline/core/llm_factory.py`
Crea modello LangChain (OpenRouter o Groq), rate limiter Groq, parallelismo worker.

### `pipeline/core/workspace_io.py`
`load_json`, `save_json`, lettura righe markdown, ricerca sezioni.

### `pipeline/core/course_viewer.py`
Costruisce payload grafo (nodi lezione/quiz, archi) da `microlearning_course.json`.

### `pipeline/models/schemas.py`
Contratti Pydantic: `SourceInput`, `JobBatchInput`, `MicrolearningCourse`, `ModuloMicrolearning`, `DomandaQuiz`, ecc.

### Agenti (`pipeline/agents/`)

| File | Responsabilità |
|------|----------------|
| `acquisition_agent.py` | Salva upload in `uploads/`, crea `SourceInput` |
| `document_agent.py` | Routing PDF/Word/markitdown, pulizia MD, chunk, qualità LLM |
| `planning_agent.py` | Analisi struttura MD, piano tagli, gerarchia |
| `segmentation_agent.py` | Estrae moduli grezzi dal piano |
| `validation_agent.py` | Regole + LLM opzionale, moduli validati |
| `microlearning_agent.py` | Deep Agent: workspace corso + home `/agent/` (note, script, memoria) |
| `agent_home.py` | Libreria globale `agent_shared/` + mount materiali corso in lettura |

### Tools (`pipeline/tools/`)

| File | Responsabilità |
|------|----------------|
| `pdf_to_markdown.py` | Conversione PDF con pymupdf4llm |
| `doc_to_markdown.py` | Conversione .docx/.doc (mammoth o pandoc) |
| `markdown_analyzer.py` | Statistiche e struttura heading per planning |

---

## Sviluppo e test agenti

Test locale di un agente (dalla root backend, venv attivo):

```bash
PYTHONPATH=. python -m pipeline.agents.document_agent
PYTHONPATH=. python -m pipeline.agents.microlearning_agent
```

Il document agent cerca un PDF di prova in `temp/` o `data/uploads/`.

---

## Note

- **`workspace/`** è in `.gitignore`: i corsi generati restano in locale.
- Non committare **`.env`** (contiene API key).
- Corsi legacy in `temp/workspace` sono ancora visibili come `temp_workspace` se la cartella esiste.
- Gli esempi statici precedenti sono in **`data/examples/`** (prima `esempi/`).

Per domande sull’architettura generale del tirocinio, vedi anche `architettura.pdf` nella root del repository.
