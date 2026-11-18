"""LangGraph pipeline — the agentic generate→compile→fix loop."""

import asyncio
import json
import os
import shutil
from pathlib import Path

from langgraph.graph import END, StateGraph
from tenacity import retry, stop_after_attempt, wait_exponential

from agent.config import AgentConfig
from agent.progress import EventType, ProgressCallback, ProgressEvent, emit, set_progress_callback
from agent.state import PipelineState, get_config
from agent.utils.editorial_notes import NO_NOTES_PLACEHOLDER, split_editorial_notes
from agent.utils.page_markers import prepend_page_marker
from agent.utils.text import strip_code_fences
from clients.cdn.client import upload_file
from clients.llm.client import acompletion
from compiler.compiler import compile_latex
from core.logger import get_logger
from document.preprocessing import load_pages
from document.processing import assemble_document, open_environments, strip_preamble_from_body

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain LLM functions
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def transcribe_page(
    image_b64: str,
    system_prompt: str,
    config: AgentConfig,
    context_latex: str = "",
) -> str:
    """Send a page image to the VLM and return LaTeX source."""
    user_content: list[dict] = []

    if context_latex:
        tail = "\n".join(context_latex.splitlines()[-config.context_lines :])
        user_content.append(
            {
                "type": "text",
                "text": (
                    "Here is the LaTeX body from previous pages (last "
                    f"{config.context_lines} lines):\n```latex\n{tail}\n```\n"
                    "Continue typesetting the next page shown in the image."
                ),
            }
        )

    user_content.extend(
        [
            {
                "type": "text",
                "text": "Typeset the handwritten math notes in this image into LaTeX body content.",
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64}",
                    "detail": "high",
                },
            },
        ]
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    text = await acompletion(
        model=config.model,
        messages=messages,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        api_key=config.api_key,
        api_base=config.api_base,
    )
    return strip_code_fences(text)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def fix_latex(
    latex_source: str,
    errors: list[dict],
    system_prompt: str,
    config: AgentConfig,
) -> str:
    """Send broken LaTeX + errors to LLM, return fixed LaTeX."""
    error_text = "\n".join(
        f"- Line {e.get('line', '?')}: {e['message']}"
        + (f" (context: {e['context']})" if e.get("context") else "")
        for e in errors
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"The following LaTeX source has compilation errors:\n\n"
                f"```latex\n{latex_source}\n```\n\n"
                f"Errors:\n{error_text}\n\n"
                f"Return ONLY the corrected complete LaTeX source."
            ),
        },
    ]

    text = await acompletion(
        model=config.model,
        messages=messages,
        temperature=0.0,
        max_tokens=config.max_tokens,
        api_key=config.api_key,
        api_base=config.api_base,
    )
    return strip_code_fences(text)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def preprocess_node(state: PipelineState) -> dict:
    return {
        "page_index": 0,
        "retry_count": 0,
        "base_body": "",
        "accumulated_body": "",
        "current_page_latex": "",
        "compiler_success": False,
        "errors": [],
        "editorial_notes": {},
        "output_tex_path": "",
        "output_pdf_path": "",
    }


async def generate_latex_node(state: PipelineState) -> dict:
    config = get_config(state)
    page_idx = state["page_index"]
    total = len(state["pages"])
    page_b64 = state["pages"][page_idx]

    logger.info("Generating LaTeX for page %d/%d", page_idx + 1, total)
    await emit(
        ProgressEvent(
            event_type=EventType.PAGE_GENERATING,
            page=page_idx + 1,
            total_pages=total,
            message=f"Generating LaTeX for page {page_idx + 1}/{total}",
        )
    )

    accumulated_body = state.get("accumulated_body", "")
    open_envs = open_environments(accumulated_body) if accumulated_body else []

    render_prompt = (
        config.render_material_prompt
        if config.mode == "material"
        else config.render_transcribe_prompt
    )
    system_prompt = render_prompt(
        page_number=page_idx + 1,
        open_envs=open_envs,
    )

    generated = await transcribe_page(
        image_b64=page_b64,
        system_prompt=system_prompt,
        config=config,
        context_latex=accumulated_body,
    )

    latex, notes = split_editorial_notes(generated)
    if config.mode == "material" and not notes:
        # Make a silent omission visible instead of losing the record.
        notes = NO_NOTES_PLACEHOLDER
    latex = strip_preamble_from_body(latex)
    new_body = prepend_page_marker(page_idx + 1, latex, accumulated_body)

    return {
        "current_page_latex": latex,
        "base_body": accumulated_body,
        "accumulated_body": new_body,
        "editorial_notes": {page_idx + 1: notes},
        "retry_count": 0,
    }


