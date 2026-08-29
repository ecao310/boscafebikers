"""Structural checks on the static pages in site/.

Offline and dependency-free (``html.parser`` from the stdlib), because the
pages are hand-written with no build step: nothing else would notice an
unclosed ``<div>`` or a root-relative ``href``.

Two rules, both from CLAUDE.md:

* **Well-formed markup** — every element that opens closes, in order. The
  browser would silently repair most of it; the calendar and modal JS would
  not.
* **No root-relative URLs** — the site is served from the ``/boscafebikers/``
  subpath (and mirrored again under ``/preview/`` for the ``dev`` branch), so
  a leading ``/`` 404s in production even though it works on a local
  ``http.server``. Protocol-relative ``//host/…`` counts as the same failure:
  nothing here needs it.

Plus the shared chrome: every page carries the same ``.nav`` and ``<footer>``.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parent.parent / "site"

# HTML void elements: they never take an end tag.
VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})

# Attributes that hold a URL the browser will resolve against the page.
URL_ATTRS = frozenset({"href", "src", "action", "poster", "srcset", "data-bg", "formaction"})

# The seven pages CLAUDE.md documents. Checked as a subset of the glob so that
# adding an eighth page doesn't fail the suite — but deleting one does.
EXPECTED_PAGES = frozenset({
    "index.html", "cafes.html", "gallery.html", "shopify.html",
    "meta-business.html", "contact.html", "donate.html",
})


def site_pages() -> list[Path]:
    return sorted(SITE.glob("*.html"))


PAGES = site_pages()
PAGE_IDS = [p.name for p in PAGES]


class PageParser(HTMLParser):
    """Collects tag-nesting errors, URL attributes and class names."""

    def __init__(self, name: str) -> None:
        super().__init__(convert_charrefs=True)
        self.name = name
        self._stack: list[tuple[str, int]] = []
        self.errors: list[str] = []
        self.urls: list[tuple[str, str, int]] = []   # (attr, value, line)
        self.tags: list[str] = []
        self.classes: set[str] = set()

    # -- helpers -------------------------------------------------------
    def _record(self, tag: str, attrs) -> None:
        self.tags.append(tag)
        line = self.getpos()[0]
        for name, value in attrs:
            if value is None:
                continue
            if name == "class":
                self.classes.update(value.split())
            if name in URL_ATTRS:
                self.urls.append((name, value, line))

    # -- HTMLParser hooks ----------------------------------------------
    def handle_starttag(self, tag, attrs):
        self._record(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self._stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        # <br /> and friends: opened and closed in one go.
        self._record(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID_ELEMENTS:
            self.errors.append(f"line {self.getpos()[0]}: </{tag}> on a void element")
            return
        if not self._stack:
            self.errors.append(f"line {self.getpos()[0]}: </{tag}> with nothing open")
            return
        open_tag, open_line = self._stack[-1]
        if open_tag == tag:
            self._stack.pop()
            return
        # Mismatch: report it against whatever is actually open, and recover by
        # unwinding to the matching tag if there is one, so one stray tag
        # doesn't cascade into a hundred errors.
        self.errors.append(
            f"line {self.getpos()[0]}: </{tag}> closes <{open_tag}> opened on line {open_line}"
        )
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                return

    def close(self):  # type: ignore[override]
        super().close()
        for tag, line in self._stack:
            self.errors.append(f"line {line}: <{tag}> is never closed")
        return self


def parse(path: Path) -> PageParser:
    parser = PageParser(path.name)
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def test_the_documented_pages_all_exist():
    assert EXPECTED_PAGES <= {p.name for p in PAGES}


@pytest.mark.parametrize("path", PAGES, ids=PAGE_IDS)
def test_page_is_well_formed(path: Path):
    parser = parse(path)
    assert parser.errors == [], f"{path.name}:\n  " + "\n  ".join(parser.errors)


@pytest.mark.parametrize("path", PAGES, ids=PAGE_IDS)
def test_page_has_the_shared_nav_and_footer(path: Path):
    parser = parse(path)
    assert "nav" in parser.classes, f"{path.name} is missing the shared .nav"
    assert "footer" in parser.tags, f"{path.name} is missing the shared <footer>"


@pytest.mark.parametrize("path", PAGES, ids=PAGE_IDS)
def test_page_has_no_root_relative_urls(path: Path):
    """Served from /boscafebikers/ (and /boscafebikers/preview/), so a leading
    slash points at the wrong host root. Protocol-relative // is out too."""
    offenders = [
        f"line {line}: {attr}={value!r}"
        for attr, value, line in parse(path).urls
        if value.startswith("/")
    ]
    assert offenders == [], f"{path.name} has root-relative URLs:\n  " + "\n  ".join(offenders)


@pytest.mark.parametrize("path", PAGES, ids=PAGE_IDS)
def test_page_has_no_root_relative_urls_in_raw_text(path: Path):
    """Belt and braces for anything the parser doesn't treat as an attribute
    (inline CSS url(), a stray single-quoted href)."""
    text = path.read_text(encoding="utf-8")
    bad = re.findall(r"""(?:href|src|action|poster)\s*=\s*['"]//?[^'"]*""", text)
    assert bad == [], f"{path.name}: {bad}"


def test_stylesheet_has_no_root_relative_urls():
    css = (SITE / "styles.css").read_text(encoding="utf-8")
    assert re.search(r"url\(\s*['\"]?/", css) is None
