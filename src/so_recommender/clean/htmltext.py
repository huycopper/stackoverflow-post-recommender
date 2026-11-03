"""Turn Stack Overflow HTML into plain text, without Spark, so it can be unit tested.

Spark only wraps these functions in UDFs (normalize.py).
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

# Tags after which the text continues on a new line.
BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "br",
        "hr",
        "li",
        "ul",
        "ol",
        "dl",
        "dt",
        "dd",
        "blockquote",
        "table",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }
)
_SPACES = re.compile(r"[ \t\f\v ]+")
_ANY_SPACE = re.compile(r"\s+")


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.code_blocks: list[str] = []
        self._code: list[str] = []
        self._pre_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "pre":
            self._pre_depth += 1
        elif tag in BLOCK_TAGS and not self._pre_depth:
            self.text.append("\n")

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag in BLOCK_TAGS and not self._pre_depth:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre" and self._pre_depth:
            self._pre_depth -= 1
            if not self._pre_depth:
                self.code_blocks.append("".join(self._code))
                self._code = []
                self.text.append("\n")
        elif tag in BLOCK_TAGS and not self._pre_depth:
            self.text.append("\n")

    def handle_data(self, data: str) -> None:
        (self._code if self._pre_depth else self.text).append(data)


def collapse_lines(text: str) -> str:
    """Collapse runs of spaces in each line, trim lines and drop empty ones."""
    lines = (_SPACES.sub(" ", line).strip() for line in text.replace("\r", "").split("\n"))
    return "\n".join(line for line in lines if line)


def html_to_text(body: str | None) -> tuple[str, list[str]] | None:
    """Return (text without code blocks, code blocks) for an HTML post body.

    Inline <code> stays in the text: it is usually a name ("use `dict.update`") that the
    sentence needs. Block code (<pre>) goes to the second element, one string per block.
    """
    if body is None:
        return None
    parser = _Extractor()
    parser.feed(body)
    parser.close()
    if parser._pre_depth:  # unclosed <pre>: keep what was read as code
        parser.code_blocks.append("".join(parser._code))
    code = [block.strip("\n") for block in parser.code_blocks]
    return collapse_lines("".join(parser.text)), [block for block in code if block.strip()]


def plain_text(value: str | None) -> str | None:
    """Decode HTML entities (&quot;, &#39;, &amp;) and collapse whitespace to one line."""
    if value is None:
        return None
    return _ANY_SPACE.sub(" ", html.unescape(value)).strip()
