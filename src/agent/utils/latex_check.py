"""Cheap structural checks for generated LaTeX bodies.

Providers sometimes report ``finish_reason='stop'`` on output they actually cut
at a token cap. A balanced-braces, balanced-environment, balanced-math check
catches the common truncation shapes without a compiler run.
"""

from __future__ import annotations


def _strip_comments(latex: str) -> str:
    """Drop ``%`` comments (unless escaped with a backslash)."""
    lines = []
    for line in latex.splitlines():
        i = 0
        while i < len(line):
            if line[i] == "\\":
                i += 2
                continue
            if line[i] == "%":
                line = line[:i]
                break
            i += 1
        lines.append(line)
    return "\n".join(lines)


def looks_complete(latex: str) -> bool:
    """Return False when a generated body is visibly cut off or unbalanced."""
    if not latex or not latex.strip():
        return False
    text = _strip_comments(latex)

    # Braces must balance, ignoring escaped \{ and \}.
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    if depth != 0:
        return False

    # \begin{X} ... \end{X} must nest and close in order.
    stack: list[str] = []
    i = 0
    while True:
        start = text.find("\\begin{", i)
        end = text.find("\\end{", i)
        if start == -1 and end == -1:
            break
        if start != -1 and (end == -1 or start < end):
            close = text.find("}", start)
            if close == -1:
                return False
            stack.append(text[start + 7 : close])
            i = close + 1
        else:
            close = text.find("}", end)
            if close == -1:
                return False
            name = text[end + 5 : close]
            if not stack or stack[-1] != name:
                return False
            stack.pop()
            i = close + 1
    if stack:
        return False

    # Inline/display math delimiters must pair up.
    dollars = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "$":
            dollars += 1
        i += 1
    return dollars % 2 == 0
