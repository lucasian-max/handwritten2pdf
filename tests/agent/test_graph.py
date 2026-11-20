"""Tests for pipeline routing, helpers, and end-to-end flow."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from agent.config import AgentConfig
from agent.graph import route_after_advance, route_after_compile, run_pipeline
from agent.state import PipelineState
from agent.utils.editorial_notes import split_editorial_notes
from compiler.compiler import CompilerResult
from document.processing import assemble_document, open_environments

# Default preamble loaded from prompts/preamble.tex
_DEFAULT_PREAMBLE = AgentConfig().preamble


class TestRouting:
    def test_route_after_compile_success(self):
        state: PipelineState = {"compiler_success": True, "retry_count": 0, "config_dict": {}}
        assert route_after_compile(state) == "advance"

    def test_route_after_compile_retry(self):
        state: PipelineState = {"compiler_success": False, "retry_count": 1, "config_dict": {}}
        assert route_after_compile(state) == "fix"

    def test_route_after_compile_max_retries(self):
        state: PipelineState = {
            "compiler_success": False,
            "retry_count": 3,
            "config_dict": {},
            "page_index": 0,
        }
        assert route_after_compile(state) == "advance"

    def test_route_after_advance_next_page(self):
        # page_index=1 means we just advanced from page 0; page 1 still needs processing
        state: PipelineState = {"page_index": 1, "pages": ["a", "b", "c"]}
        assert route_after_advance(state) == "next_page"

    def test_route_after_advance_done(self):
        # page_index=3 means all 3 pages (0,1,2) are done
        state: PipelineState = {"page_index": 3, "pages": ["a", "b", "c"]}
        assert route_after_advance(state) == "done"

    def test_route_after_advance_single_page(self):
        # page_index=1 after advancing from the only page
        state: PipelineState = {"page_index": 1, "pages": ["a"]}
        assert route_after_advance(state) == "done"

    def test_route_after_advance_two_pages_midway(self):
        # page_index=1 means page 0 done, page 1 still needs processing
        state: PipelineState = {"page_index": 1, "pages": ["a", "b"]}
        assert route_after_advance(state) == "next_page"


class TestOpenEnvironments:
    def test_empty_string(self):
        assert open_environments("") == []

    def test_no_environments(self):
        assert open_environments(r"Hello $x^2$ world") == []

    def test_closed_environment(self):
        latex = r"\begin{theorem}Some theorem.\end{theorem}"
        assert open_environments(latex) == []

    def test_open_environment(self):
        latex = r"\begin{enumerate}\item First"
        assert open_environments(latex) == ["enumerate"]

    def test_nested_open(self):
        latex = (
            r"\begin{theorem}"
            "\n"
            r"\begin{align}"
            "\n"
            r"x &= 1"
        )
        assert open_environments(latex) == ["theorem", "align"]

    def test_partially_closed(self):
        latex = (
            r"\begin{theorem}"
            "\n"
            r"\begin{align}"
            "\n"
            r"x &= 1"
            "\n"
            r"\end{align}"
        )
        assert open_environments(latex) == ["theorem"]

    def test_multiple_open_close(self):
        latex = (
            r"\begin{theorem}Thm.\end{theorem}"
            "\n"
            r"\begin{proof}"
            "\n"
            r"\begin{align}"
            "\n"
            r"a &= b"
        )
        assert open_environments(latex) == ["proof", "align"]


class TestAssembleDocument:
    def test_assembles_correctly(self):
        body = "Hello $x^2$."
        doc = assemble_document(body, _DEFAULT_PREAMBLE)
        assert doc.startswith(_DEFAULT_PREAMBLE)
        assert "Hello $x^2$." in doc
        assert doc.strip().endswith(r"\end{document}")

    def test_empty_body(self):
        doc = assemble_document("", _DEFAULT_PREAMBLE)
        assert r"\begin{document}" in doc
        assert r"\end{document}" in doc


# Body-only mock (no preamble, no \begin/\end{document})
MOCK_BODY = "Hello $x^2$."

NOTES_MARKER = "% --- EDITORIAL NOTES: PAGE 1 ---"
NOTES_LINES = "% corrected a sign error in the second line\n% added the missing justification"


def _make_image(tmp_path):
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="white")
    img_path = tmp_path / "test.png"
    img.save(img_path)
    return img_path


async def _run_mocked_pipeline(tmp_path, config, generated):
    """Run the pipeline with the VLM and compiler mocked out."""
    img_path = _make_image(tmp_path)
    with (
        patch("agent.graph.transcribe_page", new_callable=AsyncMock) as mock_transcribe,
        patch("agent.graph.compile_latex") as mock_compile,
    ):
        mock_transcribe.return_value = generated
        mock_compile.return_value = CompilerResult(
            success=True,
            pdf_path=None,
            errors=[],
            log_output="",
        )
        result = await run_pipeline([img_path], config)
    return result, mock_transcribe, mock_compile


class TestEditorialNotesSplit:
    def test_splits_body_and_notes(self):
        body, notes = split_editorial_notes(f"Text $x$.\n\n{NOTES_MARKER}\n{NOTES_LINES}")
        assert body == "Text $x$."
        assert notes == NOTES_LINES
        assert "EDITORIAL NOTES" not in body

    def test_no_marker_returns_body_only(self):
        body, notes = split_editorial_notes("Text $x$.")
        assert body == "Text $x$."
        assert notes == ""

    def test_multiline_body_preserved(self):
        body, _ = split_editorial_notes(
            "\\begin{theorem}\nStatement.\n\\end{theorem}\n" + NOTES_MARKER
        )
        assert body == "\\begin{theorem}\nStatement.\n\\end{theorem}"

    def test_doubled_percent_marker_still_splits(self):
        # The model sometimes doubles the comment character.
        doubled = "% " + NOTES_MARKER.removeprefix("% ")
        body, notes = split_editorial_notes(f"Text.\n{doubled}\n{NOTES_LINES}")
        assert body == "Text."
        assert "corrected a sign error" in notes

    def test_mid_line_marker_splits(self):
        # A marker appended after prose comments the rest of that line; the
        # prose must stay in the body and the notes must not leak into it.
        line = "Text $x$. % --- EDITORIAL NOTES: PAGE 1 --- tail"
        body, notes = split_editorial_notes(f"{line}\n{NOTES_LINES}")
        assert body == "Text $x$."
        assert "corrected a sign error" in notes
        assert "EDITORIAL NOTES" not in body

    def test_marker_before_body_yields_empty_body(self):
        body, notes = split_editorial_notes(f"{NOTES_MARKER}\n{NOTES_LINES}")
        assert body == ""
        assert notes == NOTES_LINES


class TestConfigSerialization:
    def test_api_base_and_mode_serialized(self):
        config = AgentConfig(api_base="https://example.com/proxy/v1", mode="material")
        state = config.to_state_dict()
        assert state["api_base"] == "https://example.com/proxy/v1"
        assert state["mode"] == "material"

    def test_defaults(self):
        state = AgentConfig().to_state_dict()
        assert state["api_base"] is None
        assert state["mode"] == "transcribe"


class TestModePromptSelection:
    @pytest.mark.asyncio
    async def test_material_mode_renders_material_prompt(self, tmp_path):
        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1, mode="material")

        _, mock_transcribe, _ = await _run_mocked_pipeline(tmp_path, config, MOCK_BODY)

        system_prompt = mock_transcribe.call_args.kwargs["system_prompt"]
        assert system_prompt == config.render_material_prompt(page_number=1, open_envs=[])
        assert system_prompt != config.render_transcribe_prompt(page_number=1, open_envs=[])

    @pytest.mark.asyncio
    async def test_transcribe_mode_renders_transcribe_prompt(self, tmp_path):
        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1)

        _, mock_transcribe, _ = await _run_mocked_pipeline(tmp_path, config, MOCK_BODY)

        system_prompt = mock_transcribe.call_args.kwargs["system_prompt"]
        assert system_prompt == config.render_transcribe_prompt(page_number=1, open_envs=[])


class TestEditorialNotesPipeline:
    @pytest.mark.asyncio
    async def test_notes_kept_out_of_document(self, tmp_path):
        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1, mode="material")
        generated = f"Text $x$.\n\n{NOTES_MARKER}\n{NOTES_LINES}"

        result, _, mock_compile = await _run_mocked_pipeline(tmp_path, config, generated)

        assert result["accumulated_body"] == "% ====== Page 1 ======\nText $x$."
        assert "EDITORIAL NOTES" not in result["accumulated_body"]
        assert NOTES_LINES.splitlines()[0] not in mock_compile.call_args_list[0][0][0]

        notes_path = config.output_dir / "editorial-notes.md"
        assert notes_path.exists()
        notes = notes_path.read_text(encoding="utf-8")
        assert "## Page 1" in notes
        assert "corrected a sign error" in notes

    @pytest.mark.asyncio
    async def test_missing_marker_leaves_visible_note(self, tmp_path):
        """A page with no notes block must not vanish silently."""
        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1, mode="material")

        result, _, _ = await _run_mocked_pipeline(tmp_path, config, "Just body text.")

        notes = (config.output_dir / "editorial-notes.md").read_text(encoding="utf-8")
        assert "did not emit an editorial-notes block" in notes
        assert result["accumulated_body"].endswith("Just body text.")

    @pytest.mark.asyncio
    async def test_fix_pass_preserves_notes(self, tmp_path):
        """A compile fix must not wipe the notes produced at generation."""
        from types import SimpleNamespace

        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1, mode="material")
        generated = f"Broken \\undefinedcmd $x$.\n\n{NOTES_MARKER}\n{NOTES_LINES}"
        img_path = _make_image(tmp_path)

        compile_results = [
            CompilerResult(
                success=False,
                pdf_path=None,
                errors=[SimpleNamespace(line=1, message="Undefined control sequence.", context="")],
                log_output="",
            ),
            # After the fix.
            CompilerResult(success=True, pdf_path=None, errors=[], log_output=""),
            # Final document assembly.
            CompilerResult(success=True, pdf_path=None, errors=[], log_output=""),
        ]
        with (
            patch("agent.graph.transcribe_page", new_callable=AsyncMock) as mock_transcribe,
            patch("agent.graph.fix_latex", new_callable=AsyncMock) as mock_fix,
            patch("agent.graph.compile_latex") as mock_compile,
        ):
            mock_transcribe.return_value = generated
            # A fix pass never re-emits the notes block.
            mock_fix.return_value = "Fixed text $x$."
            mock_compile.side_effect = compile_results
            result = await run_pipeline([img_path], config)

        assert mock_fix.await_count == 1
        assert result["accumulated_body"].endswith("Fixed text $x$.")
        assert "EDITORIAL NOTES" not in result["accumulated_body"]
        notes = (config.output_dir / "editorial-notes.md").read_text(encoding="utf-8")
        assert "corrected a sign error" in notes


class TestCdnUploads:
    @pytest.mark.asyncio
    async def test_cdn_urls_written_on_success(self, tmp_path):
        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1, cdn_api_key="test-key")

        with patch("agent.graph.upload_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://cdn.example/page_001.png"
            await _run_mocked_pipeline(tmp_path, config, MOCK_BODY)

        cdn_path = config.output_dir / "cdn_urls.json"
        assert cdn_path.exists()
        assert json.loads(cdn_path.read_text(encoding="utf-8")) == {
            "1": "https://cdn.example/page_001.png"
        }
        mock_upload.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cdn_failure_does_not_fail_job(self, tmp_path):
        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1, cdn_api_key="test-key")

        with patch("agent.graph.upload_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.side_effect = RuntimeError("cdn down")
            result, _, _ = await _run_mocked_pipeline(tmp_path, config, MOCK_BODY)

        assert result["accumulated_body"] == f"% ====== Page 1 ======\n{MOCK_BODY}"
        assert not (config.output_dir / "cdn_urls.json").exists()

    @pytest.mark.asyncio
    async def test_no_key_skips_upload(self, tmp_path):
        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1)

        with patch("agent.graph.upload_file", new_callable=AsyncMock) as mock_upload:
            await _run_mocked_pipeline(tmp_path, config, MOCK_BODY)

        mock_upload.assert_not_awaited()
        assert not (config.output_dir / "cdn_urls.json").exists()


class TestSettings:
    def test_mode_accepts_known_values(self):
        from core.config import Settings

        assert Settings.model_fields["mode"].default == "transcribe"
        assert Settings(_env_file=None, mode="material").mode == "material"

    def test_mode_rejects_unknown_value(self):
        from pydantic import ValidationError

        from core.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None, mode="faithful")


class TestPipelineEndToEnd:
    """Mock-based test for the full pipeline flow."""

    @pytest.mark.asyncio
    async def test_single_page_pipeline(self, tmp_path):
        # Create a dummy image file
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="white")
        img_path = tmp_path / "test.png"
        img.save(img_path)

        config = AgentConfig(output_dir=tmp_path / "output", max_retries=1)

        with (
            patch("agent.graph.transcribe_page", new_callable=AsyncMock) as mock_transcribe,
            patch("agent.graph.compile_latex") as mock_compile,
        ):
            mock_transcribe.return_value = MOCK_BODY

            mock_compile.return_value = CompilerResult(
                success=True,
                pdf_path=None,
                errors=[],
                log_output="",
            )

            result = await run_pipeline([img_path], config)

        # accumulated_body should contain page marker + body content
        assert result["accumulated_body"] == f"% ====== Page 1 ======\n{MOCK_BODY}"
        # The assembled document passed to compile should include preamble
        compile_call_args = mock_compile.call_args_list[0][0][0]
        assert _DEFAULT_PREAMBLE in compile_call_args
        assert r"\end{document}" in compile_call_args
        mock_transcribe.assert_called_once()
        # compile is called in compile_latex_node + finalize_node = 2 times
        assert mock_compile.call_count == 2


class TestSplitPipeline:
    @pytest.mark.asyncio
    async def test_split_transcribes_then_authors(self, tmp_path):
        config = AgentConfig(
            output_dir=tmp_path / "output",
            max_retries=1,
            mode="material",
            pipeline="split",
            verify_rounds=0,
        )
        img = _make_image(tmp_path)
        with (
            patch("agent.graph.transcribe_page", new_callable=AsyncMock) as mock_tr,
            patch("agent.graph.author_page", new_callable=AsyncMock) as mock_au,
            patch("agent.graph.compile_latex") as mock_compile,
        ):
            mock_tr.return_value = "TITLE: Gauss\nEQUATION: q/(4 pi eps_0 r^2)"
            mock_au.return_value = f"Body text.\n\n{NOTES_MARKER}\n{NOTES_LINES}"
            mock_compile.return_value = CompilerResult(
                success=True, pdf_path=None, errors=[], log_output=""
            )
            result = await run_pipeline([img], config)

        # Split mode uses the faithful transcription prompt...
        assert "transcription engine" in mock_tr.call_args.kwargs["system_prompt"]
        # ...and hands the transcription to the authoring stage.
        assert "TITLE: Gauss" in mock_au.call_args.kwargs["system_prompt"]
        assert mock_au.call_args.kwargs["transcription"].startswith("TITLE: Gauss")
        assert result["accumulated_body"].endswith("Body text.")
        notes = (config.output_dir / "editorial-notes.md").read_text(encoding="utf-8")
        assert "corrected a sign error" in notes

    def test_role_models_fall_back_to_model(self):
        config = AgentConfig(model="m")
        assert config.role_models() == {"transcribe": "m", "author": "m", "verify": "m"}

    def test_role_models_use_overrides(self):
        config = AgentConfig(
            model="m",
            transcribe_model="tr",
            author_model="au",
            verify_model="ve",
        )
        assert config.role_models() == {"transcribe": "tr", "author": "au", "verify": "ve"}


class TestVerifyNode:
    @pytest.mark.asyncio
    async def test_defects_trigger_regeneration(self, tmp_path):
        from agent.graph import verify_latex_node

        config = AgentConfig(
            output_dir=tmp_path / "output",
            mode="material",
            pipeline="split",
            verify_rounds=1,
        )
        state = {
            "pages": ["orig-b64"],
            "config_dict": config.to_state_dict(),
            "page_index": 0,
            "transcriptions": {1: "ORIGINAL TRANSCRIPT"},
            "page_pdf_path": "/tmp/fake.pdf",
            "current_page_latex": "Wrong body.",
            "editorial_notes": {1: "% first pass"},
            "base_body": "",
            "verify_count": 0,
        }
        report = {
            "verdict": "regen",
            "defects": [{"page_element": "fig 1", "problem": "wrong curve", "fix": "redraw"}],
            "notes": "x",
        }
        with (
            patch("agent.graph._render_page_png", return_value="render-b64"),
            patch("agent.graph.verify_page", new_callable=AsyncMock) as mock_verify,
            patch("agent.graph.author_page", new_callable=AsyncMock) as mock_author,
        ):
            mock_verify.return_value = report
            mock_author.return_value = "Fixed body."
            out = await verify_latex_node(state)

        assert out["verify_action"] == "recompile"
        assert out["verify_count"] == 1
        assert out["current_page_latex"] == "Fixed body."
        assert "wrong curve" in mock_author.call_args.kwargs["revision_notes"]
        assert "verify round 1" in out["editorial_notes"][1]
        assert "% first pass" in out["editorial_notes"][1]

    @pytest.mark.asyncio
    async def test_ok_advances_without_regeneration(self, tmp_path):
        from agent.graph import verify_latex_node

        config = AgentConfig(output_dir=tmp_path / "output", mode="material", pipeline="split")
        state = {
            "pages": ["orig-b64"],
            "config_dict": config.to_state_dict(),
            "page_index": 0,
            "transcriptions": {1: "T"},
            "page_pdf_path": "/tmp/fake.pdf",
            "current_page_latex": "Good body.",
            "editorial_notes": {1: "% notes"},
            "base_body": "",
            "verify_count": 0,
        }
        with (
            patch("agent.graph._render_page_png", return_value="render-b64"),
            patch("agent.graph.verify_page", new_callable=AsyncMock) as mock_verify,
            patch("agent.graph.author_page", new_callable=AsyncMock) as mock_author,
        ):
            mock_verify.return_value = {"verdict": "ok", "defects": [], "notes": ""}
            out = await verify_latex_node(state)

        assert out["verify_action"] == "advance"
        mock_author.assert_not_awaited()
        assert "no defects" in out["editorial_notes"][1]

    def test_routing_split_goes_to_verify(self):
        config = AgentConfig(pipeline="split", verify_rounds=1).to_state_dict()
        assert route_after_compile({"compiler_success": True, "config_dict": config}) == "verify"

    def test_routing_verify_rounds_zero_advances(self):
        config = AgentConfig(pipeline="split", verify_rounds=0).to_state_dict()
        assert route_after_compile({"compiler_success": True, "config_dict": config}) == "advance"

    def test_routing_single_pipeline_unchanged(self):
        config = AgentConfig(pipeline="single").to_state_dict()
        assert route_after_compile({"compiler_success": True, "config_dict": config}) == "advance"


class TestAuthorFallback:
    @pytest.mark.asyncio
    async def test_api_error_falls_back_to_transcribe_model(self):
        from agent.graph import author_page

        config = AgentConfig(model="primary")
        calls = []

        async def fake(model, **kwargs):
            calls.append(model)
            if model == "primary":
                raise RuntimeError("402 spending limit")
            return "body"

        with patch("agent.graph.acompletion", side_effect=fake):
            out = await author_page(
                transcription="T",
                system_prompt="S",
                config=config,
                model="primary",
                fallback_model="fallback",
            )

        assert out == "body"
        assert calls == ["primary", "fallback"]
