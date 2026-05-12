import re
import os
import subprocess
from markitdown import MarkItDown
from typing import Tuple, List
from pydantic import BaseModel, Field
import json

# LangChain/Groq setup
from langchain_groq import ChatGroq

from utils import (
    SourceInput, SourceProfile, QualitySignals, Issue,
    QualityReport, Chunk, DocumentStatus
)
from dotenv import load_dotenv
load_dotenv()


class RoutingDecision(BaseModel):
    extractor: str = Field(
        description="L'estrattore da usare. Valori ammessi rigorosi: 'pdf_script' (solo per PDF), 'word_script' (solo per doc/docx), 'markitdown' (per pptx, epub, immagini, txt, md, html)."
    )
# Schema LLM per i singoli difetti trovati
class LLMIssue(BaseModel):
    severity: str = Field(description="Obbligatorio: 'warning' o 'critical'")
    type: str = Field(description="Es: 'table_degradation', 'gibberish', 'missing_formatting'")
    message: str = Field(description="Breve descrizione del problema rilevato")

# Schema LLM per la pagella finale (Cantiere 3)
class LLMQualityEvaluation(BaseModel):
    title_structure: float = Field(description="Punteggio da 0.0 a 1.0", ge=0.0, le=1.0)
    reading_order: float = Field(description="Punteggio da 0.0 a 1.0", ge=0.0, le=1.0)
    noise_level: float = Field(description="Punteggio da 0.0 a 1.0 (1.0 = testo pulito)", ge=0.0, le=1.0)
    table_quality: float = Field(description="Punteggio da 0.0 a 1.0", ge=0.0, le=1.0)
    ocr_confidence: float = Field(description="Punteggio da 0.0 a 1.0", ge=0.0, le=1.0)
    issues: List[LLMIssue] = Field(default_factory=list)

