import re
import os
import subprocess
from markitdown import MarkItDown

from typing import Tuple, List
from utils import (
    SourceInput, SourceProfile, QualitySignals, Issue,
    QualityReport, Chunk, DocumentStatus
)

class DocumentAgent:
    def __init__(self):
        # Inizializziamo il jolly Microsoft
        self.md_converter = MarkItDown()

    def elabora_sorgente(self, source: SourceInput) -> Tuple[SourceProfile, str, List[Chunk], QualityReport]:
        """
        Metodo principale dell'agente. Prende in carico il documento ed esegue la pipeline di estrazione.
        """
        # 1 e 2. Routing e Conversione (Simulata)
        raw_markdown = self._estrai_con_markitdown(source.storage_ref)

        # 3. Post-Processing
        clean_markdown = self._normalizza_testo(raw_markdown)

        # 4. Quality Check (Calcolo metriche e routing decisionale)
        signals, issues = self._calcola_segnali_qualita(clean_markdown)
        quality_score = self._calcola_punteggio_globale(signals)
        status, blocking, action = self._determina_stato_handoff(quality_score, issues)

        # 5. Generazione dei 4 Artefatti di Output
        profile = SourceProfile(
            source_id=source.source_id,
            detected_format=source.source_type_hint,
            document_class="text_document",
            language=source.language_hint or "it",
            has_extractable_text=True,
            ocr_used=source.ocr_required,
            layout_complexity="medium",
            page_count=1, # Dato simulato
            conversion_strategy="markitdown_standard"
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

        # Creazione del Chunked Corpus (simulato dividendo per paragrafi)
        chunks = self._crea_chunks(clean_markdown, source.source_id, quality_score)

        return profile, clean_markdown, chunks, report

    # --- METODI INTERNI (L'intelligenza dell'Agente) ---

    def _estrai_con_markitdown(self, source_path: str) -> str:
        """
        Smista il file al tool corretto in base all'estensione e restituisce il Markdown.
        """
        # 1. Estraggo l'estensione del file in minuscolo (es. '.pdf', '.docx')
        _, ext = os.path.splitext(source_path)
        ext = ext.lower()

        try:
            # caso A: pdf
            if ext == '.pdf':
                print(f"Routing: File PDF rilevato. Uso pdf_manuals_to_markdown.py per {source_path}")
                # Lancia il tuo script dei PDF tramite terminale e cattura l'output
                result = subprocess.run(
                    ['python', 'tools/pdf_manuals_to_markdown.py', source_path],
                    capture_output=True, text=True, check=True
                )
                return result.stdout

            #caso B: Word
            elif ext in ['.doc', '.docx']:
                print(f"Routing: File Word rilevato. Uso doc_to_md.py per {source_path}")
                # Lancia il tuo script Word tramite terminale e cattura l'output
                result = subprocess.run(
                    ['python', 'tools/doc_to_md.py', source_path],
                    capture_output=True, text=True, check=True
                )
                return result.stdout

            #caso C: jolly
            else:
                print(f"Routing: Estensione {ext} rilevata. Uso MarkItDown universale.")
                # Usa la libreria MarkItDown per immagini, pptx, excel, ecc.
                result = self.md_converter.convert(source_path)
                return result.text_content
                
        except Exception as e:
            print(f"Errore critico durante l'estrazione di {source_path}: {e}")
            return f"Errore estrazione: {str(e)}"

    def _normalizza_testo(self, raw_md: str) -> str:
        """Ripulisce il markdown grezzo. Fase di post-processing."""
        testo_pulito = raw_md.strip()
        # Esempio: rimuove spazi vuoti multipli
        testo_pulito = re.sub(r'\n{3,}', '\n\n', testo_pulito)
        return testo_pulito

    def _calcola_segnali_qualita(self, test_md: str) -> Tuple[QualitySignals, List[Issue]]:
        """Analizza il testo per capire se markitdown ha fatto un buon lavoro."""
        issues = []
        
        # Simulazione di analisi logica
        ha_titoli = "#" in test_md
        ha_tabelle_rotte = "|---|---|" in test_md and "fuso" in test_md

        signals = QualitySignals(
            title_structure=0.9 if ha_titoli else 0.3,
            reading_order=0.8,
            noise_level=0.9,
            table_quality=0.4 if ha_tabelle_rotte else 0.9,
            ocr_confidence=0.85
        )

        if ha_tabelle_rotte:
            issues.append(Issue(severity="warning", type="table_degradation", message="Rilevate tabelle linearizzate in modo errato."))

        return signals, issues

    def _calcola_punteggio_globale(self, signals: QualitySignals) -> float:
        """Pesa i vari segnali per ottenere un punteggio da 0.0 a 1.0"""
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
        """Applica la logica di business per decidere il destino del documento."""
        if score >= 0.85 and not issues:
            return DocumentStatus.PASS, False, "continue"
        elif score >= 0.60:
            return DocumentStatus.PASS_WITH_WARNINGS, False, "continue_with_warnings"
        else:
            return DocumentStatus.FAIL, True, "require_human_review"

    def _crea_chunks(self, text: str, source_id: str, base_score: float) -> List[Chunk]:
        """Divide il testo pulito in blocchi per il Planning Agent."""
        paragrafi = [p for p in text.split('\n\n') if p.strip()]
        chunks = []
        for i, para in enumerate(paragrafi):
            chunks.append(
                Chunk(
                    chunk_id=f"{source_id}_chunk_{i+1:03d}",
                    source_id=source_id,
                    section_path=["Root"], # Simulato
                    page_refs=[1],
                    text=para,
                    token_estimate=len(para) // 4, # Stima approssimativa
                    quality_score=base_score
                )
            )
        return chunks 