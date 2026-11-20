#!/usr/bin/env python3
"""Benchmark candidate models on the app's real conversion pipeline.

For each (model, page): create a material-mode job, wait for completion,
then score the artifacts against the known ground truth of each fixture.
"""

import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

API = "http://127.0.0.1:8000/api/v1"
HERE = Path(__file__).resolve().parent
OUT = HERE / "results.json"
PAGES = {
    1: str(HERE / "fixtures" / "hw_page1.png"),
    2: str(HERE / "fixtures" / "hw_page2.png"),
}
MODELS = [
    "z-ai/glm-5.3-flash",
    "z-ai/glm-5.3-flashx",
    "z-ai/glm-4.6v",
    "deepseek/deepseek-v4.1-flash",
    "deepseek/deepseek-v4-flash-vision-exp",
    "google/gemini-3-flash-preview",
    "qwen/qwen3-vl-235b-a22b-instruct",
    "openai/gpt-4o",
]

# (pattern, is_hard) per page; patterns are regexes over the output.tex body.
CHECKS = {
    1: [
        (r"gauss", True),
        (r"\\oint", True),
        (r"\\varepsilon|\\epsilon", True),
        (r"4\s*\\pi", True),
        (r"4\s*\\pi\s*r\s*\^\s*{?2", True),
        (r"q\s*_\s*{?\s*(\\(?:mathrm|text)\{)?\s*enc", False),  # subscript is
        # illegible in the fixture; reward either a reasonable reading...
        (r"tikzpicture", False),
    ],
    2: [
        (r"integration by parts", True),
        (r"\\int", True),
        (r"u\s*\\?,?\s*dv|u\s+dv", True),
        (r"v\s*\\?,?\s*du|v\s+du", True),
        (r"e\s*\^\s*{?x", True),
        (r"\(\s*x\s*-\s*1\s*\)\s*e\s*\^\s*{?x|\(\s*\(x\s*-\s*1\)", True),
        (r"\+\s*C", True),
        (r"differenti|check", False),
        (r"tikzpicture", False),
    ],
}


def post_job(model: str, page: int) -> str:
    config = {
        "model": f"openai/{model}",
        "api_base": "https://ai.hackclub.com/proxy/v1",
        "mode": "material",
    }
    # multipart via stdlib
    boundary = "----benchboundary123"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="hw_page{page}.png"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode()
        + open(PAGES[page], "rb").read()
        + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="config"\r\n\r\n'
            f"{json.dumps(config)}\r\n--{boundary}--\r\n"
        ).encode()
    )
    req = urllib.request.Request(
        f"{API}/jobs",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    resp = json.load(urllib.request.urlopen(req, timeout=60))
    return resp["job_id"]


def wait_job(job_id: str, timeout_s: int = 420) -> dict:
    start = time.time()
    while time.time() - start < timeout_s:
        d = json.load(urllib.request.urlopen(f"{API}/jobs/{job_id}", timeout=30))
        if d["status"] in ("completed", "failed"):
            d["_duration"] = round(time.time() - start, 1)
            return d
        time.sleep(4)
    return {"status": "timeout", "_duration": round(time.time() - start, 1)}


def score(job_dir: Path, page: int) -> dict:
    tex_path = job_dir / "output" / "output.tex"
    notes_path = job_dir / "output" / "editorial-notes.md"
    result = {"hard": 0, "hard_max": 0, "soft": 0, "detail": []}
    if not tex_path.exists():
        result["detail"].append("no output.tex")
        result["hard_max"] = sum(1 for _, hard in CHECKS[page] if hard)
        return result
    tex = tex_path.read_text(encoding="utf-8")
    # score the generated body only (after the page marker), not the preamble
    marker = re.search(r"% ====== Page \d+ ======", tex)
    body = tex[marker.end() :] if marker else tex
    body_low = body.lower()
    notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""

    for pattern, hard in CHECKS[page]:
        hit = re.search(pattern, body, re.IGNORECASE)
        if hard:
            result["hard_max"] += 1
            if hit:
                result["hard"] += 1
            else:
                result["detail"].append(f"MISS {pattern}")
        elif hit:
            result["soft"] += 1

    # q_enc is illegible in the fixture; flagging the uncertainty is equally good
    if (
        page == 1
        and not re.search(r"enc", body_low)
        and ("uncertain" in notes.lower() or "ambiguous" in notes.lower())
    ):
        result["soft"] += 1
        result["detail"].append("flagged ambiguous subscript in notes")

    if r"\documentclass" in body or "```" in body:
        result["detail"].append("FORMAT LEAK (preamble/fences in body)")
    if "editorial notes" in body_low:
        result["detail"].append("NOTES LEAK into body")
    if notes and len(notes) > 150:
        result["soft"] += 1  # substantive editorial notes
    return result


def main() -> None:
    jobs_root = Path("data/jobs")  # run from the repo root  # run from the repo root
    results = []
    for model in MODELS:
        for page in (1, 2):
            try:
                job_id = post_job(model, page)
                d = wait_job(job_id)
                sc = score(jobs_root / job_id, page)
                results.append(
                    {
                        "model": model,
                        "page": page,
                        "job_id": job_id,
                        "status": d["status"],
                        "duration_s": d.get("_duration"),
                        "has_pdf": d.get("has_pdf", False),
                        **sc,
                    }
                )
                print(json.dumps(results[-1]), flush=True)
            except Exception as exc:  # noqa: BLE001
                results.append({"model": model, "page": page, "error": str(exc)})
                print(json.dumps(results[-1]), flush=True)
    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {OUT}")


main()
