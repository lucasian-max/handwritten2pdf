#!/usr/bin/env python3
"""Check which candidate models accept image input via the Hack Club AI proxy.

Usage:
    export HACKCLUB_AI_KEY=sk-hc-v1-...
    python3 probe_vision.py
"""
import base64
import json
import os
import sys
import urllib.request
import urllib.error

KEY = os.environ.get("HACKCLUB_AI_KEY", "")
BASE = "https://ai.hackclub.com/proxy/v1/chat/completions"

CANDIDATES = [
    "z-ai/glm-5.3-flash",
    "z-ai/glm-5.3-flashx",
    "z-ai/glm-4.6v",
    "deepseek/deepseek-v4.1-flash",
    "deepseek/deepseek-v4-flash-vision-exp",
    "google/gemini-3-flash-preview",
    "qwen/qwen3-vl-235b-a22b-instruct",
    "openai/gpt-4o",
]


def main() -> int:
    if not KEY:
        print("Set HACKCLUB_AI_KEY first (a sk-hc-v1-... key from ai.hackclub.com).")
        return 1

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB"
        "h6FO1AAAAABJRU5ErkJggg=="
    )
    b64 = base64.b64encode(png).decode()

    ok, bad = [], []
    for model in CANDIDATES:
        body = {
            "model": model,
            "max_tokens": 30,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What color is this image? One word."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
        }
        req = urllib.request.Request(
            BASE, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        )
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=90))
            content = (resp["choices"][0]["message"].get("content") or "").strip()
            print(f"OK    {model:45s} -> {content[:30]!r}")
            ok.append(model)
        except urllib.error.HTTPError as e:
            print(f"FAIL  {model:45s} -> {e.code} {e.read().decode()[:120]}")
            bad.append(model)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {model:45s} -> {exc}")
            bad.append(model)

    print("\nvision-ok:", json.dumps(ok))
    return 0


if __name__ == "__main__":
    sys.exit(main())