class DocumentAgent:
    def __init__(self):
        # Fallback per formati generici
        self.md_converter = MarkItDown()
        
        # Init LLM (Groq) - Temp 0 per precisione nel routing e nel reporting
        self.llm = ChatGroq(
            model="llama3-8b-8192",
            temperature=0,
            max_tokens=1024
        )
    def _estrai_testo_con_routing(self, source: SourceInput) -> str:
        # Prompt routing per l'LLM basato su metadati
        prompt = f"""
        Analizza i metadati del file e restituisci l'estrattore corretto.
        Path: {source.storage_ref}
        Type hint: {source.source_type_hint}
        """
        
        # Binding schema Pydantic per output JSON garantito
        router = self.llm.with_structured_output(RoutingDecision)
        
        try:
            # Chiamata LLM e parsing
            decision = router.invoke(prompt)
            print(f"Routing LLM: {decision.extractor.upper()} per {source.storage_ref}")
            
            # Esecuzione condizionale basata su decisione LLM
            if decision.extractor == 'pdf_script':
                result = subprocess.run(
                    ['python', 'tools/pdf_manuals_to_markdown.py', source.storage_ref],
                    capture_output=True, text=True, check=True
                )
                return result.stdout
                
            elif decision.extractor == 'word_script':
                result = subprocess.run(
                    ['python', 'tools/doc_to_md.py', source.storage_ref],
                    capture_output=True, text=True, check=True
                )
                return result.stdout
                
            else:
                # Fallback universale per tutti gli altri formati
                result = self.md_converter.convert(source.storage_ref)
                return result.text_content
                
        except Exception as e:
            print(f"Errore critico estrazione su {source.storage_ref}: {e}")
            return f"Errore estrazione: {str(e)}"
    
    def _calcola_segnali_qualita(self, test_md: str) -> Tuple[QualitySignals, List[Issue]]:
        # Campionamento stratificato: inizio, centro, fine
        lunghezza = len(test_md)
        if lunghezza < 6000:
            campione = test_md
        else:
            inizio = test_md[:2000]
            centro = test_md[lunghezza//2 - 1000 : lunghezza//2 + 1000]
            fine = test_md[-2000:]
            campione = f"--- INIZIO ---\n{inizio}\n\n--- CENTRO ---\n{centro}\n\n--- FINE ---\n{fine}"

        # Prompt per l'ispettore LLM
        prompt = f"""
        Agisci da ispettore qualità dati. Analizza questo campione di markdown estratto da un file.
        Valuta la formattazione, il rumore OCR e la presenza di tabelle rotte o testo incomprensibile.
        Restituisci metriche precise.
        
        CAMPIONE TESTO:
        {campione}
        """
        
        # Binding output strutturato
        ispettore = self.llm.with_structured_output(LLMQualityEvaluation)
        
        try:
            # Invocazione LLM
            valutazione = ispettore.invoke(prompt)
            print("Ispezione LLM completata con successo.")
            
            # Mapping dell'output LLM sulle classi utils.py native
            signals = QualitySignals(
                title_structure=valutazione.title_structure,
                reading_order=valutazione.reading_order,
                noise_level=valutazione.noise_level,
                table_quality=valutazione.table_quality,
                ocr_confidence=valutazione.ocr_confidence
            )
            
            issues = [
                Issue(severity=i.severity, type=i.type, message=i.message) 
                for i in valutazione.issues
            ]
            
            return signals, issues
            
        except Exception as e:
            print(f"Errore ispettore LLM: {e}")
            # Fallback pessimistico per evitare blocchi pipeline
            return QualitySignals(0.5, 0.5, 0.5, 0.5, 0.5), [Issue(severity="critical", type="llm_failure", message=str(e))]
        



    def _normalizza_testo(self, raw_md: str) -> str:
        # Pulisce il markdown grezzo e normalizza gli a capo
        testo_pulito = raw_md.strip()
        testo_pulito = re.sub(r'\n{3,}', '\n\n', testo_pulito)
        return testo_pulito

    def _calcola_punteggio_globale(self, signals: QualitySignals) -> float:
        # Media pesata dei segnali di qualità
        pesi = {
            'title_structure': 0.3,
            'reading_order': 0.3,
            'noise_level': 0.1,
            'table_quality': 0.2,
            'ocr_confidence': 0.1
        }
        score = (
            signals.title_structure * pesi['title_structure'] +
            signals.reading_order * pesi['reading_order'] +
            signals.noise_level * pesi['noise_level'] +
            signals.table_quality * pesi['table_quality'] +
            signals.ocr_confidence * pesi['ocr_confidence']
        )
        return round(score, 2)

    def _determina_stato_handoff(self, score: float, issues: List[Issue]) -> Tuple[DocumentStatus, bool, str]:
        # Soglie per definire se il doc passa o serve review manuale
        if score >= 0.85 and not issues:
            return DocumentStatus.PASS, False, "continue"
        elif score >= 0.60:
            return DocumentStatus.PASS_WITH_WARNINGS, False, "continue_with_warnings"
        else:
            return DocumentStatus.FAIL, True, "require_human_review"
        

        
    def elabora_sorgente(self, source: SourceInput) -> Tuple[SourceProfile, str, List[Chunk], QualityReport]:
        # 1. Routing ed estrazione via LLM
        
        raw_markdown = self._estrai_testo_con_routing(source)

        # 2. Normalizzazione testo
        clean_markdown = self._normalizza_testo(raw_markdown)

        # 3. Ispezione semantica a campione via LLM
        signals, issues = self._calcola_segnali_qualita(clean_markdown)
        quality_score = self._calcola_punteggio_globale(signals)
        status, blocking, action = self._determina_stato_handoff(quality_score, issues)

        # Stima pagine: ~2000 caratteri per pagina standard se non fornito
        estimated_pages = max(1, len(clean_markdown) // 2000)

        # --- LEZIONE 6: CREAZIONE FRONTMATTER YAML ---
        # Formattiamo le issue per il file YAML
        if issues:
            yaml_issues = "\n".join([f'  - "{i.message}"' for i in issues])
        else:
            yaml_issues = '  - "Nessun difetto rilevato"'

        # Costruzione della stringa YAML (occhio all'indentazione a sinistra)
        yaml_frontmatter = f"""---
source_id: "{source.source_id}"
filename: "{os.path.basename(source.storage_ref)}"
document_class: "text_document"
language: "{source.language_hint or 'it'}"
conversion_strategy: "llm_routed"
quality_score: {quality_score}
issues_detected:
{yaml_issues}
page_count: {estimated_pages}
---

"""
        # Appiccichiamo il frontmatter in cima al testo pulito
        clean_markdown_con_yaml = yaml_frontmatter + clean_markdown

        # 4. Assemblaggio payload (Profile e Report restano identici)
        profile = SourceProfile(
            source_id=source.source_id,
            detected_format=source.source_type_hint,
            document_class="text_document",
            language=source.language_hint or "it",
            has_extractable_text=True,
            ocr_used=source.ocr_required,
            layout_complexity="medium",
            page_count=estimated_pages,
            conversion_strategy="llm_routed"
        )

        report = QualityReport(
            source_id=source.source_id,
            quality_score=quality_score,
            status=status,
            blocking=blocking,
            signals=signals,
            issues=issues,
            recommended_action=action
        )

        # Generazione vettori (usiamo il testo SENZA YAML per non sporcare i chunk)
        chunks = self._crea_chunks(clean_markdown, source.source_id, quality_score)

        # Restituiamo il markdown CON il frontmatter YAML per il Planning Agent
        return profile, clean_markdown_con_yaml, chunks, report
    

    
    def _crea_chunks(self, text: str, source_id: str, base_score: float) -> List[Chunk]:
        # Split base su doppi a capo con pulizia stringhe vuote
        paragrafi = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []
        
        for i, para in enumerate(paragrafi):
            # Stima token grezza: ~1.3 token per parola
            num_words = len(para.split())
            token_est = int(num_words * 1.3)
            
            chunks.append(
                Chunk(
                    chunk_id=f"{source_id}_chunk_{i+1:03d}",
                    source_id=source_id,
                    section_path=["Document"],
                    page_refs=[1], # Placeholder: richiede tracking da parser
                    text=para,
                    token_estimate=token_est,
                    quality_score=base_score
                )
            )
        return chunks
    

    def elabora_batch(self, batch_input: JobBatchInput, workspace_dir: str = "workspace") -> JobBatchOutput:
        """
        Prende un intero lotto di documenti, li elabora uno ad uno, salva gli output su disco
        e compila la "pagella" aggregata del job.
        """
        # 1. Prepara le cartelle fisiche dove salveremo i file
        os.makedirs(f"{workspace_dir}/sources", exist_ok=True)
        os.makedirs(f"{workspace_dir}/chunks", exist_ok=True)
        os.makedirs(f"{workspace_dir}/reports", exist_ok=True)

        processed = 0
        passed = 0
        flagged = 0
        failed = 0
        total_score = 0.0
        
        overviews = []

        # 2. Ciclo principale sulle sorgenti
        for source in batch_input.sources:
            print(f"\n--- Inizio elaborazione: {source.source_id} ---")
            try:
                # Chiamiamo il nostro "operaio specializzato"
                profile, md_text, chunks, report = self.elabora_sorgente(source)
                
                # 3. Salvataggio su disco
                # Markdown pulito (con YAML frontmatter integrato)
                md_path = f"{workspace_dir}/sources/{source.source_id}.md"
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(md_text)
                    
                # Chunks in formato JSON
                chunks_path = f"{workspace_dir}/chunks/{source.source_id}_chunks.json"
                with open(chunks_path, "w", encoding="utf-8") as f:
                    json.dump([c.model_dump() for c in chunks], f, indent=2, ensure_ascii=False)
                    
                # Report Qualità in formato JSON
                report_path = f"{workspace_dir}/reports/{source.source_id}_quality.json"
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)
                
                # 4. Aggiorniamo i contatori per le statistiche aggregate
                processed += 1
                total_score += report.quality_score
                
                if report.status == DocumentStatus.PASS:
                    passed += 1
                elif report.status == DocumentStatus.PASS_WITH_WARNINGS:
                    flagged += 1
                else:
                    failed += 1
                    
                # 5. Generiamo l'overview per questo singolo file
                overview = SourceOutputOverview(
                    source_id=source.source_id,
                    status=report.status,
                    quality_score=report.quality_score,
                    markdown_ref=md_path,
                    chunk_index_ref=chunks_path,
                    quality_report_ref=report_path
                )
                overviews.append(overview)
                
            except Exception as e:
                print(f"Errore gravissimo sul file {source.source_id}: {e}")
                # Se un file si schianta completamente, non rompiamo il batch ma lo segniamo come fallito
                processed += 1
                failed += 1
                overviews.append(SourceOutputOverview(
                    source_id=source.source_id,
                    status=DocumentStatus.FAIL,
                    quality_score=0.0,
                    markdown_ref="",
                    chunk_index_ref="",
                    quality_report_ref=""
                ))

        # 6. Matematica finale per il Job
        avg_score = round(total_score / processed, 2) if processed > 0 else 0.0
        # Il job è pronto per il planning solo se NON ci sono file bloccati/falliti
        ready = failed == 0 and processed > 0
        
        # 7. Restituiamo il pacco completo
        return JobBatchOutput(
            job_id=batch_input.job_id,
            processed_sources=processed,
            passed_sources=passed,
            flagged_sources=flagged,
            failed_sources=failed,
            average_quality_score=avg_score,
            ready_for_planning=ready,
            sources=overviews
        )


if __name__ == "__main__":
    # Test isolato per debug
    print("Init DocumentAgent...")
    agente = DocumentAgent()
    
    # TODO: Mettici un path di un file vero che hai in temp/
    path_file_test = "temp/file_di_prova.pdf" 
    
    test_input = SourceInput(
        source_id="test_doc_001",
        filename="file_di_prova.pdf",   
        media_type="application/pdf",     
        storage_ref=path_file_test,
        source_type_hint="application/pdf",
        language_hint="it",
        ocr_required=False
    )
    
    print(f"Test in corso su: {test_input.storage_ref}")
    
    try:
        # Fa girare tutto il flusso
        profile, testo, chunks, report = agente.elabora_sorgente(test_input)
        
        # Check rapido della tupla in uscita
        print("\n--- OUTPUT ---")
        print(f"PROFILE: Pagine={profile.page_count}, OCR={profile.ocr_used}")
        print(f"TESTO: {len(testo)} chars. Anteprima: {testo[:80]}...")
        print(f"CHUNKS: {len(chunks)} generati.")
        print(f"REPORT: Score={report.quality_score}, Status={report.status.value}")
        
        if report.issues:
            print("Difetti trovati:")
            for issue in report.issues:
                print(f"- {issue.type}: {issue.message}")
                
    except Exception as e:
        print(f"Errore nel test: {e}")