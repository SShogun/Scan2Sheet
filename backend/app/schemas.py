from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DocumentType = Literal["invoice", "ledger", "unknown"]


class WarningItem(BaseModel):
    level: Literal["warning", "error", "info", "success"] = "warning"
    field: str = ""
    message: str


class Confidence(BaseModel):
    overall: float = 0.0


class ImageQualityInfo(BaseModel):
    status: Literal["good", "degraded"] = "good"
    blurred: bool = False
    low_contrast: bool = False
    noisy: bool = False
    orientation_degrees: int = 0
    estimated_skew_degrees: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class ArbitrationInfo(BaseModel):
    field: str = ""
    selected_engine: str = ""
    reason: str = ""
    primary_value: str = ""
    primary_confidence: float = 0.0
    secondary_value: str = ""
    secondary_confidence: float = 0.0


class ProcessingInfo(BaseModel):
    image_quality: ImageQualityInfo | None = None
    preprocessing_applied: list[str] = Field(default_factory=list)
    experimental_ocr_status: Literal[
        "disabled",
        "not_applicable",
        "not_run",
        "no_candidate_crop",
        "abstained",
        "candidate",
        "selected",
        "error",
    ] = "not_applicable"
    experimental_ocr_engine: str = ""
    arbitration: ArbitrationInfo | None = None


class ExtractedRow(BaseModel):
    date: str = ""
    description: str = ""
    debit: str = ""
    credit: str = ""
    balance: str = ""


class InvoiceLineItem(BaseModel):
    description: str = ""
    hsn_code: str = ""
    quantity: str = ""
    unit: str = ""
    rate: str = ""
    amount: str = ""


class Box(BaseModel):
    x: int
    y: int
    w: int
    h: int


class TemplateAnchor(BaseModel):
    id: str
    expected_text: str
    box: Box
    match_threshold: float = 0.8


class TemplateField(BaseModel):
    id: str
    label: str
    box: Box
    type: str = "string"
    regex: str | None = None
    format: str | None = None


class TemplateColumn(BaseModel):
    id: str
    name: str
    x_start: int
    x_end: int
    type: str = "string"


class RowDetection(BaseModel):
    method: str = "line_separator"
    min_row_height: int = 20


class TemplateTable(BaseModel):
    id: str
    label: str
    bounding_box: Box
    row_detection: RowDetection | None = None
    columns: list[TemplateColumn] = Field(default_factory=list)


class ReferenceImage(BaseModel):
    url: str = ""
    width: int
    height: int
    dpi: int = 150


class Template(BaseModel):
    template_id: str | None = None
    name: str
    doc_type: DocumentType
    vendor_name: str = ""
    created_at: str = ""
    reference_image: ReferenceImage
    anchors: list[TemplateAnchor] = Field(default_factory=list)
    fields: list[TemplateField] = Field(default_factory=list)
    tables: list[TemplateTable] = Field(default_factory=list)


class ExtractResponse(BaseModel):
    document_type: DocumentType = "unknown"
    raw_text: str = ""
    fields: dict[str, str] = Field(default_factory=dict)
    rows: list[ExtractedRow] = Field(default_factory=list)
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=Confidence)
    processing: ProcessingInfo = Field(default_factory=ProcessingInfo)
