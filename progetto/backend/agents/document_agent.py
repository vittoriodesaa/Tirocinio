import re
import os
import subprocess
from markitdown import MarkItDown
from typing import Tuple, List
from pydantic import BaseModel, Field
import json
import time

# LangChain/Groq setup
from langchain_groq import ChatGroq

from utils import (
    SourceInput, SourceProfile, QualitySignals, Issue,
    QualityReport, Chunk, DocumentStatus, 
    JobBatchInput, JobBatchOutput, SourceOutputOverview,
    DocumentHierarchy 
)
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path

# Importiamo le funzioni native dai nostri tool
from tools.pdf_manuals_to_markdown import _convert_one as convert_pdf
from tools.doc_to_md import convert as convert_word
from tools.markdown_analyzer import MarkdownAnalyzer

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

# Schema LLM temporaneo per estrarre in sicurezza il riassunto (Cantiere 4 - Strutturati)
class CapitoloSintesi(BaseModel):
    sintesi: str = Field(description="La sintesi densa, strutturata e proporzionale del testo fornito.")

# Schema LLM di transito per estrarre titolo e riassunto (Cantiere 4 - Piatti)
class CarrelloSintesi(BaseModel):
    titolo: str = Field(description="Un titolo breve ed esplicativo inventato per questo blocco di testo.")
    sintesi: str = Field(description="La sintesi densa, strutturata e proporzionale del testo fornito.")

