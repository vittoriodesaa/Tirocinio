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
        # Inizializzo MarkItDown (il nostro fallback per i formati non coperti)
        self.md_converter = MarkItDown()

    def elabora_sorgente(self, source: SourceInput) -> Tuple[SourceProfile, str, List[Chunk], QualityReport]:
        """
        Cuore dell'agente: prende il file, lo fa digerire agli script e restituisce testo pulito + metriche.
        """
        # 1. Capisce che file è e lo converte in markdown (chiama gli script esterni)
        raw_markdown = self._estrai_con_markitdown(source.storage_ref)

        # 2. Pulizia base del testo grezzo
        clean_markdown = self._normalizza_testo(raw_markdown)

        # 3. Check della qualità: com'è andata l'estrazione?
        signals, issues = self._calcola_segnali_qualita(clean_markdown)
        quality_score = self._calcola_punteggio_globale(signals)
        status, blocking, action = self._determina_stato_handoff(quality_score, issues)

        # 4. Prepara il pacchetto finale per il prossimo agente
        profile = SourceProfile(
            source_id=source.source_id,
            detected_format=source.source_type_hint,
            document_class="text_document",
            language=source.language_hint or "it",
            has_extractable_text=True,
            ocr_used=source.ocr_required,
            layout_complexity="medium",
            page_count=1, # TODO: da implementare il conteggio reale delle pagine
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

        # Taglia il testo in chunk (per ora in modo grezzo sui doppi a capo)
        chunks = self._crea_chunks(clean_markdown, source.source_id, quality_score)

        return profile, clean_markdown, chunks, report

    # --- HELPER METHODS ---

    def _estrai_con_markitdown(self, source_path: str) -> str:
        """
        Capisce l'estensione e lancia lo script giusto tramite terminale.
        """
        # Prendo l'estensione in lower per evitare casini con i case
        _, ext = os.path.splitext(source_path)
        ext = ext.lower()

        try:
            # Sezione PDF
            if ext == '.pdf':
                print(f"Routing: File PDF rilevato. Uso pdf_manuals_to_markdown.py per {source_path}")
                # Lancia lo script batch e si prende l'output da stdout
                result = subprocess.run(
                    ['python', 'tools/pdf_manuals_to_markdown.py', source_path],
                    capture_output=True, text=True, check=True
                )
                return result.stdout

            # Sezione Word
            elif ext in ['.doc', '.docx']:
                print(f"Routing: File Word rilevato. Uso doc_to_md.py per {source_path}")
                # Idem come sopra ma per i .docx
                result = subprocess.run(
                    ['python', 'tools/doc_to_md.py', source_path],
                    capture_output=True, text=True, check=True
                )
                return result.stdout

            # Fallback per tutto il resto
            else:
                print(f"Routing: Estensione {ext} rilevata. Passo la palla a MarkItDown universale.")
                result = self.md_converter.convert(source_path)
                return result.text_content
                
        except Exception as e:
            print(f"Errore critico durante l'estrazione di {source_path}: {e}")
            return f"Errore estrazione: {str(e)}"

    def _normalizza_testo(self, raw_md: str) -> str:
        """Toglie un po' di sporco dal markdown appena estratto."""
        testo_pulito = raw_md.strip()
        # Via gli a capo esagerati
        testo_pulito = re.sub(r'\n{3,}', '\n\n', testo_pulito)
        return testo_pulito

    def _calcola_segnali_qualita(self, test_md: str) -> Tuple[QualitySignals, List[Issue]]:
        """Cerca di capire se il testo fa schifo o è usabile."""
        issues = []
        
        # TODO: logica provvisoria, da raffinare
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
        """Fa la media pesata dei segnali di qualità."""
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
        """Decide se il file passa il turno o serve un controllo umano."""
        if score >= 0.85 and not issues:
            return DocumentStatus.PASS, False, "continue"
        elif score >= 0.60:
            return DocumentStatus.PASS_WITH_WARNINGS, False, "continue_with_warnings"
        else:
            return DocumentStatus.FAIL, True, "require_human_review"

    def _crea_chunks(self, text: str, source_id: str, base_score: float) -> List[Chunk]:
        """Spezza il malloppo in chunk più piccoli (fondamentale per i vettori dopo)."""
        paragrafi = [p for p in text.split('\n\n') if p.strip()]
        chunks = []
        for i, para in enumerate(paragrafi):
            chunks.append(
                Chunk(
                    chunk_id=f"{source_id}_chunk_{i+1:03d}",
                    source_id=source_id,
                    section_path=["Root"], # TODO: da sistemare l'alberatura vera
                    page_refs=[1],
                    text=para,
                    token_estimate=len(para) // 4, # Hack veloce per stimare i token
                    quality_score=base_score
                )
            )
        return chunks