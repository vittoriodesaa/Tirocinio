from fastapi import FastAPI, HTTPException
from utils import JobBatchInput, JobBatchOutput, SourceOutputOverview, DocumentStatus

# 1. INIZIALIZZAZIONE FASTAPI
app = FastAPI(
    title="Pipeline Backend Didattico",
    description="Architettura Multi-Agente per la conversione di documenti didattici",
    version="1.0.0"
)

# 2. IL DIRETTORE D'ORCHESTRA (SUPERVISOR)
class Supervisor:
    def __init__(self):
        # In futuro, qui istanzieremo le classi dei nostri agenti (es. self.document_agent = DocumentAgent())
        print("🤖 Supervisor inizializzato. In attesa degli agenti...")

    def _fase_1_motore_logico(self, source_id: str):
        """
        Gestisce la conversione testuale, la mappatura, il taglio e la validazione.
        """
        print(f"  [FASE 1] Avvio Motore Logico per {source_id}...")
        # 1. Deep Agent Documentale (Il Traduttore)
        # 2. Deep Agent Mappatore (Il Cervello)
        # 3. Deep Agent Segmentatore (Il Braccio Armato)
        # 4. Deep Agent Validatore (L'Ispettore Qualità)
        return "moduli_validati_mock"

    def _fase_2_arricchimento_parallelo(self, moduli_validati):
        """
        Smista il lavoro in parallelo ai tre agenti di arricchimento.
        """
        print("  [FASE 2] Avvio Arricchimento in Parallelo...")
        # 5a. Deep Agent Editor (Markdown/UI)
        # 5b. Deep Agent Estrattore (Glossario)
        # 5c. Deep Agent Valutatore (Quiz)
        return "moduli_arricchiti_mock"

    def _assemblaggio_finale(self, job_id: str) -> JobBatchOutput:
        """
        Unisce il lavoro di tutti e restituisce il pacchetto JSON definitivo.
        """
        print("  [ASSEMBLAGGIO] Creazione pacchetto JSON finale...")
        
        # Output simulato basato sui contratti di utils.py
        mock_source_overview = SourceOutputOverview(
            source_id="src_mock_001",
            status=DocumentStatus.PASS,
            quality_score=0.95,
            markdown_ref="/workspace/source/src_mock_001.md",
            chunk_index_ref="/workspace/chunks/src_mock_001_chunks.json",
            quality_report_ref="/workspace/reports/src_mock_001_quality.json"
        )

        return JobBatchOutput(
            job_id=job_id,
            processed_sources=1,
            passed_sources=1,
            flagged_sources=0,
            failed_sources=0,
            average_quality_score=0.95,
            ready_for_planning=True,
            sources=[mock_source_overview]
        )

    def esegui_pipeline(self, job: JobBatchInput) -> JobBatchOutput:
        """
        Metodo principale chiamato dall'endpoint. Mette in moto l'intera fabbrica.
        """
        print(f"\n🚀 NUOVO JOB RICEVUTO: {job.job_id}")
        print(f"📄 Numero di sorgenti da processare: {len(job.sources)}")
        
        for source in job.sources:
            # Eseguiamo la Fase 1 (Motore Logico) in sequenza[cite: 1]
            moduli = self._fase_1_motore_logico(source.source_id)
            
            # Eseguiamo la Fase 2 (Arricchimento) simultaneamente[cite: 1]
            arricchimento = self._fase_2_arricchimento_parallelo(moduli)
        
        # Raccogliamo il lavoro e assembliamo il JSON[cite: 1]
        output_finale = self._assemblaggio_finale(job.job_id)
        return output_finale


# Istanziamo il Supervisor all'avvio dell'app
orchestratore = Supervisor()

# 3. ENDPOINT DI INGRESSO (IL CANCELLO)
@app.post("/api/v1/process-job", response_model=JobBatchOutput)
async def avvia_processo_documentale(job_input: JobBatchInput):
    """
    Riceve un batch di documenti e avvia la pipeline del Supervisor.
    Grazie a 'JobBatchInput', FastAPI bloccherà automaticamente qualsiasi 
    richiesta che non rispetta rigorosamente i contratti che abbiamo definito.
    """
    try:
        # Passiamo il pacchetto JSON validato al nostro Orchestratore
        risultato = orchestratore.esegui_pipeline(job_input)
        return risultato
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno del Supervisor: {str(e)}")

# Per eseguire l'applicazione dal terminale:
# uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)