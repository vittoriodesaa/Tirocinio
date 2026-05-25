from pipeline.paths import BACKEND_ROOT, LEGACY_TEMP_DIR, UPLOADS_DIR
import re
import os
import subprocess
from pathlib import Path

from markitdown import MarkItDown
from typing import Tuple, List, Optional, Callable, Any
from pydantic import BaseModel, Field, field_validator
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import threading
import time

from pipeline.core.llm_factory import create_chat_model, resolve_llm_max_workers

from pipeline.models.schemas import (
    SourceInput, SourceProfile, QualitySignals, Issue,
    QualityReport, Chunk, DocumentStatus, 
    JobBatchInput, JobBatchOutput, SourceOutputOverview,
    DocumentHierarchy 
)
from dotenv import load_dotenv
load_dotenv(BACKEND_ROOT / ".env")

from pipeline.core.agent_logging import (
    setup_logging,
    phase,
    narrative,
    narrative_llm_batch,
    phase_percent_for,
    LLMUsageAccumulator,
    record_llm_response,
)
import logging as _logging

_technical = _logging.getLogger("pipeline.technical")
logger = _technical  # solo batch / __main__

# Importiamo le funzioni native dai nostri tool
from pipeline.tools.pdf_to_markdown import _convert_one as convert_pdf
from pipeline.tools.doc_to_markdown import convert as convert_word
from pipeline.tools.markdown_analyzer import MarkdownAnalyzer

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

    @field_validator(
        "title_structure", "reading_order", "noise_level",
        "table_quality", "ocr_confidence",
        mode="before",
    )
    @classmethod
    def _clamp_metric(cls, v):
        """L'LLM a volte restituisce valori >1; li normalizziamo prima della validazione."""
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5

# Schema LLM temporaneo per estrarre in sicurezza il riassunto (Cantiere 4 - Strutturati)
class CapitoloSintesi(BaseModel):
    sintesi: str = Field(description="La sintesi densa, strutturata e proporzionale del testo fornito.")

# Schema LLM di transito per estrarre titolo e riassunto (Cantiere 4 - Piatti)
class CarrelloSintesi(BaseModel):
    titolo: str = Field(description="Un titolo breve ed esplicativo inventato per questo blocco di testo.")
    sintesi: str = Field(description="La sintesi densa, strutturata e proporzionale del testo fornito.")


@dataclass
class SourceArtifactPaths:
    """Percorsi su disco per salvataggio incrementale."""
    workspace: Path
    raw_md: Path
    clean_md: Path
    final_md: Path
    chunks_json: Path
    hierarchy_json: Path
    quality_json: Path


@dataclass
class ChunkBuildContext:
    """Stato per assemblare chunk/gerarchia dopo il pool LLM globale."""
    is_flat: bool
    source_id: str
    # Documento piatto: task_id → meta carrello
    flat_carrelli: List[dict] = field(default_factory=list)
    flat_task_ids: List[str] = field(default_factory=list)
    # Documento strutturato
    prepared: List[dict] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)
    strutt_task_to_prep: dict = field(default_factory=dict)
    carrello_task_to_meta: dict = field(default_factory=dict)
    section_carrello_tasks: dict = field(default_factory=dict)


