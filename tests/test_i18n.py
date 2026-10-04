"""Spanish translation coverage and style.

English source text is the key, so the risk is a string added to the UI without an entry
in locales/es.js (it would silently show up in English). These tests catch that.
"""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Comment, Doctype

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "frontend" / "static" / "js"
ES_JS = STATIC / "locales" / "es.js"

# English on purpose: same in both languages (brand, currency codes, units, symbols).
# The language switch itself is labelled in each language, so it never changes.
SAME_IN_BOTH = {"Budget Tracker", "CRC", "USD", "Color", "Tasa Cero", "+ Tasa Cero", "EN", "ES", "English", "Español"}


def load_es():
    """es.js is generated with one JSON-encoded `"key": "value",` entry per line."""
    entries = {}
    for line in ES_JS.read_text(encoding="utf8").splitlines():
        line = line.strip()
        if line.startswith('"'):
            entries.update(json.loads("{" + line.rstrip(",") + "}"))
    return entries


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def has_letters(s):
    return re.search(r"[A-Za-z]{2}", s) is not None


def static_strings():
    soup = BeautifulSoup((ROOT / "frontend" / "templates" / "index.html").read_text(encoding="utf8"), "html.parser")
    found = set()
    for el in soup.find_all(attrs={"data-i18n-html": True}):
        found.add(norm("".join(str(c) for c in el.contents)))
        el.clear()  # its children are covered by the whole-sentence key
    for el in soup.find_all(True):
        for attr in ("placeholder", "title", "aria-label", "alt"):
            if el.get(attr) and has_letters(el[attr]):
                found.add(norm(el[attr]))
    for text in soup.find_all(string=True):
        if isinstance(text, (Comment, Doctype)) or text.parent.name in ("script", "style", "title", "textarea"):
            continue
        if has_letters(text) and not text.strip().startswith("{{"):
            found.add(norm(str(text)))
    return found


def js_keys():
    """Literal first arguments of _t('...') / _tp(n, '...', '...') in the frontend JS."""
    unescape = lambda s: re.sub(r"\\(.)", r"\1", s)
    keys = set()
    for name in ("app.js", "utils.js"):
        src = (STATIC / name).read_text(encoding="utf8")
        for m in re.finditer(r"""_t\(\s*(['"`])((?:\\.|(?!\1).)*)\1""", src):
            if "${" not in m.group(2):
                keys.add(unescape(m.group(2)))
        for m in re.finditer(r"""_tp\(\s*[^,]+,\s*(['"`])((?:\\.|(?!\1).)*)\1\s*,\s*(['"`])((?:\\.|(?!\3).)*)\3""", src):
            keys.update((unescape(m.group(2)), unescape(m.group(4))))
    # Looked up through the RULE_MATCH_LABELS table rather than a literal.
    keys.update(["Starts with", "Contains", "Ends with", "Exactly", "Matches regex"])
    return keys


def test_every_static_string_is_translated():
    es = load_es()
    missing = sorted(s for s in static_strings() if s not in es and s not in SAME_IN_BOTH)
    assert not missing, "index.html strings without a Spanish entry:\n" + "\n".join(missing)


def test_every_js_string_is_translated():
    es = load_es()
    missing = sorted(k for k in js_keys() if k not in es and k not in SAME_IN_BOTH)
    assert not missing, "app.js/utils.js strings without a Spanish entry:\n" + "\n".join(missing)


def test_placeholders_match_between_english_and_spanish():
    bad = []
    for en, es in load_es().items():
        if set(re.findall(r"\{(\w+)\}", en)) != set(re.findall(r"\{(\w+)\}", es)):
            bad.append(en)
    assert not bad, "placeholders differ:\n" + "\n".join(bad)


def test_default_categories_have_a_spanish_name():
    es = load_es()
    src = (ROOT / "backend" / "init_db.py").read_text(encoding="utf8")
    block = src[src.index("default_categories = ["):]
    names = re.findall(r'^\s*\("([^"]+)",\s*"(?:expense|income)"', block, re.M)
    assert names, "could not read the default category list"
    missing = [n for n in names if f"category:{n}" not in es and n != "Seguros Tarjetas"]
    assert not missing, f"default categories without a Spanish name: {missing}"


def test_spanish_is_neutral_no_tu_vos_usted():
    forbidden = re.compile(r"\b(tú|tu|tus|vos|usted|ustedes|te|ti|contigo|sos|vení|mirá)\b", re.I)
    offenders = [f"{k!r} -> {v!r}" for k, v in load_es().items() if forbidden.search(v)]
    assert not offenders, "Spanish should avoid tú/vos/usted forms:\n" + "\n".join(offenders)


def test_dictionary_has_no_unused_html_breakage():
    # Every Spanish value that contains HTML must open and close the same tags.
    for en, es in load_es().items():
        tags = lambda s: sorted(re.findall(r"</?(strong|em|span|br|ul|li)\b", s))
        assert tags(en) == tags(es), f"HTML tags differ for {en!r}"