async def compile_latex_node(state: PipelineState) -> dict:
    config = get_config(state)
    page_idx = state["page_index"]
    total = len(state["pages"])
    body = state["accumulated_body"]

    await emit(
        ProgressEvent(
            event_type=EventType.PAGE_COMPILING,
            page=page_idx + 1,
            total_pages=total,
            message=f"Compiling page {page_idx + 1}/{total}",
        )
    )

    # Temporarily close any environments still open at the end of the body
    open_envs = open_environments(body)
    if open_envs:
        closing_tags = "\n".join(rf"\end{{{env}}}" for env in reversed(open_envs))
        body = body + "\n" + closing_tags

    full_doc = assemble_document(body, config.preamble)
    result = await asyncio.to_thread(
        compile_latex,
        full_doc,
        config.latex_engine,
        config.compile_timeout,
    )

    if result.errors:
        logger.warning(
            "Page %d compile errors: %s",
            page_idx + 1,
            "; ".join(e.message for e in result.errors),
        )
    else:
        logger.info("Page %d compiled successfully", page_idx + 1)
        await emit(
            ProgressEvent(
                event_type=EventType.PAGE_COMPILED_OK,
                page=page_idx + 1,
                total_pages=total,
                message=f"Page {page_idx + 1} compiled successfully",
            )
        )

    return {
        "compiler_success": result.success,
        "errors": [
            {"line": e.line, "message": e.message, "context": e.context} for e in result.errors
        ],
    }


async def fix_latex_node(state: PipelineState) -> dict:
    config = get_config(state)
    retry_count = state["retry_count"] + 1
    page_idx = state["page_index"]
    total = len(state["pages"])

    logger.info("Fix attempt %d for page %d", retry_count, page_idx + 1)
    await emit(
        ProgressEvent(
            event_type=EventType.PAGE_FIX_ATTEMPT,
            page=page_idx + 1,
            total_pages=total,
            retry=retry_count,
            max_retries=config.max_retries,
            message=f"Fixing errors on page {page_idx + 1} (attempt {retry_count}/{config.max_retries})",
        )
    )

    # Calculate line offset: preamble lines + base_body lines
    preamble_lines = config.preamble.count("\n") + 1
    base_body = state["base_body"]
    base_lines = base_body.count("\n") + 1 if base_body else 0
    offset = preamble_lines + base_lines

    adjusted_errors = [
        {**e, "line": max(1, e["line"] - offset)} if e.get("line") is not None else e
        for e in state["errors"]
    ]

    system_prompt = config.render_fix_errors_prompt()

    fixed_page = await fix_latex(
        latex_source=state["current_page_latex"],
        errors=adjusted_errors,
        system_prompt=system_prompt,
        config=config,
    )

    fixed_page, notes = split_editorial_notes(fixed_page)
    fixed_page = strip_preamble_from_body(fixed_page)
    new_body = prepend_page_marker(page_idx + 1, fixed_page, state["base_body"])

    # The fix prompt never asks for a notes block, so a fix pass must not wipe
    # the notes the initial generation produced for this page.
    if not notes:
        notes = (state.get("editorial_notes") or {}).get(page_idx + 1, "")

    return {
        "current_page_latex": fixed_page,
        "accumulated_body": new_body,
        "editorial_notes": {page_idx + 1: notes},
        "retry_count": retry_count,
    }


async def advance_page_node(state: PipelineState) -> dict:
    page_idx = state["page_index"]
    total = len(state["pages"])
    await emit(
        ProgressEvent(
            event_type=EventType.PAGE_DONE,
            page=page_idx + 1,
            total_pages=total,
            message=f"Page {page_idx + 1}/{total} done",
        )
    )
    return {
        "page_index": page_idx + 1,
        "retry_count": 0,
    }


async def finalize_node(state: PipelineState) -> dict:
    config = get_config(state)
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    await emit(
        ProgressEvent(
            event_type=EventType.FINALIZING,
            total_pages=len(state["pages"]),
            message="Assembling final document",
        )
    )

    # Assemble full document from body
    full_doc = assemble_document(state["accumulated_body"], config.preamble)

    # Write final .tex
    tex_path = output_dir / "output.tex"
    tex_path.write_text(full_doc, encoding="utf-8")

    # One final compilation to get the PDF in the output dir
    result = await asyncio.to_thread(
        compile_latex,
        full_doc,
        config.latex_engine,
        config.compile_timeout,
    )

    # Save compiler log
    if result.log_output:
        (output_dir / "output.log").write_text(result.log_output, encoding="utf-8")

    _write_editorial_notes(state.get("editorial_notes") or {}, output_dir)

    # Copy compiled PDF to output directory
    output_pdf = ""
    if result.pdf_path and result.pdf_path.exists():
        dest = output_dir / "output.pdf"
        shutil.copy2(result.pdf_path, dest)
        output_pdf = str(dest)
        logger.info("PDF saved to %s", output_pdf)
    else:
        logger.warning("Final compilation failed — only .tex saved")

    return {
        "output_tex_path": str(tex_path),
        "output_pdf_path": output_pdf,
    }


# ---------------------------------------------------------------------------
# Output artifacts
# ---------------------------------------------------------------------------


