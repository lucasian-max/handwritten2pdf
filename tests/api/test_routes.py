"""Tests for job response assembly."""

import json
from unittest.mock import patch

from api.v1.agent.routes import _build_job_response
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