class DocumentAgent:
    def __init__(self):
        # Fallback per formati generici
        self.md_converter = MarkItDown()
        self.llm_usage = LLMUsageAccumulator()
        self.llm, self._model_name, self._llm_provider = create_chat_model()
        self._llm_workers_raw = resolve_llm_max_workers(self._llm_provider)
        self._io_lock = threading.Lock()
        self._paths: Optional[SourceArtifactPaths] = None
        _technical.debug(
            "DocumentAgent init provider=%s model=%s workers=%s",
            self._llm_provider, self._model_name, self._llm_workers_raw,
        )

    def _resolve_workers(self, n_tasks: int) -> int:
        """MAX / all / 0 → una richiesta per worker (tutte in parallelo)."""
        if n_tasks <= 0:
            return 1
        raw = self._llm_workers_raw.lower()
        if raw in ("max", "all", "unlimited", "none", "0", "-1"):
            return n_tasks
        try:
            w = int(raw)
            return n_tasks if w <= 0 else min(w, n_tasks)
        except ValueError:
            return min(12, n_tasks)

    def _setup_artifact_paths(self, workspace_dir: str, source_id: str) -> SourceArtifactPaths:
        base = Path(workspace_dir)
        for sub in ("sources", "chunks", "reports"):
            (base / sub).mkdir(parents=True, exist_ok=True)
        paths = SourceArtifactPaths(
            workspace=base,
            raw_md=base / "sources" / f"{source_id}_raw.md",
            clean_md=base / "sources" / f"{source_id}_clean.md",
            final_md=base / "sources" / f"{source_id}.md",
            chunks_json=base / "chunks" / f"{source_id}_chunks.json",
            hierarchy_json=base / "reports" / f"{source_id}_hierarchy.json",
            quality_json=base / "reports" / f"{source_id}_quality.json",
        )
        self._paths = paths
        return paths

    def _salva_testo(self, path: Path, contenuto: str, label: str) -> None:
        with self._io_lock:
            path.write_text(contenuto, encoding="utf-8")
        narrative(f"Ho salvato {label} sul disco.", percent=phase_percent_for("document_agent", 0.85))

    def _salva_json(self, path: Path, data: Any, label: str) -> None:
        with self._io_lock:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        pass  # salvataggio silenzioso (json intermedi)

    def _parallel_map(
        self,
        items: list,
        fn: Callable,
        *,
        label: str,
        on_complete: Optional[Callable[[Any, Any], None]] = None,
    ) -> list:
        """Esegue fn(item) in parallelo; ritorna risultati nello stesso ordine di items."""
        if not items:
            return []
        n_workers = self._resolve_workers(len(items))
        total = len(items)
        if label == "llm_globale" and total > 0:
            narrative(
                f"Avvio {total} analisi con l'IA "
                f"({'in parallelo' if n_workers >= total else f'max {n_workers} alla volta'}).",
                percent=phase_percent_for("llm_globale", 0.05),
            )
        results: list[Any] = [None] * len(items)
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            future_to_idx = {pool.submit(fn, item): i for i, item in enumerate(items)}
            done = 0
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    narrative(f"Un'analisi IA è fallita: {e}", level="error")
                    raise
                done += 1
                if on_complete:
                    on_complete(idx, results[idx])
                if label == "llm_globale" and (
                    done % max(1, total // 8) == 0 or done == total
                ):
                    narrative_llm_batch(done, total, "analisi del testo")
        return results

    def _esegui_pool_llm(
        self,
        tasks: List[Tuple[str, Callable[[], Any]]],
        *,
        on_task_done: Optional[Callable[[str, Any], None]] = None,
    ) -> dict[str, Any]:
        """Esegue tutte le callable LLM in un unico pool; ritorna {task_id: risultato}."""

        def _run(task: Tuple[str, Callable[[], Any]]) -> Tuple[str, Any]:
            task_id, fn = task
            return task_id, fn()

        pairs = self._parallel_map(
            tasks,
            _run,
            label="llm_globale",
            on_complete=(
                (lambda _i, pair: on_task_done(pair[0], pair[1]))
                if on_task_done
                else None
            ),
        )
        return dict(pairs)

    def _invoke_structured(self, schema: type[BaseModel], prompt: str, operation: str) -> BaseModel:
        """Chiamata LLM unificata con log di durata, token e costo."""
        llm = self.llm.with_structured_output(schema, include_raw=True)
        t0 = time.perf_counter()
        result = llm.invoke(prompt)
        duration = time.perf_counter() - t0

        if isinstance(result, dict) and "parsed" in result:
            parsed = result["parsed"]
            raw = result.get("raw")
        else:
            parsed = result
            raw = None

        record_llm_response(
            self.llm_usage,
            operation=operation,
            model=self._model_name,
            duration_s=duration,
            prompt_chars=len(prompt),
            raw_message=raw,
        )
        return parsed
    def _resolve_extractor(self, source: SourceInput) -> str:
        """Routing deterministico per estensioni note; LLM solo per il resto."""
        path = Path(source.storage_ref)
        ext = path.suffix.lower()
        if ext == ".pdf":
            return "pdf_script"
        if ext in (".doc", ".docx"):
            return "word_script"
        return ""

    def _estrai_testo_con_routing(self, source: SourceInput) -> str:
        path = Path(source.storage_ref)
        try:
            extractor = self._resolve_extractor(source)
            if not extractor:
                prompt = f"""
                Analizza i metadati del file e restituisci l'estrattore corretto.
                Path: {source.storage_ref}
                Type hint: {source.source_type_hint}
                Valori ammessi SOLO: pdf_script, word_script, markitdown.
                """
                decision = self._invoke_structured(
                    RoutingDecision, prompt, "routing_estrattore"
                )
                extractor = decision.extractor
            narrative(f"Uso l'estrattore «{extractor}» per {path.name}.", percent=phase_percent_for("estrazione_testo", 0.3))

            if extractor == 'pdf_script':
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
                narrative(f"PDF letto: circa {len(testo_estratto):,} caratteri estratti.", percent=phase_percent_for("estrazione_testo", 0.9))
                return testo_estratto

            elif extractor == 'word_script':
                testo_estratto = convert_word(path, engine="mammoth")
                narrative(f"Documento Word convertito ({len(testo_estratto):,} caratteri).", percent=phase_percent_for("estrazione_testo", 0.9))
                return testo_estratto

            else:
                result = self.md_converter.convert(source.storage_ref)
                narrative(f"File convertito con MarkItDown ({len(result.text_content):,} caratteri).", percent=phase_percent_for("estrazione_testo", 0.9))
                return result.text_content

        except Exception as e:
            narrative(f"Non sono riuscito a leggere il file: {e}", level="error")
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
        Restituisci metriche precise. Ogni punteggio DEVE essere un numero tra 0.0 e 1.0 (inclusi).
        
        CAMPIONE TESTO:
        {campione}
        """
        
        try:
            valutazione = self._invoke_structured(
                LLMQualityEvaluation, prompt, "ispezione_qualita"
            )
            
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
            narrative(f"Controllo qualità non riuscito: {e}", level="warn")
            # Fallback pessimistico per evitare blocchi pipeline
            return QualitySignals(
                title_structure=0.5,
                reading_order=0.5,
                noise_level=0.5,
                table_quality=0.5,
                ocr_confidence=0.5,
            ), [Issue(severity="critical", type="llm_failure", message=str(e))]
        



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
        

        
    def elabora_sorgente(
        self,
        source: SourceInput,
        workspace_dir: str = "workspace",
    ) -> Tuple[SourceProfile, str, List[Chunk], QualityReport, DocumentHierarchy]:
        self.llm_usage = LLMUsageAccumulator()
        paths = self._setup_artifact_paths(workspace_dir, source.source_id)
        narrative(f"Elaboro il documento «{source.source_id}».", percent=phase_percent_for("document_agent", 0.02))

        with phase("estrazione_testo", source_id=source.source_id, file=source.storage_ref):
            raw_markdown = self._estrai_testo_con_routing(source)
        self._salva_testo(paths.raw_md, raw_markdown, "markdown grezzo (post-estrazione)")

        with phase("normalizzazione", chars=len(raw_markdown)):
            clean_markdown = self._normalizza_testo(raw_markdown)
        self._salva_testo(paths.clean_md, clean_markdown, "markdown normalizzato")

        with phase("analisi_struttura"):
            analisi = MarkdownAnalyzer.analyze(clean_markdown, section_level=2)

        llm_tasks, ctx = self._pianifica_task_llm(
            clean_markdown, analisi, source.source_id,
        )
        llm_tasks.insert(
            0,
            ("ispezione_qualita", lambda: self._calcola_segnali_qualita(clean_markdown)),
        )

        def _flush_hierarchy(ger: DocumentHierarchy) -> None:
            self._salva_json(
                paths.hierarchy_json, ger.model_dump(), "gerarchia (incrementale)",
            )

        def _flush_chunks(chunk_list: List[Chunk]) -> None:
            self._salva_json(
                paths.chunks_json,
                [c.model_dump() for c in chunk_list],
                "chunks (incrementale)",
            )

        with phase("llm_globale", task=len(llm_tasks)):
            risultati_llm = self._esegui_pool_llm(llm_tasks)

        signals, issues = risultati_llm["ispezione_qualita"]
        quality_score = self._calcola_punteggio_globale(signals)
        status, blocking, action = self._determina_stato_handoff(quality_score, issues)
        narrative(
            f"Qualità del testo: {quality_score:.0%} — "
            f"{'tutto ok' if not issues else f'{len(issues)} avvisi'}.",
            percent=phase_percent_for("document_agent", 0.95),
        )

        chunks, gerarchia = self._assembla_chunk_da_risultati(
            risultati_llm, ctx, quality_score,
        )
        _flush_chunks(chunks)
        _flush_hierarchy(gerarchia)

        estimated_pages = max(1, len(clean_markdown) // 2000)
        if issues:
            yaml_issues = "\n".join([f'  - "{i.message}"' for i in issues])
        else:
            yaml_issues = '  - "Nessun difetto rilevato"'

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
        clean_markdown_con_yaml = yaml_frontmatter + clean_markdown
        self._salva_testo(paths.final_md, clean_markdown_con_yaml, "markdown finale (YAML + corpo)")

        profile = SourceProfile(
            source_id=source.source_id,
            detected_format=source.source_type_hint,
            document_class="text_document",
            language=source.language_hint or "it",
            has_extractable_text=True,
            ocr_used=source.ocr_required,
            layout_complexity="medium",
            page_count=estimated_pages,
            conversion_strategy="llm_routed",
        )

        report = QualityReport(
            source_id=source.source_id,
            quality_score=quality_score,
            status=status,
            blocking=blocking,
            signals=signals,
            issues=issues,
            recommended_action=action,
        )
        self._salva_json(paths.quality_json, report.model_dump(), "report qualità")
        self.llm_usage.log_summary()
        narrative(
            f"Documento pronto: {len(chunks)} segmenti e {len(gerarchia.macro_argomenti)} capitoli nell'indice.",
            percent=phase_percent_for("document_agent", 1.0),
        )
        return profile, clean_markdown_con_yaml, chunks, report, gerarchia
    

    
    def _segmenta_carrelli(self, raw_text: str) -> List[dict]:
        """Segmenta testo in carrelli senza chiamate LLM."""
        lines = raw_text.split("\n")
        max_parole = 3000
        carrelli: List[dict] = []
        carrello: List[str] = []
        current_page = 1
        start_page = 1
        parole_nel_carrello = 0
        chunk_counter = 1

        for i, line in enumerate(lines):
            if re.match(r'^[-*_]{3,}$', line.strip()):
                current_page += 1
                continue
            testo_pulito = line.strip()
            if not testo_pulito:
                continue
            carrello.append(testo_pulito)
            parole_nel_carrello += len(testo_pulito.split())
            if parole_nel_carrello >= max_parole or i == len(lines) - 1:
                range_pagine = (
                    f"{start_page}-{current_page}"
                    if start_page != current_page
                    else str(start_page)
                )
                carrelli.append({
                    "counter": chunk_counter,
                    "testo": "\n".join(carrello),
                    "parole": parole_nel_carrello,
                    "page_range": range_pagine,
                })
                chunk_counter += 1
                carrello = []
                parole_nel_carrello = 0
                start_page = current_page
        return carrelli

    def _pianifica_task_llm(
        self,
        clean_markdown: str,
        analisi: dict,
        source_id: str,
    ) -> Tuple[List[Tuple[str, Callable[[], Any]]], ChunkBuildContext]:
        """Raccoglie TUTTE le chiamate LLM (sintesi) in un'unica lista per il pool globale."""
        tasks: List[Tuple[str, Callable[[], Any]]] = []

        if analisi["is_flat"]:
            carrelli = self._segmenta_carrelli(clean_markdown)
            ctx = ChunkBuildContext(
                is_flat=True,
                source_id=source_id,
                flat_carrelli=carrelli,
            )
            for c in carrelli:
                tid = f"carrello_{c['counter']:03d}"
                ctx.flat_task_ids.append(tid)
                testo = c["testo"]
                tasks.append((
                    tid,
                    lambda t=testo: self._chiama_llm_per_sintesi(t),
                ))
            narrative(f"Ho preparato {len(tasks)} analisi per questo documento.", percent=phase_percent_for("document_agent", 0.4))
            return tasks, ctx

        # Documento strutturato
        ctx = ChunkBuildContext(is_flat=False, source_id=source_id)
        sezioni = analisi["sections"]

        for i, sec in enumerate(sezioni):
            titolo = sec["title"]
            testo = sec["raw_content"]
            livello = 2 if re.match(r'^(\d+|[A-Z])\.\d+', titolo) else 1
            token_est = int(len(testo.split()) * 1.3)
            entry = {
                "i": i,
                "titolo": titolo,
                "testo": testo,
                "livello": livello,
                "token_est": token_est,
                "page_range": sec.get("page_range", "1"),
                "delegated": False,
                "sintesi_formattata": None,
            }

            if token_est > 4000:
                entry["delegated"] = True
                carrelli = self._segmenta_carrelli(testo)
                ctx.section_carrello_tasks[i] = []
                for c in carrelli:
                    tid = f"sec_{i:03d}_carrello_{c['counter']:03d}"
                    ctx.section_carrello_tasks[i].append(tid)
                    ctx.carrello_task_to_meta[tid] = (i, c)
                    t = c["testo"]
                    tasks.append((
                        tid,
                        lambda txt=t: self._chiama_llm_per_sintesi(txt),
                    ))
            else:
                tid = f"strutt_{i:03d}"
                ctx.strutt_task_to_prep[tid] = len(ctx.prepared)
                ctx.chunks.append(Chunk(
                    chunk_id=f"{source_id}_chunk_{i+1:03d}",
                    source_id=source_id,
                    section_path=["Document", titolo],
                    page_refs=[entry["page_range"]],
                    text=testo,
                    token_estimate=token_est,
                    quality_score=0.0,
                ))
                tit, txt = titolo, testo
                tasks.append((
                    tid,
                    lambda t=tit, x=txt: (
                        t,
                        self._chiama_llm_per_sintesi_strutturati(t, x),
                    ),
                ))
            ctx.prepared.append(entry)

        narrative(
            f"Documento strutturato: {len(sezioni)} sezioni, {len(tasks)} analisi da fare.",
            percent=phase_percent_for("document_agent", 0.4),
        )
        return tasks, ctx

    def _assembla_chunk_da_risultati(
        self,
        risultati: dict[str, Any],
        ctx: ChunkBuildContext,
        quality_score: float,
    ) -> Tuple[List[Chunk], DocumentHierarchy]:
        """Costruisce chunk e gerarchia dai risultati del pool LLM globale."""

        if ctx.is_flat:
            gerarchia = DocumentHierarchy()
            chunks: List[Chunk] = []
            for tid in ctx.flat_task_ids:
                titolo, sintesi = risultati[tid]
                c = next(x for x in ctx.flat_carrelli if f"carrello_{x['counter']:03d}" == tid)
                if titolo not in gerarchia.macro_argomenti:
                    gerarchia.macro_argomenti.append(titolo)
                gerarchia.mappa_sintesi[titolo] = sintesi
                chunks.append(Chunk(
                    chunk_id=f"{ctx.source_id}_chunk_{c['counter']:03d}",
                    source_id=ctx.source_id,
                    section_path=["Document", titolo],
                    page_refs=[c["page_range"]],
                    text=c["testo"],
                    token_estimate=int(c["parole"] * 1.3),
                    quality_score=quality_score,
                ))
            chunks.sort(key=lambda ch: ch.chunk_id)
            return chunks, gerarchia

        # Strutturato: applica sintesi ai prepared
        for tid, prep_idx in ctx.strutt_task_to_prep.items():
            titolo, sintesi = risultati[tid]
            ctx.prepared[prep_idx]["sintesi_formattata"] = f"**{titolo}**\n{sintesi}"

        for prep_idx, task_ids in ctx.section_carrello_tasks.items():
            parti = []
            sub_chunks: List[Chunk] = []
            for tid in task_ids:
                titolo_c, sintesi_c = risultati[tid]
                _prep_i, c = ctx.carrello_task_to_meta[tid]
                parti.append(f"- **{titolo_c}**: {sintesi_c}")
                sub_chunks.append(Chunk(
                    chunk_id=f"{ctx.source_id}_chunk_{ctx.prepared[prep_idx]['i']+1:03d}_{c['counter']:02d}",
                    source_id=ctx.source_id,
                    section_path=["Document", ctx.prepared[prep_idx]["titolo"], titolo_c],
                    page_refs=[c["page_range"]],
                    text=c["testo"],
                    token_estimate=int(c["parole"] * 1.3),
                    quality_score=quality_score,
                ))
            titolo = ctx.prepared[prep_idx]["titolo"]
            ctx.prepared[prep_idx]["sintesi_formattata"] = (
                f"**{titolo}**\nSintesi spezzettata:\n" + "\n".join(parti)
            )
            ctx.prepared[prep_idx]["sub_chunks"] = sub_chunks

        chunks = list(ctx.chunks)
        for entry in ctx.prepared:
            if entry.get("sub_chunks"):
                chunks.extend(entry["sub_chunks"])

        for ch in chunks:
            ch.quality_score = quality_score

        gerarchia = DocumentHierarchy()
        macro_argomento_corrente: Optional[str] = None
        sintesi_accumulate: List[str] = []

        for entry in ctx.prepared:
            sintesi_formattata = entry.get("sintesi_formattata")
            if not sintesi_formattata:
                continue
            titolo = entry["titolo"]
            livello = entry["livello"]
            if livello == 1:
                if macro_argomento_corrente:
                    gerarchia.macro_argomenti.append(macro_argomento_corrente)
                    gerarchia.mappa_sintesi[macro_argomento_corrente] = "\n\n".join(sintesi_accumulate)
                macro_argomento_corrente = titolo
                sintesi_accumulate = [sintesi_formattata]
            else:
                if not macro_argomento_corrente:
                    macro_argomento_corrente = "Sezioni Iniziali"
                sintesi_accumulate.append(sintesi_formattata)

        if macro_argomento_corrente:
            if macro_argomento_corrente not in gerarchia.macro_argomenti:
                gerarchia.macro_argomenti.append(macro_argomento_corrente)
            gerarchia.mappa_sintesi[macro_argomento_corrente] = "\n\n".join(sintesi_accumulate)

        return chunks, gerarchia

    def _chiama_llm_per_sintesi_strutturati(self, titolo: str, testo: str) -> str:
        """
        Helper per la chiamata LLM (Documenti Strutturati).
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
            risposta = self._invoke_structured(
                CapitoloSintesi, prompt, f"sintesi_strutturata:{titolo[:40]}"
            )
            return risposta.sintesi

        except Exception as e:
            narrative(f"Sintesi non generata per «{titolo[:30]}»: uso testo di riserva.", level="warn")
            # Fallback sicuro in caso di timeout o errore API per non bloccare il batch
            return f"Sintesi non disponibile. Errore durante l'elaborazione del capitolo '{titolo}'."

    def _chiama_llm_per_sintesi(self, testo: str) -> Tuple[str, str]:
        """
        Helper per la chiamata LLM (Documenti Piatti).
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
            risposta = self._invoke_structured(
                CarrelloSintesi, prompt, "sintesi_carrello"
            )
            return risposta.titolo, risposta.sintesi

        except Exception as e:
            narrative(f"Sintesi di un blocco fallita: {e}", level="warn")
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

        logger.info(
            "Batch job=%s | sorgenti=%d | workspace=%s",
            batch_input.job_id, len(batch_input.sources), workspace_dir,
        )

        for source in batch_input.sources:
            logger.info("--- Batch: sorgente %s ---", source.source_id)
            try:
                # Chiamiamo il nostro "operaio specializzato"
                profile, md_text, chunks, report, gerarchia = self.elabora_sorgente(
                    source, workspace_dir=workspace_dir,
                )
                
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
                logger.exception("Errore grave su %s: %s", source.source_id, e)
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
        
        logger.info(
            "Batch completato | job=%s | ok=%d warn=%d fail=%d | score_medio=%.2f",
            batch_input.job_id, passed, flagged, failed, avg_score,
        )
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
    os.chdir(BACKEND_ROOT)
    setup_logging()

    logger.info("Avvio test DocumentAgent")
    agente = DocumentAgent()
    
    test_pdf = LEGACY_TEMP_DIR / "file_di_prova.pdf"
    if not test_pdf.exists():
        test_pdf = UPLOADS_DIR / "file_di_prova.pdf"
    path_file_test = str(test_pdf)
    
    test_input = SourceInput(
        source_id="test_doc_001",
        filename="file_di_prova.pdf",   
        media_type="application/pdf",     
        storage_ref=path_file_test,
        source_type_hint="application/pdf",
        language_hint="it",
        ocr_required=False
    )
    
    workspace_test = str(BACKEND_ROOT / "workspace" / "think_python")
    logger.info("File di test: %s | workspace=%s", test_input.storage_ref, workspace_test)

    try:
        profile, testo, chunks, report, gerarchia = agente.elabora_sorgente(
            test_input, workspace_dir=workspace_test,
        )

        logger.info("--- OUTPUT ---")
        logger.info("PROFILE: pagine=%d | OCR=%s", profile.page_count, profile.ocr_used)
        logger.info("CHUNKS: %d generati", len(chunks))
        logger.info("GERARCHIA: %d capitoli", len(gerarchia.macro_argomenti))
        logger.info("REPORT: score=%.2f | status=%s", report.quality_score, report.status.value)
        logger.info(
            "Artifact in %s: *_raw.md, *_clean.md, *.md, chunks/, reports/",
            workspace_test,
        )

    except Exception as e:
        logger.exception("Errore nel test: %s", e)