def _write_editorial_notes(notes: dict[int, str], output_dir: Path) -> Path | None:
    """Write per-page editorial notes to markdown, keeping them out of the PDF."""
    sections = [f"## Page {page}\n\n{notes[page]}" for page in sorted(notes) if notes[page]]
    if not sections:
        return None
    path = output_dir / "editorial-notes.md"
    path.write_text("# Editorial Notes\n\n" + "\n\n".join(sections) + "\n", encoding="utf-8")
    return path


async def upload_page_images(pages_dir: Path, api_key: str | None) -> dict[str, str]:
    """Upload saved page images to the CDN. Best effort — never raises."""
    if not api_key:
        return {}

    urls: dict[str, str] = {}
    for image_path in sorted(pages_dir.glob("page_*.png")):
        try:
            page_number = int(image_path.stem.removeprefix("page_"))
        except ValueError:
            logger.warning("Skipping unparseable page image: %s", image_path.name)
            continue
        try:
            urls[str(page_number)] = await upload_file(image_path, api_key)
        except Exception as exc:
            logger.warning("CDN upload failed for %s: %s", image_path.name, exc)
            try:
                await emit(
                    ProgressEvent(
                        event_type=EventType.CDN_UPLOAD_FAILED,
                        page=page_number,
                        message=f"CDN upload failed for page {page_number}: {exc}",
                    )
                )
            except Exception:
                pass
            continue
        try:
            await emit(
                ProgressEvent(
                    event_type=EventType.CDN_UPLOADED,
                    page=page_number,
                    message=f"Uploaded page {page_number} to CDN",
                )
            )
        except Exception:
            pass
    return urls


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route_after_compile(state: PipelineState) -> str:
    if state.get("compiler_success"):
        return "advance"
    config = get_config(state)
    if state.get("retry_count", 0) >= config.max_retries:
        logger.warning(
            "Max retries reached for page %d, advancing anyway",
            state["page_index"] + 1,
        )
        return "advance"  # give up on this page, move on
    return "fix"


def route_after_advance(state: PipelineState) -> str:
    if state["page_index"] >= len(state["pages"]):
        return "done"
    return "next_page"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("preprocess", preprocess_node)
    graph.add_node("generate_latex", generate_latex_node)
    graph.add_node("compile_latex", compile_latex_node)
    graph.add_node("fix_latex", fix_latex_node)
    graph.add_node("advance_page", advance_page_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("preprocess")
    graph.add_edge("preprocess", "generate_latex")
    graph.add_edge("generate_latex", "compile_latex")

    graph.add_conditional_edges(
        "compile_latex",
        route_after_compile,
        {
            "fix": "fix_latex",
            "advance": "advance_page",
        },
    )

    graph.add_edge("fix_latex", "compile_latex")

    graph.add_conditional_edges(
        "advance_page",
        route_after_advance,
        {
            "next_page": "generate_latex",
            "done": "finalize",
        },
    )

    graph.add_edge("finalize", END)

    return graph


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_pipeline(
    file_paths: list[Path],
    config: AgentConfig,
    callback: ProgressCallback | None = None,
) -> PipelineState:
    """Run the full conversion pipeline on the given input files."""
    if callback is not None:
        set_progress_callback(callback)

    # Save page images alongside output for the review UI
    pages_dir = config.output_dir / "pages"
    pages = load_pages(file_paths, config.dpi, save_dir=pages_dir)

    logger.info("Loaded %d page(s) from %d file(s)", len(pages), len(file_paths))

    await emit(
        ProgressEvent(
            event_type=EventType.JOB_STARTED,
            total_pages=len(pages),
            message=f"Starting conversion of {len(pages)} page(s)",
        )
    )

    cdn_url_path = config.output_dir / "cdn_urls.json"
    # Never leave URLs from a previous run in a shared output directory.
    cdn_url_path.unlink(missing_ok=True)
    cdn_urls = await upload_page_images(pages_dir, config.cdn_api_key)
    if cdn_urls:
        tmp_path = cdn_url_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(cdn_urls, indent=2), encoding="utf-8")
        os.replace(tmp_path, cdn_url_path)

    graph = build_graph()
    compiled = graph.compile()

    initial_state: PipelineState = {
        "pages": pages,
        "config_dict": config.to_state_dict(),
        "page_index": 0,
        "retry_count": 0,
        "base_body": "",
        "accumulated_body": "",
        "current_page_latex": "",
        "compiler_success": False,
        "errors": [],
        "output_tex_path": "",
        "output_pdf_path": "",
    }

    try:
        final_state = await compiled.ainvoke(initial_state)
    except Exception as exc:
        await emit(
            ProgressEvent(
                event_type=EventType.JOB_FAILED,
                message=str(exc),
            )
        )
        raise

    await emit(
        ProgressEvent(
            event_type=EventType.JOB_COMPLETED,
            total_pages=len(pages),
            message="Conversion complete",
            extra={
                "output_tex_path": final_state.get("output_tex_path", ""),
                "output_pdf_path": final_state.get("output_pdf_path", ""),
            },
        )
    )

    return final_state
