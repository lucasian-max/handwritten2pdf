"""Split the editorial-notes comment block out of a generated page."""

import re

# A comment containing the editorial-notes marker. Tolerates the shapes the
# model actually emits:
#   * any number of leading '%' (the model sometimes doubles them),
#   * the marker appearing mid-line after body text — LaTeX comments out the
#     rest of that line, so the prose before the '%' stays in the body while
#     everything from the marker onward becomes notes,
#   * dashes and spacing variations around "EDITORIAL NOTES".
EDITORIAL_NOTES_MARKER_RE = re.compile(
    r"%[^\n]*?-{2,}[ \t]*EDITORIAL NOTES[^\n]*",
    re.IGNORECASE,
)

NO_NOTES_PLACEHOLDER = (
    "(the model did not emit an editorial-notes block for this page; "
    "check the body against the original by hand)"
)


def split_editorial_notes(latex: str) -> tuple[str, str]:
    """Return ``(body, notes)`` for one generated page.

    Everything from the editorial-notes marker comment onward becomes *notes*;
    the body keeps only the LaTeX that may reach the compiled document.
    """
    match = EDITORIAL_NOTES_MARKER_RE.search(latex)
    if match is None:
        return latex.strip(), ""
    body = latex[: match.start()].rstrip()
    notes = latex[match.end() :].strip("\n")
    return body, notes