class DocumentAgent:
    def __init__(self):
        # Fallback per formati generici
        self.md_converter = MarkItDown()
        
        # Init LLM (Groq) - Temp 0 per precisione nel routing e nel reporting
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
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
                # FASE 1: Chiamata diretta in RAM alla funzione PDF
                testo_estratto = convert_pdf(
                    Path(source.storage_ref),
                    header=False, 
                    footer=False, 
                    show_progress=False, 
                    page_separators=True, 
                    dpi=150, 
                    ocr_language="ita+eng", 
                    front_matter=False, 
                    write_images=False, 
                    image_path=None
                )
                return testo_estratto
                
            elif decision.extractor == 'word_script':
                # FASE 1: Chiamata diretta in RAM alla funzione Word
                testo_estratto = convert_word(Path(source.storage_ref), engine="mammoth")
                return testo_estratto
                
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
        analisi = MarkdownAnalyzer.analyze(clean_markdown, section_level=2)
        
        if analisi["is_flat"]:
            print("-> Rilevato documento piatto. Esecuzione chunking di fallback.")
            # Aggiunto 'gerarchia'
            chunks, gerarchia = self._crea_chunks_piatti(clean_markdown, source.source_id, quality_score)
        else:
            print(f"-> Rilevato documento strutturato ({analisi['section_count']} sezioni). Esecuzione chunking gerarchico.")
            # Aggiunto 'gerarchia'
            chunks, gerarchia = self._crea_chunks_strutturati(analisi["sections"], source.source_id, quality_score)

        # Restituiamo il markdown CON il frontmatter YAML e la NUOVA gerarchia per il Planning Agent
        return profile, clean_markdown_con_yaml, chunks, report, gerarchia
    

    
    def _crea_chunks_strutturati(self, sezioni: List[dict], source_id: str, base_score: float):
        """
        Punto 3a: Usa la gerarchia nativa dell'Analyzer e genera la sintesi LLM.
        Restituisce (List[Chunk], DocumentHierarchy).
        """
        chunks = []
        gerarchia = DocumentHierarchy() # Il nostro nuovo cassetto
        
        for i, sec in enumerate(sezioni):
            titolo = sec["title"]
            testo = sec["raw_content"]
            range_pagine = sec.get("page_range", "1")
            token_est = int(len(testo.split()) * 1.3)
            
            
            # Se il capitolo supera i 4000 token, è troppo grosso per Groq e per il DB vettoriale.
            if token_est > 4000:
                print(f"   [Routing Interno] Capitolo '{titolo}' troppo grande ({token_est} token). Delego al carrello...")
                # Chiamiamo l'altro metodo. Lui taglierà e farà tutto il lavoro sporco.
                sub_chunks, sub_gerarchia = self._crea_chunks_piatti(testo, source_id, base_score)
                
                # Uniamo il suo lavoro al nostro contenitore principale
                chunks.extend(sub_chunks)
                gerarchia.macro_argomenti.extend(sub_gerarchia.macro_argomenti)
                gerarchia.mappa_sintesi.update(sub_gerarchia.mappa_sintesi)
                continue # Saltiamo il resto del ciclo, per questo capitolo abbiamo finito!
            

            # 1. Creazione del Chunk (Già fixato nella Fase 3)
            chunk = Chunk(
                chunk_id=f"{source_id}_chunk_{i+1:03d}",
                source_id=source_id,
                section_path=["Document", titolo],
                page_refs=[range_pagine], 
                text=testo,                             
                token_estimate=token_est,          
                quality_score=base_score            
            )
            chunks.append(chunk)
            
            # 2. Popolamento dell'Indice Globale
            if titolo not in gerarchia.macro_argomenti:
                gerarchia.macro_argomenti.append(titolo)
                
            # 3. Chiamata all'IA (Solo per la sintesi)
            sintesi = self._chiama_llm_per_sintesi_strutturati(titolo, testo)
            gerarchia.mappa_sintesi[titolo] = sintesi
            
            
            # Pausa matematica: 1 secondo ogni 100 token (limite Groq 6000/minuto), con minimo 3 secondi
            tempo_pausa = max(3, int(token_est / 100))
            print(f"   [Pacing] Attesa di {tempo_pausa} sec per il cooldown di Groq...")
            time.sleep(tempo_pausa)
            
            
        return chunks, gerarchia

    def _chiama_llm_per_sintesi_strutturati(self, titolo: str, testo: str) -> str:
        """
        Helper reale per la chiamata a Groq (Documenti Strutturati).
        Usa lo structured output di LangChain per estrarre la sintesi.
        """
        #print(f"   [LLM] Generazione sintesi reale per il capitolo: {titolo}...")
        
        prompt = (
            f"Sei un analista esperto. Leggi il capitolo seguente intitolato '{titolo}'.\n"
            "Genera un riassunto denso e strutturato, la cui lunghezza sia proporzionale "
            "al volume del testo che hai appena letto.\n"
            "ATTENZIONE: DEVI RESTITUIRE ESATTAMENTE ED ESCLUSIVAMENTE IL FORMATO JSON RICHIESTO. "
            "NON AGGIUNGERE TESTO FUORI DAL JSON. NON USARE TAG COME <function>. "
            "POPOLA SOLO ED ESCLUSIVAMENTE LA CHIAVE 'sintesi'.\n\n"
            f"TESTO:\n{testo}"
        )
        
        try:
            # Vincoliamo l'LLM a rispondere usando la nostra micro-classe Pydantic
            llm_strutturato = self.llm.with_structured_output(CapitoloSintesi)
            
            # Invocazione del modello
            risposta = llm_strutturato.invoke(prompt)
            
            # Restituiamo direttamente la stringa estratta dal campo del modello
            return risposta.sintesi
            
        except Exception as e:
            print(f"   [Errore LLM] Impossibile generare la sintesi per {titolo}: {e}")
            # Fallback sicuro in caso di timeout o errore API per non bloccare il batch
            return f"Sintesi non disponibile. Errore durante l'elaborazione del capitolo '{titolo}'."

    def _crea_chunks_piatti(self, raw_text: str, source_id: str, base_score: float):
        """
        Punto 3b: Motore semantico a carrelli per documenti senza struttura.
        Restituisce (List[Chunk], DocumentHierarchy).
        """
        chunks = []
        gerarchia = DocumentHierarchy() # Il nostro nuovo cassetto
        
        lines = raw_text.split('\n')
        carrello = []
        
        # Contatori spaziali e di volume
        current_page = 1
        start_page = 1
        parole_nel_carrello = 0
        MAX_PAROLE = 3000  # Soglia del carrello: circa 8-10 pagine di testo
        chunk_counter = 1
        
        import re
        
        for i, line in enumerate(lines):
            # 1. Rilevatore di pagina spaziale
            if re.match(r'^[-*_]{3,}$', line.strip()):
                current_page += 1
                continue
                
            testo_pulito = line.strip()
            if not testo_pulito:
                continue
                
            # 2. Riempimento del carrello
            carrello.append(testo_pulito)
            parole_nel_carrello += len(testo_pulito.split())
            
            # 3. Svuotamento carrello (se pieno o se è finita la lettura del documento)
            is_last_line = (i == len(lines) - 1)
            
            if parole_nel_carrello >= MAX_PAROLE or is_last_line:
                testo_carrello = "\n".join(carrello)
                
                # --- CHIAMATA ALL'IA (Llama/Groq) ---
                # Chiamiamo un metodo di appoggio per ottenere il JSON col Titolo e la Sintesi dinamica
                titolo, sintesi = self._chiama_llm_per_sintesi(testo_carrello)
                
                # 4. Archiviazione Globale (Compilazione di utils.py)
                if titolo not in gerarchia.macro_argomenti:
                    gerarchia.macro_argomenti.append(titolo)
                gerarchia.mappa_sintesi[titolo] = sintesi
                
                # 5. Formattazione Spaziale e Creazione Chunk
                # 5. Formattazione Spaziale e Creazione Chunk
                token_est = int(parole_nel_carrello * 1.3)
                range_pagine = f"{start_page}-{current_page}" if start_page != current_page else str(start_page)
                
                chunk = Chunk(
                    chunk_id=f"{source_id}_chunk_{chunk_counter:03d}",
                    source_id=source_id,
                    section_path=["Document", titolo], 
                    page_refs=[range_pagine],          
                    text=testo_carrello,
                    token_estimate=token_est,
                    quality_score=base_score
                )
                chunks.append(chunk)
                
                
                tempo_pausa = max(3, int(token_est / 100))
                print(f"   [Pacing] Attesa di {tempo_pausa} sec per il cooldown di Groq (Carrello)...")
                time.sleep(tempo_pausa)
                # ---------------------------------------------
                
                # 6. Reset del carrello per il prossimo blocco
                chunk_counter += 1
                carrello = []
                parole_nel_carrello = 0
                start_page = current_page # Il prossimo blocco parte dalla pagina attuale
                
        return chunks, gerarchia

    def _chiama_llm_per_sintesi(self, testo: str) -> Tuple[str, str]:
        """
        Helper reale per la chiamata a Groq (Documenti Piatti).
        Usa lo structured output di LangChain per farsi inventare Titolo e Sintesi.
        """
        #print("   [LLM] Generazione titolo e sintesi per il carrello di testo...")
        
        prompt = (
            "Sei un analista esperto. Leggi il testo seguente.\n"
            "Inventa un 'titolo' breve che riassuma l'argomento trattato, e scrivi una 'sintesi' densa "
            "la cui lunghezza sia proporzionale al volume del testo che hai appena letto.\n"
            "ATTENZIONE: DEVI RESTITUIRE ESATTAMENTE ED ESCLUSIVAMENTE IL FORMATO JSON RICHIESTO. "
            "NON AGGIUNGERE TESTO FUORI DAL JSON. NON USARE TAG COME <function>. "
            "POPOLA ENTRAMBE LE CHIAVI 'titolo' E 'sintesi'.\n\n"
            f"TESTO:\n{testo}"
        )
        
        try:
            # Vincoliamo l'LLM a rispondere con i due campi richiesti (Titolo + Sintesi)
            llm_strutturato = self.llm.with_structured_output(CarrelloSintesi)
            
            # Invocazione del modello
            risposta = llm_strutturato.invoke(prompt)
            
            # Restituiamo la tupla pulita al chiamante
            return risposta.titolo, risposta.sintesi
            
        except Exception as e:
            print(f"   [Errore LLM] Impossibile generare dati per il carrello: {e}")
            # Fallback sicuro per non far crashare lo script
            return "Argomento Non Riconosciuto", "Sintesi non disponibile a causa di un errore dell'API."
    

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
                profile, md_text, chunks, report, gerarchia = self.elabora_sorgente(source)
                
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

                hierarchy_path = f"{workspace_dir}/reports/{source.source_id}_hierarchy.json"
                with open(hierarchy_path, "w", encoding="utf-8") as f:
                    json.dump(gerarchia.model_dump(), f, indent=2, ensure_ascii=False)
                
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
                    quality_report_ref=report_path,
                    hierarchy_ref=hierarchy_path
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
        profile, testo, chunks, report, gerarchia = agente.elabora_sorgente(test_input)
        
        # --- NOVITÀ 1: Salviamo il file Markdown ---
        with open("temp/anteprima_markdown.md", "w", encoding="utf-8") as f:
            f.write(testo)
            
        # --- NOVITÀ 2: Salviamo la mappa dei riassunti generati da Groq! ---
        with open("temp/gerarchia_test.json", "w", encoding="utf-8") as f:
            json.dump(gerarchia.model_dump(), f, indent=2, ensure_ascii=False)
            
        # Check rapido della tupla in uscita
        print("\n--- OUTPUT ---")
        print(f"PROFILE: Pagine={profile.page_count}, OCR={profile.ocr_used}")
        print(f"CHUNKS: {len(chunks)} generati.")
        print(f"GERARCHIA: {len(gerarchia.macro_argomenti)} capitoli indicizzati.")
        print(f"REPORT: Score={report.quality_score}, Status={report.status.value}")
        print("\n  File Markdown salvato in: temp/anteprima_markdown.md")
        print("  Indice Riassunti salvato in: temp/gerarchia_test.json")
                
    except Exception as e:
        print(f"Errore nel test: {e}")