from typing import List, Optional,Dict
from enum import Enum
from pydantic import BaseModel, Field


# ENUMERATORI (Stati rigidi per evitare errori di battitura)


class DocumentStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


# 1. CONTRATTI DI INPUT (Ciò che entra nel Document Agent)


class ImportContext(BaseModel):
    campagna_id: Optional[int] = None
    requested_by: Optional[str] = None

class SourceConfig(BaseModel):
    target_language: str = "it"
    min_quality_score: float = 0.75
    emit_markdown: bool = True
    emit_chunks: bool = True

class SourceInput(BaseModel):
    source_id: str
    filename: str
    media_type: str
    source_type_hint: str
    storage_ref: str
    language_hint: Optional[str] = None
    domain_hint: Optional[str] = None
    ocr_required: bool = False
    title_hint: Optional[str] = None
    import_context: Optional[ImportContext] = None

class JobBatchInput(BaseModel):
    job_id: str
    sources: List[SourceInput]
    config: SourceConfig



# 2. CONTRATTI DI OUTPUT (Ciò che esce dal Document Agent)


class SourceProfile(BaseModel):
    source_id: str
    detected_format: str
    document_class: str
    language: str
    has_extractable_text: bool
    ocr_used: bool
    layout_complexity: str
    page_count: int
    conversion_strategy: str

class QualitySignals(BaseModel):
    title_structure: float
    reading_order: float
    noise_level: float
    table_quality: float
    ocr_confidence: float

class Issue(BaseModel):
    severity: str
    type: str
    message: str

class QualityReport(BaseModel):
    source_id: str
    quality_score: float
    status: DocumentStatus
    blocking: bool
    signals: QualitySignals
    issues: List[Issue] = Field(default_factory=list)
    recommended_action: str


class DocumentHierarchy(BaseModel):
    macro_argomenti: List[str] = Field(default_factory=list)
    mappa_sintesi: Dict[str, str] = Field(default_factory=dict)

    
class Chunk(BaseModel):
    chunk_id: str
    source_id: str
    section_path: List[str]
    page_refs: List[str]
    text: str
    token_estimate: int
    quality_score: float

class SourceOutputOverview(BaseModel):
    source_id: str
    status: DocumentStatus
    quality_score: float
    markdown_ref: str
    chunk_index_ref: str
    quality_report_ref: str
    hierarchy_ref: str = ""


# 3. CONTRATTI MICROLEARNING (Planning Agent)


class FonteRiferimento(BaseModel):
    """Punto nel libro convertito dove approfondire l'argomento."""
    percorso: str = Field(description="Percorso relativo nel workspace, es. sources/test_doc_001.md")
    riga_inizio: int = Field(ge=1)
    riga_fine: Optional[int] = Field(default=None, ge=1)


class DomandaQuiz(BaseModel):
    testo: str
    opzioni: List[str] = Field(min_length=2, max_length=5)
    indice_corretto: int = Field(ge=0, description="Indice 0-based della risposta corretta")
    spiegazione: str = ""


class ModuloMicrolearning(BaseModel):
    id: str
    ordine: int = Field(ge=1)
    tipo: str = Field(default="lezione", description="lezione | quiz")
    argomento: str
    sintesi_breve: str = ""
    contenuto: str = Field(
        default="",
        description="Testo didattico completo in italiano (lezioni); vuoto per i quiz",
    )
    fonte: FonteRiferimento
    fonti_aggiuntive: List[FonteRiferimento] = Field(
        default_factory=list,
        description="Altre sorgenti integrate nella stessa lezione (corpus)",
    )
    obiettivi_apprendimento: List[str] = Field(default_factory=list)
    durata_stimata_minuti: int = Field(default=10, ge=1, le=120)
    prerequisiti: List[str] = Field(default_factory=list)
    domande: List[DomandaQuiz] = Field(default_factory=list)


class MicrolearningCourse(BaseModel):
    titolo_corso: str
    lingua: str = "it"
    descrizione: str
    moduli: List[ModuloMicrolearning] = Field(default_factory=list)
    metadati: Dict[str, str] = Field(default_factory=dict)

class JobBatchOutput(BaseModel):
    job_id: str
    processed_sources: int
    passed_sources: int
    flagged_sources: int
    failed_sources: int
    average_quality_score: float
    ready_for_planning: bool
    sources: List[SourceOutputOverview]


