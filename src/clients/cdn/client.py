"""Hack Club CDN client — best-effort hosting for page images."""

from pathlib import Path

import httpx

CDN_UPLOAD_URL = "https://cdn.hackclub.com/api/v4/upload"


async def upload_file(path: Path, api_key: str, timeout: float = 60.0) -> str:
    """Upload *path* to the CDN and return its public URL.

    Raises on network or API failure so callers can treat hosting as best effort.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            CDN_UPLOAD_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (path.name, path.read_bytes(), "image/png")},
        )
        response.raise_for_status()
    return response.json()["url"]
