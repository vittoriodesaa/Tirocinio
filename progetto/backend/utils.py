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

class JobBatchOutput(BaseModel):
    job_id: str
    processed_sources: int
    passed_sources: int
    flagged_sources: int
    failed_sources: int
    average_quality_score: float
    ready_for_planning: bool
    sources: List[SourceOutputOverview]