# 4. ACQUISIZIONE DOCUMENTO


class AcquisitionRecord(BaseModel):
    source_id: str
    filename: str
    media_type: str
    storage_ref: str
    size_bytes: int
    estensione: str
    ocr_probabile: bool = False
    acquisito_il: str


# 5. PLANNING AGENT (mappa strutturale + punti di taglio)


class SegmentoFonte(BaseModel):
    """Un estratto da una sorgente, usato nei punti di taglio integrati (corpus)."""
    source_id: str
    markdown_sorgente: str
    riga_inizio: int = Field(ge=1)
    riga_fine: int = Field(ge=1)
    titolo_originale: str = ""


class PuntoTaglio(BaseModel):
    id: str
    ordine: int = Field(ge=1)
    titolo: str
    riga_inizio: int = Field(ge=1)
    riga_fine: int = Field(ge=1)
    carico_cognitivo: float = Field(ge=0.0, le=1.0, description="0=leggero, 1=massimo")
    durata_stimata_minuti: int = Field(ge=1, le=180)
    concetti_chiave: List[str] = Field(default_factory=list)
    prerequisiti: List[str] = Field(default_factory=list, description="ID punti taglio prerequisito")
    source_id: Optional[str] = Field(
        default=None,
        description="Sorgente del punto (piano corpus multi-documento)",
    )
    markdown_sorgente: Optional[str] = Field(
        default=None,
        description="Path relativo al markdown, es. sources/manuale.md",
    )
    segmenti_fonte: List[SegmentoFonte] = Field(
        default_factory=list,
        description="Segmenti da più libri da integrare in una sola lezione (corpus)",
    )


class StructuralPlan(BaseModel):
    source_id: str
    livello_struttura: str = Field(description="structured | flat | hybrid | corpus")
    markdown_sorgente: str
    unita_tempo_totale_minuti: int = 0
    punti_taglio: List[PuntoTaglio] = Field(default_factory=list)
    albero_dipendenze: List[Dict[str, str]] = Field(
        default_factory=list,
        description='Archi {"da": "pt_001", "a": "pt_002"}',
    )
    note_pianificazione: str = ""
    sorgenti: List[str] = Field(
        default_factory=list,
        description="Ordine delle source_id unite (piano corpus)",
    )


class CourseSourceEntry(BaseModel):
    source_id: str
    filename: str = ""
    order: int = Field(default=1, ge=1)
    role: str = Field(default="primary", description="primary | supplement | reference")


# 6. SEGMENTATION AGENT (moduli grezzi)


class ModuloGrezzo(BaseModel):
    id: str
    ordine: int
    titolo: str
    testo: str
    token_estimate: int
    riga_inizio: int
    riga_fine: int
    punto_taglio_id: str
    carico_cognitivo: float
    durata_stimata_minuti: int


class SegmentationOutput(BaseModel):
    source_id: str
    moduli: List[ModuloGrezzo] = Field(default_factory=list)
    totale_moduli: int = 0


# 7. VALIDATION AGENT


class ModuleValidation(BaseModel):
    modulo_id: str
    stato: str = Field(description="approved | rejected | needs_review")
    coerenza_logica: float = Field(ge=0.0, le=1.0)
    propedeuticita_ok: bool = True
    messaggi: List[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    source_id: str
    stato_globale: DocumentStatus
    moduli_approvati: int = 0
    moduli_respinti: int = 0
    moduli_in_revisione: int = 0
    validazioni: List[ModuleValidation] = Field(default_factory=list)
    albero_dipendenze_ok: bool = True
    raccomandazione: str = "continue"


class PipelineSourceResult(BaseModel):
    """Esito completo per una sorgente dopo tutta la pipeline."""
    source_id: str
    acquisition: Optional[AcquisitionRecord] = None
    status: DocumentStatus
    quality_score: float
    markdown_ref: str = ""
    plan_ref: str = ""
    raw_modules_ref: str = ""
    validated_modules_ref: str = ""
    validation_ref: str = ""
    chunks_ref: str = ""
    hierarchy_ref: str = ""
    quality_report_ref: str = ""
    microlearning_ref: str = ""
    ready_for_enrichment: bool = False


class FullPipelineOutput(BaseModel):
    job_id: str
    workspace_dir: str
    sources: List[PipelineSourceResult] = Field(default_factory=list)
    microlearning_course_ref: str = ""
    log_summary: List[str] = Field(default_factory=list)