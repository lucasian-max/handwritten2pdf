"""Agent configuration — settings, preamble, and prompt templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from jinja2 import BaseLoader, Environment

if TYPE_CHECKING:
    from core.config import Settings

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_jinja_env = Environment(loader=BaseLoader())

_SERIALIZABLE_FIELDS = frozenset(
    {
        "model",
        "api_base",
        "temperature",
        "max_tokens",
        "max_retries",
        "context_lines",
        "api_key",
        "mode",
        "pipeline",
        "transcribe_model",
        "author_model",
        "verify_model",
        "verify_rounds",
        "dpi",
        "latex_engine",
        "compile_timeout",
        "output_dir",
        "preamble",
    }
)


DEFAULT_PREAMBLE = (_PROMPTS_DIR / "preamble.tex").read_text(encoding="utf-8")


def _load_prompt(name: str) -> str:
    """Read a prompt template by name (without extension) from the prompts directory."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


@dataclass
class AgentConfig:
    """Configuration for a single pipeline run."""

    # LLM settings
    model: str = "openrouter/google/gemini-3-flash-preview"
    api_base: str | None = None
    temperature: float = 0.1
    max_tokens: int = 16384

    # Conversion mode
    mode: Literal["transcribe", "material"] = "transcribe"

    # Pipeline: one vision call per page, or split roles
    #   transcribe (vision) -> author (text) -> verify (vision, optional)
    pipeline: Literal["single", "split"] = "single"
    transcribe_model: str | None = None  # defaults to `model`
    author_model: str | None = None  # defaults to `model`
    verify_model: str | None = None  # defaults to transcribe_model
    verify_rounds: int = 1  # split pipeline only; 0 disables verification

    # Pipeline settings
    max_retries: int = 3
    context_lines: int = 40

    # Runtime
    api_key: str | None = None
    cdn_api_key: str | None = None

    # Output / preprocessing
    output_dir: Path = Path("./output")
    dpi: int = 300

    # Compiler
    latex_engine: str = "pdflatex"
    compile_timeout: int = 60

    # Document settings (loaded from files)
    preamble: str = field(default_factory=lambda: DEFAULT_PREAMBLE)

    # Prompt templates (raw Jinja2 strings, overridable)
    transcribe_template: str = field(default_factory=lambda: _load_prompt("transcribe"))
    material_template: str = field(default_factory=lambda: _load_prompt("transcribe-material"))
    fix_errors_template: str = field(default_factory=lambda: _load_prompt("fix_errors"))
    transcribe_only_template: str = field(default_factory=lambda: _load_prompt("transcribe-only"))
    author_template: str = field(default_factory=lambda: _load_prompt("author-material"))
    verify_template: str = field(default_factory=lambda: _load_prompt("verify-page"))

    # Metadata
    name: str = "notes2latex"
    version: str = "0.1.0"

    def to_state_dict(self) -> dict:
        """Serialize scalar/path fields for LangGraph state (excludes templates)."""

        def _serialize(val: object) -> object:
            return str(val) if isinstance(val, Path) else val

        return {f: _serialize(getattr(self, f)) for f in _SERIALIZABLE_FIELDS}

    @classmethod
    def from_settings(cls, settings: Settings, **overrides) -> AgentConfig:
        """Build AgentConfig from app Settings with optional per-request overrides."""
        base = {
            "model": settings.model,
            "api_base": settings.api_base,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
            "max_retries": settings.max_retries,
            "context_lines": settings.context_lines,
            "api_key": settings.api_key,
            "mode": settings.mode,
            "pipeline": settings.pipeline,
            "transcribe_model": settings.transcribe_model,
            "author_model": settings.author_model,
            "verify_model": settings.verify_model,
            "verify_rounds": settings.verify_rounds,
            "cdn_api_key": settings.cdn_api_key,
            "output_dir": settings.output_dir,
            "dpi": settings.dpi,
            "latex_engine": settings.latex_engine,
            "compile_timeout": settings.compile_timeout,
        }
        client_overrides = {k: v for k, v in overrides.items() if v is not None}
        if client_overrides.get("api_base") not in (None, settings.api_base):
            # Defense in depth: a client-chosen endpoint never receives the
            # server's API key, even if the request-layer guard is bypassed.
            base["api_key"] = client_overrides.get("api_key")
        base.update(client_overrides)
        if client_overrides.get("api_base") not in (None, settings.api_base):
            # Role models are configured for the server's trusted endpoint; a
            # client-chosen endpoint falls back to the single requested model.
            base["transcribe_model"] = None
            base["author_model"] = None
            base["verify_model"] = None
        return cls(**base)

    def render_transcribe_prompt(self, page_number: int, open_envs: list[str]) -> str:
        """Render the transcription system prompt from stored template."""
        template = _jinja_env.from_string(self.transcribe_template)
        return template.render(page_number=page_number, open_envs=open_envs)

    def render_material_prompt(self, page_number: int, open_envs: list[str]) -> str:
        """Render the material-mode system prompt from stored template."""
        template = _jinja_env.from_string(self.material_template)
        return template.render(page_number=page_number, open_envs=open_envs)

    def render_fix_errors_prompt(self) -> str:
        """Render the fix-errors system prompt from stored template."""
        template = _jinja_env.from_string(self.fix_errors_template)
        return template.render()

    def render_transcribe_only_prompt(self, page_number: int) -> str:
        """Render the faithful transcription prompt (split pipeline, vision stage)."""
        template = _jinja_env.from_string(self.transcribe_only_template)
        return template.render(page_number=page_number)

    def render_author_prompt(
        self, page_number: int, open_envs: list[str], transcription: str
    ) -> str:
        """Render the authoring prompt (split pipeline, text stage)."""
        template = _jinja_env.from_string(self.author_template)
        return template.render(
            page_number=page_number,
            open_envs=open_envs,
            transcription=transcription,
        )

    def render_verify_prompt(self) -> str:
        """Render the verification system prompt (split pipeline, vision stage)."""
        template = _jinja_env.from_string(self.verify_template)
        return template.render()

    def role_models(self) -> dict[str, str]:
        """Resolve the per-role model names, falling back to `model`."""
        transcribe = self.transcribe_model or self.model
        return {
            "transcribe": transcribe,
            "author": self.author_model or self.model,
            "verify": self.verify_model or transcribe,
        }
