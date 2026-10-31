#!/usr/bin/env python3
"""Check internal links, JSON-LD, published prices, and the blog contract."""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://theaireadyexecutive.com"
ALLOWED_PRICES = {"0", "20000", "45000", "75000"}
ALLOWED_SAME_AS = {
    "https://www.linkedin.com/in/colin-dowling-4598113",
    "https://modernbusiness.life/",
    "https://rncld.com/",
    "https://www.bofubaby.com/",
    "https://www.withants.com/",
}
FORBIDDEN_ON_NEW = (
    "GoDaddy",
    "Alembic",
    "WP Engine",
    "Liquid Web",
    "AgentPress",
    "1905",
    "McKinsey",
    "Accenture",
    "Deloitte",
    "Bain",
)
NEW_PAGES = (
    "about/index.html",
    "advisory/index.html",
)


def visible(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def html_files() -> list[Path]:
    files = [ROOT / "index.html"]
    files.extend(sorted(ROOT.glob("*/index.html")))
    files.extend(sorted(ROOT.glob("blog/*/index.html")))
    return [path for path in files if path.is_file() and "content" not in path.parts]


def resolve(url: str, source: Path) -> tuple[Path | None, str | None]:
    raw = url.strip()
    if raw.startswith(("#", "mailto:", "javascript:", "data:")) or raw.startswith("//"):
        if raw.startswith("#"):
            return source, raw[1:]
        return None, None
    if raw.startswith(SITE):
        raw = raw[len(SITE) :] or "/"
    if not raw.startswith("/"):
        return None, None
    path, _, fragment = raw.partition("#")
    path = path.split("?", 1)[0]
    if path in ("", "/"):
        target = ROOT / "index.html"
    elif path.endswith("/"):
        target = ROOT / path.strip("/") / "index.html"
    else:
        target = ROOT / path.lstrip("/")
    return target, fragment or None


def types_of(node: dict) -> list[str]:
    kind = node.get("@type")
    if isinstance(kind, list):
        return kind
    if isinstance(kind, str):
        return [kind]
    return []


def walk_prices(node, found: list[str]) -> None:
    if isinstance(node, dict):
        if "price" in node and node.get("@type") == "Offer":
            found.append(str(node["price"]))
        for value in node.values():
            walk_prices(value, found)
    elif isinstance(node, list):
        for value in node:
            walk_prices(value, found)


def main() -> int:
    errors: list[str] = []
    pages = html_files()
    canonicals: set[str] = set()
    for path in pages:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT))
        if "@@" in text:
            errors.append(f"{rel}: unfilled template token")
        for url in re.findall(r'''(?:href|src)\s*=\s*["']([^"']+)["']''', text):
            target, fragment = resolve(url, path)
            if target is None:
                continue
            if not target.is_file():
                errors.append(f"{rel}: missing {url}")
                continue
            if fragment and f'id="{fragment}"' not in target.read_text(encoding="utf-8"):
                errors.append(f"{rel}: {url} has no id {fragment}")
        blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', text, re.S)
        graph_types: list[str] = []
        for block in blocks:
            try:
                data = json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel}: invalid JSON-LD ({exc})")
                continue
            nodes = data.get("@graph", [data])
            for node in nodes:
                graph_types.extend(types_of(node))
                if "Person" in types_of(node):
                    if node.get("name") != "Colin Dowling":
                        errors.append(f"{rel}: Person name is not Colin Dowling")
                    extra = set(node.get("sameAs") or []) - ALLOWED_SAME_AS
                    if extra:
                        errors.append(f"{rel}: unexpected sameAs {sorted(extra)}")
                if "FAQPage" in types_of(node):
                    questions = node.get("mainEntity") or []
                    if not 3 <= len(questions) <= 6 and rel.startswith("blog/") and rel != "blog/index.html":
                        errors.append(f"{rel}: post FAQ count is {len(questions)}")
                    page_text = visible(text)
                    for question in questions:
                        name = question.get("name", "")
                        answer = ((question.get("acceptedAnswer") or {}).get("text")) or ""
                        if name not in page_text:
                            errors.append(f"{rel}: FAQ question not visible: {name[:80]}")
                        if answer and answer not in page_text:
                            errors.append(f"{rel}: FAQ answer not visible: {answer[:80]}")
            prices: list[str] = []
            walk_prices(data, prices)
            for price in prices:
                if price not in ALLOWED_PRICES:
                    errors.append(f"{rel}: offer price {price} is not a published price")
                if price in {"6000", "2500", "2000", "1800", "1500", "1200", "9000"}:
                    errors.append(f"{rel}: comparison or offsite figure used as an Offer price")
        canonical = re.search(r'<link rel="canonical" href="([^"]+)"', text)
        if canonical:
            canonicals.add(canonical.group(1))
        if 'property="og:image"' not in text:
            errors.append(f"{rel}: missing og:image")
        if rel in NEW_PAGES or rel.startswith("blog/"):
            for banned in FORBIDDEN_ON_NEW:
                if banned in text:
                    errors.append(f"{rel}: names {banned}")
        if rel.startswith("blog/") and rel != "blog/index.html":
            if 'href="/about/"' not in text or "Colin Dowling" not in text:
                errors.append(f"{rel}: byline does not link to /about/")
            if "utm_content=inbody" not in text or "utm_content=post_end" not in text:
                errors.append(f"{rel}: missing blog CTA markers")
            slug = path.parent.name
            if f"utm_campaign=blog_{slug}" not in text:
                errors.append(f"{rel}: utm_campaign does not match the slug")
            if 'class="takeaways"' not in text:
                errors.append(f"{rel}: missing key takeaways")
            needed = {"BlogPosting", "FAQPage", "BreadcrumbList", "Person"}
            if not needed <= set(graph_types):
                errors.append(f"{rel}: schema types {sorted(set(graph_types))}")

    home = (ROOT / "index.html").read_text(encoding="utf-8")
    home_data = json.loads(re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', home, re.S).group(1))
    home_types = []
    for node in home_data["@graph"]:
        home_types.extend(types_of(node))
    for required in ("Organization", "Person", "WebSite"):
        if required not in home_types:
            errors.append(f"homepage missing {required}")
    for href in ("/advisory/", "/blog/", "/15minutesairoadmap/", "/about/"):
        if f'href="{href}"' not in home:
            errors.append(f"homepage nav missing {href}")

    advisory = (ROOT / "advisory" / "index.html").read_text(encoding="utf-8")
    if "calendly.com/30minutechat/20-minute-ai-ready-executive" not in advisory:
        errors.append("advisory page has no Calendly CTA")
    advisory_data = json.loads(re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', advisory, re.S).group(1))
    advisory_types = []
    for node in advisory_data["@graph"]:
        advisory_types.extend(types_of(node))
    for required in ("Service", "FAQPage", "BreadcrumbList"):
        if required not in advisory_types:
            errors.append(f"advisory page missing {required}")
    if "Offer" not in json.dumps(advisory_data):
        errors.append("advisory page missing Offer")

    about = (ROOT / "about" / "index.html").read_text(encoding="utf-8")
    if "https://modernbusiness.life/" not in about or 'href="/15minutesairoadmap/"' not in about:
        errors.append("about page missing the podcast link or the roadmap CTA")
    about_data = json.loads(re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', about, re.S).group(1))
    about_types = []
    for node in about_data["@graph"]:
        about_types.extend(types_of(node))
    for required in ("AboutPage", "Person"):
        if required not in about_types:
            errors.append(f"about page missing {required}")

    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap)
    for loc in locs:
        target, _fragment = resolve(loc, ROOT / "sitemap.xml")
        if target is None or not target.is_file():
            errors.append(f"sitemap loc does not resolve: {loc}")
    for canonical in canonicals:
        if canonical not in locs:
            errors.append(f"canonical missing from sitemap: {canonical}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"{len(errors)} problem(s)", file=sys.stderr)
        return 1
    print(f"checked {len(pages)} pages, {len(locs)} sitemap URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
