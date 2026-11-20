"""Tests for job response assembly."""

import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from agent.config import AgentConfig
from api.v1.agent.models import ConvertRequest
from api.v1.agent.routes import _build_job_response, _ensure_public_api_base
from core.config import Settings
from db.models import Job, JobStatus


def _job(mode: str = "material") -> Job:
    return Job(
        id="abc123",
        status=JobStatus.COMPLETED,
        model="test/model",
        mode=mode,
        input_filenames='["page.png"]',
    )


def test_job_detail_includes_mode_and_empty_artifacts(tmp_path):
    with patch("api.v1.agent.routes._get_job_dir", return_value=tmp_path):
        response = _build_job_response(_job(), include_artifacts=True)

    assert response.mode == "material"
    assert response.cdn_urls == {}
    assert response.editorial_notes is None


def test_job_detail_reads_artifacts(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "cdn_urls.json").write_text(
        json.dumps({"1": "https://cdn.example/1.png"}), encoding="utf-8"
    )
    (output / "editorial-notes.md").write_text(
        "# Editorial Notes\n\n## Page 1\n\n% note\n", encoding="utf-8"
    )

    with patch("api.v1.agent.routes._get_job_dir", return_value=tmp_path):
        response = _build_job_response(_job(), include_artifacts=True)

    assert response.cdn_urls == {"1": "https://cdn.example/1.png"}
    assert "## Page 1" in response.editorial_notes


def test_job_list_skips_artifacts(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "cdn_urls.json").write_text(json.dumps({"1": "https://cdn.example/1.png"}))
    (output / "editorial-notes.md").write_text("# Editorial Notes\n", encoding="utf-8")

    response = _build_job_response(_job())

    assert response.cdn_urls == {}
    assert response.editorial_notes is None


def test_job_detail_tolerates_corrupt_cdn_urls(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "cdn_urls.json").write_text("{not json")

    with patch("api.v1.agent.routes._get_job_dir", return_value=tmp_path):
        response = _build_job_response(_job(), include_artifacts=True)

    assert response.cdn_urls == {}


class TestPublicApiBaseGuard:
    def test_public_base_passes(self):
        _ensure_public_api_base("https://ai.hackclub.com/proxy/v1")

    def test_loopback_name_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _ensure_public_api_base("https://localhost:8000/v1")
        assert exc.value.status_code == 422

    def test_loopback_ip_rejected(self):
        with pytest.raises(HTTPException):
            _ensure_public_api_base("http://127.0.0.1:8000/v1")

    def test_private_ip_rejected(self):
        with pytest.raises(HTTPException):
            _ensure_public_api_base("http://10.1.2.3/v1")

    def test_link_local_rejected(self):
        # The cloud metadata endpoint must not be reachable via api_base.
        with pytest.raises(HTTPException):
            _ensure_public_api_base("http://169.254.169.254/latest/meta-data")

    def test_non_http_scheme_rejected(self):
        with pytest.raises(HTTPException):
            _ensure_public_api_base("ftp://example.com/v1")


class TestConvertRequestValidation:
    def test_malformed_json_raises_validation_error(self):
        # create_job catches this and returns 422 instead of a 500 traceback.
        with pytest.raises(ValidationError):
            ConvertRequest.model_validate_json("{not json")

    def test_garbage_mode_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ConvertRequest.model_validate_json('{"mode": "garbage"}')

    def test_blank_strings_normalized_to_none(self):
        # Blank values must not override server configuration downstream.
        req = ConvertRequest.model_validate_json(
            '{"api_base": "  ", "api_key": "", "preamble": "   "}'
        )
        assert req.api_base is None
        assert req.api_key is None
        assert req.preamble is None


class TestServerKeyIsolation:
    """A client-chosen endpoint must never receive the server's API key."""

    def _settings(self) -> Settings:
        return Settings(
            model="openai/z-ai/glm-5.3-flash",
            api_key="server-secret",
            api_base="https://default.example/v1",
        )

    def test_client_base_with_client_key_uses_client_key(self):
        cfg = AgentConfig.from_settings(
            self._settings(),
            api_base="https://client.example/v1",
            api_key="client-key",
        )
        assert cfg.api_key == "client-key"

    def test_client_base_without_key_gets_no_key(self):
        cfg = AgentConfig.from_settings(self._settings(), api_base="https://client.example/v1")
        assert cfg.api_key is None

    def test_default_base_keeps_server_key(self):
        cfg = AgentConfig.from_settings(self._settings())
        assert cfg.api_key == "server-secret"
        assert cfg.api_base == "https://default.example/v1"


class TestPipelineRequest:
    def test_pipeline_accepted(self):
        req = ConvertRequest.model_validate_json(
            '{"pipeline": "split", "transcribe_model": "a", "author_model": "b", '
            '"verify_model": "c", "verify_rounds": 2}'
        )
        assert req.pipeline == "split"
        assert req.verify_rounds == 2

    def test_blank_pipeline_normalized(self):
        req = ConvertRequest.model_validate_json('{"pipeline": "  ", "author_model": ""}')
        assert req.pipeline is None
        assert req.author_model is None

    def test_garbage_pipeline_rejected(self):
        with pytest.raises(ValidationError):
            ConvertRequest.model_validate_json('{"pipeline": "multi"}')


class TestSplitRoleModels:
    def _settings(self) -> Settings:
        return Settings(
            model="server/model",
            api_base="https://default.example/v1",
            transcribe_model="server/tr",
            author_model="server/au",
            verify_model="server/ve",
        )

    def test_roles_kept_on_trusted_base(self):
        cfg = AgentConfig.from_settings(self._settings())
        assert cfg.transcribe_model == "server/tr"
        assert cfg.author_model == "server/au"

    def test_roles_cleared_on_client_base(self):
        cfg = AgentConfig.from_settings(
            self._settings(),
            api_base="https://client.example/v1",
            api_key="client-key",
        )
        assert cfg.transcribe_model is None
        assert cfg.author_model is None
        assert cfg.verify_model is None
        # Role models then fall back to the requested model.
        assert cfg.role_models()["author"] == "server/model"
