"""Pydantic request/response models for the agent API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from db.models import JobStatus


class ConvertRequest(BaseModel):
    model: str = "openrouter/google/gemini-3-flash-preview"
    api_base: str | None = None
    api_key: str | None = None
    mode: Literal["transcribe", "material"] | None = None
    max_retries: int = 3
    dpi: int = 300
    preamble: str | None = None

    @field_validator("api_base", "api_key", "preamble", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        """Treat blank/whitespace strings as absent so they cannot override
        server configuration (an empty string is not None downstream)."""
        if isinstance(v, str) and not v.strip():
            return None
        return v


class PageInfo(BaseModel):
    page_number: int
    has_content: bool


class PagesResponse(BaseModel):
    total_pages: int
    pages: list[PageInfo]


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    model: str = ""
    mode: str = "transcribe"
    total_pages: int = 0
    created_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    input_filenames: list[str] = []
    has_pdf: bool = False
    has_tex: bool = False
    cdn_urls: dict[str, str] = {}
    editorial_notes: str | None = None


class PageLatexResponse(BaseModel):
    job_id: str
    page_number: int
    latex: str
