"""Split the editorial-notes comment block out of a generated page."""

import re

EDITORIAL_NOTES_MARKER_RE = re.compile(
    r"^[ \t]*%[ \t]*-{2,}[ \t]*EDITORIAL NOTES\b.*$",
    re.MULTILINE | re.IGNORECASE,
)


def split_editorial_notes(latex: str) -> tuple[str, str]:
    """Return ``(body, notes)`` for one generated page.

    Everything after the editorial-notes marker becomes *notes*; the body keeps
    only the LaTeX that may reach the compiled document.
    """
    match = EDITORIAL_NOTES_MARKER_RE.search(latex)
    if match is None:
        return latex.strip(), ""
    body = latex[: match.start()].rstrip()
    notes = latex[match.end() :].strip("\n")
    return body, notes
