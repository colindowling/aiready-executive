#!/usr/bin/env python3
"""Build the AIReady Executive blog from Markdown in content/blog/.

Writes blog/index.html, blog/<slug>/index.html, refreshes sitemap.xml, and
refreshes the spoke list on advisory/index.html. Standard library only.

    python3 scripts/build_blog.py
    python3 scripts/build_blog.py --self-test
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://theaireadyexecutive.com"
ORG_ID = f"{SITE}/#organization"
PERSON_ID = f"{SITE}/about/#colin"
PERSON_NAME = "Colin Dowling"
PERSON_SAME_AS = [
    "https://www.linkedin.com/in/colin-dowling-4598113",
    "https://modernbusiness.life/",
    "https://rncld.com/",
    "https://www.bofubaby.com/",
    "https://www.withants.com/",
]
ORG_DESCRIPTION = (
    "A fixed-fee, fixed-timeline advisory engagement that takes C-suite leaders "
    "and boards from AI gap to boardroom-ready in 30 days — executive alignment "
    "above the Chief AI Officer layer, delivered by a senior practitioner."
)
OG_IMAGE = f"{SITE}/assets/og.jpg"
DEFAULT_CTA = "/15minutesairoadmap/"

# Topic hubs. A post may override these with an explicit hub path.
TOPIC_HUBS = {
    "engagement": "/advisory/",
    "readiness": "/advisory/#framework",
    "roadmap": "/15minutesairoadmap/",
    "board": "/advisory/",
    "fees": "/advisory/#fees",
}

BLOG_H1 = "Notes on the engagement"
BLOG_LEDE = (
    "Briefings that stay inside what this site already states: the 30-day advisory, "
    "the published fees, and the free 15-minute roadmap session."
)
BLOG_DESCRIPTION = (
    "Notes from AIReady Executive on the 30-day advisory engagement, the published fees, "
    "and the free 15-minute roadmap session."
)

CTA_MID = {
    "eyebrow": "15 minutes",
    "title": "Three quick wins and a 90-day roadmap.",
    "body": (
        "The free session on this site: three quick wins, a 90-day roadmap, and the five "
        "questions that put you back in charge of the room. Yours to keep."
    ),
    "button": "Get the Roadmap",
}
CTA_END = {
    "eyebrow": "Next step",
    "title": "See the 15-minute roadmap session.",
    "body": "No pitch. No deck. Work with us, don't work with us — the quick wins and the roadmap are yours to keep.",
    "button": "Book My 15 Minutes",
}

STATIC_PAGES = [
    # (path, lastmod, changefreq, priority)
    ("/", "2026-10-31", "monthly", "1.0"),
    ("/advisory/", "2026-10-31", "monthly", "0.9"),
    ("/about/", "2026-10-31", "monthly", "0.7"),
    ("/15minutesairoadmap/", "2026-10-31", "monthly", "0.8"),
    ("/blog/", "2026-10-31", "weekly", "0.8"),
    ("/contact/", "2026-10-31", "yearly", "0.8"),
]

MONTHS = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCAL_PATH_RE = re.compile(r"^/(?:[a-z0-9-]+/)*(?:#[a-z0-9-]+)?$")
DURATION_RE = re.compile(r"^PT(?:\d+H)?(?:\d+M)?(?:\d+S)?$")
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class BuildError(Exception):
    pass


def die(message: str) -> None:
    raise BuildError(message)


def format_date(iso: str) -> str:
    year, month, day = (int(part) for part in iso.split("-"))
    return f"{MONTHS[month]} {day}, {year}"


def parse_iso_date(value: str, label: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        die(f"{label} must be YYYY-MM-DD, got {value!r}")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        die(f"{label} is not a real date: {value} ({exc})")
    return value


def decode_double(body: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            out.append({"n": "\n", '"': '"', "\\": "\\"}.get(nxt, nxt))
            i += 2
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def parse_scalar(raw: str):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return decode_double(raw[1:-1])
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1].replace("''", "'")
    if raw in ("true", "True", "TRUE"):
        return True
    if raw in ("false", "False", "FALSE"):
        return False
    if raw in ("null", "Null", "~"):
        return None
    return raw


def split_key(text: str) -> tuple[str, str]:
    if ":" not in text:
        die(f"expected key: value, got {text!r}")
    key, rest = text.split(":", 1)
    key = key.strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", key):
        die(f"invalid front-matter key {key!r}")
    return key, rest.strip()


def dedent(lines: list[str]) -> list[str]:
    if not lines:
        return []
    indents = [len(line) - len(line.lstrip(" ")) for line in lines]
    cut = min(indents)
    return [line[cut:] for line in lines]


def fold_text(lines: list[str], style: str) -> str:
    dedented = dedent(lines)
    text = "\n".join(dedented).strip()
    if style.startswith(">"):
        text = re.sub(r"\s*\n\s*", " ", text).strip()
    return text


def parse_map(lines: list[str]) -> dict:
    data: dict = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip(" "))
        if indent != 0:
            die(f"unexpected indent in front matter: {line!r}")
        key, rest = split_key(line.strip())
        i += 1
        if rest in ("", ">", "|", ">-", "|-"):
            child: list[str] = []
            while i < len(lines) and (len(lines[i]) - len(lines[i].lstrip(" "))) > 0:
                child.append(lines[i])
                i += 1
            data[key] = interpret(rest, child)
        else:
            data[key] = parse_scalar(rest)
    return data


def interpret(style: str, child: list[str]):
    if style in (">", "|", ">-", "|-"):
        return fold_text(child, style)
    if not child:
        return {}
    content = dedent(child)
    if content[0].startswith("- "):
        return parse_list(content)
    return parse_map(content)


def parse_list(lines: list[str]) -> list:
    items = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith("- "):
            die(f"expected a list item, got {lines[i]!r}")
        rest = lines[i][2:].strip()
        i += 1
        nested: list[str] = []
        while i < len(lines) and not lines[i].startswith("- "):
            if not lines[i].startswith(" "):
                die(f"list item continuation must be indented: {lines[i]!r}")
            nested.append(lines[i])
            i += 1
        items.append(parse_list_item(rest, nested))
    return items


def parse_list_item(rest: str, nested: list[str]):
    if not nested:
        if rest[:1] in ('"', "'"):
            return parse_scalar(rest)
        if ":" in rest:
            key, val = split_key(rest)
            if val:
                return {key: parse_scalar(val)}
        return parse_scalar(rest)
    if rest in ("", ">", "|", ">-", "|-"):
        return interpret(rest, nested)
    key, val = split_key(rest)
    item: dict = {}
    child = dedent(nested)
    if val in ("", ">", "|", ">-", "|-"):
        # The value of this first key is the following indented block, and any
        # sibling keys sit at the left edge of that block. Not used by the
        # supported template; reject rather than guess.
        die(f"put a folded value on its own key, not on the dash line ({key})")
    item[key] = parse_scalar(val)
    if child:
        item.update(parse_map(child))
    return item


def split_front_matter(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        die("post must start with a --- front-matter block")
    end = text.find("\n---\n", 4)
    if end == -1:
        die("front matter is not closed with ---")
    raw = text[4:end]
    body = text[end + 5 :].strip()
    lines = []
    for line in raw.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        lines.append(line.rstrip())
    if not lines:
        die("front matter is empty")
    return parse_map(lines), body


def as_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    die(f"expected true or false, got {value!r}")


def local_path(value: str, label: str) -> str:
    if not isinstance(value, str) or not LOCAL_PATH_RE.fullmatch(value):
        die(f"{label} must be a site path like /advisory/ or /advisory/#fees, got {value!r}")
    return value


def inline(text: str, where: str) -> str:
    pattern = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*")
    out: list[str] = []
    pos = 0
    for match in pattern.finditer(text):
        out.append(html.escape(text[pos : match.start()]))
        if match.group(1) is not None:
            href = match.group(2)
            if href.startswith("/") and not href.startswith("//"):
                path = href.split("#", 1)[0].split("?", 1)[0]
                if not path.endswith("/"):
                    die(f"{where}: internal links must use a trailing slash ({href})")
            elif href.startswith("https://") or href.startswith("mailto:"):
                pass
            else:
                die(f"{where}: unsupported link {href}")
            out.append(
                f'<a href="{html.escape(href, quote=True)}">{html.escape(match.group(1))}</a>'
            )
        elif match.group(3) is not None:
            out.append(f"<strong>{html.escape(match.group(3))}</strong>")
        else:
            out.append(f"<em>{html.escape(match.group(4))}</em>")
        pos = match.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def parse_markdown(body: str, where: str) -> list[tuple]:
    lines = body.replace("\r\n", "\n").split("\n")
    blocks: list[tuple] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("### "):
            blocks.append(("h3", line[4:].strip()))
            i += 1
        elif line.startswith("## "):
            blocks.append(("h2", line[3:].strip()))
            i += 1
        elif line.startswith("# "):
            die(f"{where}: the title comes from front matter. Use ## for sections, not #.")
        elif line.startswith("> "):
            parts = [line[2:].strip()]
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                parts.append(lines[i][2:].strip())
                i += 1
            blocks.append(("quote", " ".join(parts)))
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            blocks.append(("ul", items))
        elif re.match(r"\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"\d+\. ", lines[i]):
                items.append(re.sub(r"^\d+\. ", "", lines[i]).strip())
                i += 1
            blocks.append(("ol", items))
        else:
            parts = [line.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not _block_start(lines[i]):
                parts.append(lines[i].strip())
                i += 1
            blocks.append(("p", " ".join(parts)))
    return blocks


def _block_start(line: str) -> bool:
    return line.startswith(("## ", "### ", "# ", "> ", "- ")) or bool(re.match(r"\d+\. ", line))


def render_body(blocks: list[tuple], where: str, mid_cta: str) -> str:
    bits: list[tuple[str, str]] = []
    for kind, data in blocks:
        if kind == "h2":
            bits.append((kind, f"<h2>{inline(data, where)}</h2>"))
        elif kind == "h3":
            bits.append((kind, f"<h3>{inline(data, where)}</h3>"))
        elif kind == "p":
            bits.append((kind, f"<p>{inline(data, where)}</p>"))
        elif kind == "quote":
            bits.append((kind, f"<blockquote><p>{inline(data, where)}</p></blockquote>"))
        elif kind == "ul":
            items = "".join(f"<li>{inline(item, where)}</li>" for item in data)
            bits.append((kind, f"<ul>{items}</ul>"))
        elif kind == "ol":
            items = "".join(f"<li>{inline(item, where)}</li>" for item in data)
            bits.append((kind, f"<ol>{items}</ol>"))
    h2_at = [index for index, (kind, _) in enumerate(bits) if kind == "h2"]
    if len(h2_at) < 2:
        die(f"{where}: write at least two ## sections so the mid-article CTA can follow section 2")
    insert_at = h2_at[2] if len(h2_at) >= 3 else len(bits)
    pieces = [fragment for _, fragment in bits]
    pieces.insert(insert_at, mid_cta)
    return "\n".join(pieces)


def cta_href(path: str, slug: str, content: str) -> str:
    query = (
        f"utm_source=blog&utm_medium=internal"
        f"&utm_campaign=blog_{slug}&utm_content={content}"
    )
    join = "&" if "?" in path else "?"
    return f"{path}{join}{query}"


def cta_html(copy: dict, href: str, assessment_href: str) -> str:
    return (
        '<aside class="post-cta">\n'
        f'  <p class="section-eyebrow">{html.escape(copy["eyebrow"])}</p>\n'
        f'  <p class="cta-title">{html.escape(copy["title"])}</p>\n'
        f"  <p>{html.escape(copy['body'])}</p>\n"
        '  <div class="cta-actions">\n'
        f'    <a class="btn-primary" href="{html.escape(href, quote=True)}">{html.escape(copy["button"])}</a>\n'
        f'    <a class="btn-outline" href="{html.escape(assessment_href, quote=True)}">Book an Assessment</a>\n'
        "  </div>\n"
        "</aside>"
    )


def json_script(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    raw = raw.replace("<", "\\u003c")
    return f'<script type="application/ld+json">\n{raw}\n</script>'


def organization_node() -> dict:
    return {
        "@type": "Organization",
        "@id": ORG_ID,
        "name": "AIReady Executive",
        "url": f"{SITE}/",
        "description": ORG_DESCRIPTION,
        "logo": {"@type": "ImageObject", "url": f"{SITE}/favicon.svg"},
    }


def person_node() -> dict:
    return {
        "@type": "Person",
        "@id": PERSON_ID,
        "name": PERSON_NAME,
        "url": f"{SITE}/about/",
        "jobTitle": "Senior practitioner",
        "worksFor": {"@id": ORG_ID},
        "sameAs": list(PERSON_SAME_AS),
    }


def fill(template: str, **kwargs: str) -> str:
    for key, value in kwargs.items():
        token = f"@@{key}@@"
        if token not in template:
            die(f"template is missing {token}")
        template = template.replace(token, value)
    leftover = re.findall(r"@@[A-Z0-9_]+@@", template)
    if leftover:
        die(f"unfilled template tokens: {', '.join(leftover)}")
    return template


def nav_html(current: str) -> str:
    def link(href: str, label: str, key: str) -> str:
        current_attr = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}" class="nav-link"{current_attr}>{label}</a>'

    return (
        '<nav class="site-nav">\n'
        '  <a href="/" class="nav-logo">AIReady <span>Executive</span></a>\n'
        '  <div class="nav-links">\n'
        f"    {link('/advisory/', 'Advisory', 'advisory')}\n"
        f"    {link('/blog/', 'Blog', 'blog')}\n"
        f"    {link('/15minutesairoadmap/', '15-Min Roadmap', 'roadmap')}\n"
        f"    {link('/about/', 'About', 'about')}\n"
        '    <a href="/contact/" class="nav-cta">Apply Now</a>\n'
        "  </div>\n"
        "</nav>"
    )


def footer_html() -> str:
    return """<footer>
  <a href="/" class="nav-logo">AIReady <span>Executive</span></a>
  <nav class="footer-links" aria-label="Footer">
    <a href="/advisory/">Advisory</a>
    <a href="/blog/">Blog</a>
    <a href="/15minutesairoadmap/">15-Min Roadmap</a>
    <a href="/about/">About</a>
    <a href="/contact/">Contact</a>
  </nav>
  <div>© 2026 AIReady Executive. All rights reserved.</div>
</footer>"""


def hub_label(hub: str) -> str:
    path = hub.split("#", 1)[0]
    if not path.endswith("/"):
        path += "/"
    return {
        "/advisory/": "Advisory",
        "/about/": "About",
        "/15minutesairoadmap/": "15-minute roadmap session",
        "/contact/": "Contact",
        "/blog/": "Blog",
        "/": "Home",
    }.get(path, path)


def topic_label(topic: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    return " ".join(part.capitalize() for part in topic.split("-"))


@dataclass
class Post:
    slug: str
    title: str
    description: str
    date: str
    updated: str
    topic: str
    topic_label: str
    hub: str
    cta: str
    faqs: list[tuple[str, str]]
    takeaways: list[str]
    video: dict | None
    body: str
    source: str


@dataclass
class Loaded:
    posts: list[Post] = field(default_factory=list)


def require_string(data: dict, key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        die(f"{where}: front matter {key} is required")
    return value.strip()


def load_video(raw, where: str) -> dict | None:
    if raw in (None, {}, False):
        return None
    if not isinstance(raw, dict):
        die(f"{where}: video must be a mapping")
    youtube_id = raw.get("youtube_id")
    if not isinstance(youtube_id, str) or not YOUTUBE_ID_RE.fullmatch(youtube_id):
        die(f"{where}: video.youtube_id must be an 11-character YouTube id")
    name = raw.get("name")
    description = raw.get("description")
    if not isinstance(name, str) or not name.strip():
        die(f"{where}: video.name is required")
    if not isinstance(description, str) or not description.strip():
        die(f"{where}: video.description is required")
    upload = raw.get("upload_date")
    if not isinstance(upload, str):
        die(f"{where}: video.upload_date is required (YYYY-MM-DD)")
    upload = parse_iso_date(upload, f"{where}: video.upload_date")
    thumbnail = raw.get("thumbnail_url") or f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg"
    if not isinstance(thumbnail, str) or not thumbnail.startswith("https://"):
        die(f"{where}: video.thumbnail_url must be an https URL")
    duration = raw.get("duration")
    if duration is not None:
        if not isinstance(duration, str) or not DURATION_RE.fullmatch(duration) or duration == "PT":
            die(f"{where}: video.duration must look like PT5M30S")
    return {
        "youtube_id": youtube_id,
        "name": name.strip(),
        "description": description.strip(),
        "upload_date": upload,
        "thumbnail_url": thumbnail,
        "duration": duration,
    }


def load_posts(root: Path) -> list[Post]:
    folder = root / "content" / "blog"
    if not folder.is_dir():
        die(f"missing {folder}")
    posts: list[Post] = []
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith("_") or path.name.lower() == "readme.md":
            continue
        data, body = split_front_matter(path.read_text(encoding="utf-8"))
        where = path.name
        if not as_bool(data.get("published"), True):
            continue
        slug = require_string(data, "slug", where)
        if not SLUG_RE.fullmatch(slug):
            die(f"{where}: slug must be lowercase words separated by hyphens")
        if path.stem != slug:
            die(f"{where}: filename must be {slug}.md")
        title = require_string(data, "title", where)
        description = require_string(data, "description", where)
        date = parse_iso_date(require_string(data, "date", where), f"{where}: date")
        updated_raw = data.get("updated")
        updated = parse_iso_date(updated_raw, f"{where}: updated") if isinstance(updated_raw, str) else date
        topic = require_string(data, "topic", where)
        if not SLUG_RE.fullmatch(topic):
            die(f"{where}: topic must be a short hyphenated label")
        if "hub" in data:
            hub = local_path(require_string(data, "hub", where), f"{where}: hub")
        elif topic in TOPIC_HUBS:
            hub = TOPIC_HUBS[topic]
        else:
            known = ", ".join(sorted(TOPIC_HUBS))
            die(f"{where}: unknown topic {topic!r}. Set hub: or use one of: {known}")
        cta = local_path(data["cta"], f"{where}: cta") if "cta" in data else DEFAULT_CTA
        faqs_raw = data.get("faqs")
        if not isinstance(faqs_raw, list) or not 3 <= len(faqs_raw) <= 5:
            die(f"{where}: faqs must be a list of 3 to 5 questions")
        faqs: list[tuple[str, str]] = []
        for item in faqs_raw:
            if not isinstance(item, dict) or not isinstance(item.get("q"), str) or not isinstance(item.get("a"), str):
                die(f"{where}: each faq needs q and a strings")
            question = item["q"].strip()
            answer = item["a"].strip()
            if not question or not answer:
                die(f"{where}: faq q and a cannot be empty")
            faqs.append((question, answer))
        takeaways_raw = data.get("takeaways")
        if not isinstance(takeaways_raw, list) or not takeaways_raw:
            die(f"{where}: takeaways must be a non-empty list")
        takeaways = []
        for item in takeaways_raw:
            if not isinstance(item, str) or not item.strip():
                die(f"{where}: each takeaway must be a string")
            takeaways.append(item.strip())
        if not body:
            die(f"{where}: the post body is empty")
        posts.append(
            Post(
                slug=slug,
                title=title,
                description=description,
                date=date,
                updated=updated,
                topic=topic,
                topic_label=topic_label(topic, data.get("topic_label") if isinstance(data.get("topic_label"), str) else None),
                hub=hub,
                cta=cta,
                faqs=faqs,
                takeaways=takeaways,
                video=load_video(data.get("video"), where),
                body=body,
                source=path.name,
            )
        )
    posts.sort(key=lambda post: (post.date, post.slug), reverse=True)
    return posts


def video_html(video: dict | None) -> tuple[str, str]:
    if not video:
        return "", ""
    embed = f"https://www.youtube-nocookie.com/embed/{video['youtube_id']}"
    play = html.escape(embed + "?autoplay=1", quote=True)
    thumb = html.escape(video["thumbnail_url"], quote=True)
    name = html.escape(video["name"])
    description = html.escape(video["description"])
    markup = (
        '<figure class="video-slot">\n'
        f'  <button type="button" class="video-facade" data-embed="{play}" data-title="{html.escape(video["name"], quote=True)}" aria-label="Play video: {name}">\n'
        f'    <img src="{thumb}" alt="">\n'
        '    <span class="video-play" aria-hidden="true">Play</span>\n'
        "  </button>\n"
        f"  <figcaption>{name}</figcaption>\n"
        f'  <p class="video-desc">{description}</p>\n'
        "</figure>"
    )
    script = """<script>
document.querySelectorAll(".video-facade").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var iframe = document.createElement("iframe");
    iframe.className = "video-frame";
    iframe.src = btn.getAttribute("data-embed");
    iframe.title = btn.getAttribute("data-title") || "Video";
    iframe.setAttribute("allow", "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share");
    iframe.setAttribute("allowfullscreen", "");
    iframe.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
    btn.replaceWith(iframe);
  });
});
</script>"""
    return markup, script


def video_node(video: dict, url: str) -> dict:
    node = {
        "@type": "VideoObject",
        "@id": f"{url}#video",
        "name": video["name"],
        "description": video["description"],
        "thumbnailUrl": video["thumbnail_url"],
        "uploadDate": video["upload_date"],
        "embedUrl": f"https://www.youtube-nocookie.com/embed/{video['youtube_id']}",
        "publisher": {"@id": ORG_ID},
    }
    if video.get("duration"):
        node["duration"] = video["duration"]
    return node


def related_html(post: Post, posts: list[Post]) -> str:
    items = [
        f'<li><a href="{html.escape(post.hub, quote=True)}">{html.escape(hub_label(post.hub))}</a></li>'
    ]
    cta_path = post.cta.split("#", 1)[0].rstrip("/")
    hub_path = post.hub.split("#", 1)[0].rstrip("/")
    if cta_path and cta_path != hub_path:
        items.append(
            f'<li><a href="{html.escape(post.cta, quote=True)}">{html.escape(hub_label(post.cta))}</a></li>'
        )
    siblings = [other for other in posts if other.slug != post.slug and other.topic == post.topic][:2]
    for other in siblings:
        items.append(
            f'<li><a href="/blog/{html.escape(other.slug, quote=True)}/">{html.escape(other.title)}</a></li>'
        )
    return (
        '<aside class="related">\n'
        '  <p class="section-eyebrow">Related</p>\n'
        f"  <ul>\n    " + "\n    ".join(items) + "\n  </ul>\n"
        "</aside>"
    )


def render_post(post: Post, posts: list[Post]) -> str:
    url = f"{SITE}/blog/{post.slug}/"
    mid = cta_html(
        CTA_MID,
        cta_href(post.cta, post.slug, "inbody"),
        cta_href("/contact/", post.slug, "inbody"),
    )
    end = cta_html(
        CTA_END,
        cta_href(post.cta, post.slug, "post_end"),
        cta_href("/contact/", post.slug, "post_end"),
    )
    body = render_body(parse_markdown(post.body, post.source), post.source, mid)
    takeaways = "\n".join(f"    <li>{html.escape(item)}</li>" for item in post.takeaways)
    faqs = []
    for question, answer in post.faqs:
        faqs.append(
            '<div class="faq-item">\n'
            f"  <h3>{html.escape(question)}</h3>\n"
            f"  <p>{html.escape(answer)}</p>\n"
            "</div>"
        )
    video_markup, video_script = video_html(post.video)
    graph = [
        organization_node(),
        person_node(),
        {
            "@type": "BlogPosting",
            "@id": f"{url}#article",
            "headline": post.title,
            "description": post.description,
            "datePublished": post.date,
            "dateModified": post.updated,
            "mainEntityOfPage": url,
            "url": url,
            "image": OG_IMAGE,
            "articleSection": post.topic_label,
            "author": {"@id": PERSON_ID},
            "publisher": {"@id": ORG_ID},
            "isPartOf": {"@id": f"{SITE}/blog/#blog"},
        },
        {
            "@type": "FAQPage",
            "@id": f"{url}#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
                for question, answer in post.faqs
            ],
        },
        {
            "@type": "BreadcrumbList",
            "@id": f"{url}#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"{SITE}/blog/"},
                {"@type": "ListItem", "position": 3, "name": post.title, "item": url},
            ],
        },
    ]
    if post.video:
        node = video_node(post.video, url)
        graph.append(node)
        posting = next(item for item in graph if item.get("@type") == "BlogPosting")
        posting["video"] = {"@id": node["@id"]}
    crumbs = (
        '<nav class="crumbs" aria-label="Breadcrumb">\n'
        '  <a href="/">Home</a>\n'
        '  <span aria-hidden="true">/</span>\n'
        '  <a href="/blog/">Blog</a>\n'
        '  <span aria-hidden="true">/</span>\n'
        f'  <span aria-current="page">{html.escape(post.title)}</span>\n'
        "</nav>"
    )
    return fill(
        POST_TEMPLATE,
        TITLE=html.escape(post.title),
        DESCRIPTION=html.escape(post.description),
        CANONICAL=url,
        JSONLD=json_script({"@context": "https://schema.org", "@graph": graph}),
        NAV=nav_html("blog"),
        FOOTER=footer_html(),
        CRUMBS=crumbs,
        TOPIC=html.escape(post.topic_label),
        DATE_ISO=post.date,
        DATE_DISPLAY=html.escape(format_date(post.date)),
        UPDATED_NOTE=(
            f' <span class="updated">Updated {html.escape(format_date(post.updated))}</span>'
            if post.updated != post.date
            else ""
        ),
        DECK=html.escape(post.description),
        TAKEAWAYS=takeaways,
        VIDEO=video_markup,
        BODY=body,
        END_CTA=end,
        FAQS="\n".join(faqs),
        RELATED=related_html(post, posts),
        VIDEO_SCRIPT=video_script,
    )


def render_index(posts: list[Post]) -> str:
    if posts:
        items = []
        for post in posts:
            items.append(
                "<li>\n"
                f'  <p class="post-meta"><time datetime="{post.date}">{html.escape(format_date(post.date))}</time>'
                f' <span aria-hidden="true">·</span> {html.escape(post.topic_label)}</p>\n'
                f'  <h2><a href="/blog/{html.escape(post.slug, quote=True)}/">{html.escape(post.title)}</a></h2>\n'
                f"  <p>{html.escape(post.description)}</p>\n"
                "</li>"
            )
        listing = '<ul class="post-list">\n' + "\n".join(items) + "\n</ul>"
    else:
        listing = '<p class="empty">No notes published yet.</p>'
    blog_node = {
        "@type": ["Blog", "CollectionPage"],
        "@id": f"{SITE}/blog/#blog",
        "name": BLOG_H1,
        "description": BLOG_DESCRIPTION,
        "url": f"{SITE}/blog/",
        "publisher": {"@id": ORG_ID},
        "author": {"@id": PERSON_ID},
    }
    item_list = {
        "@type": "ItemList",
        "@id": f"{SITE}/blog/#items",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": post.title,
                "url": f"{SITE}/blog/{post.slug}/",
            }
            for index, post in enumerate(posts, start=1)
        ],
    }
    graph = [
        organization_node(),
        person_node(),
        blog_node,
        item_list,
        {
            "@type": "BreadcrumbList",
            "@id": f"{SITE}/blog/#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"{SITE}/blog/"},
            ],
        },
    ]
    if posts:
        blog_node["blogPost"] = [
            {
                "@type": "BlogPosting",
                "headline": post.title,
                "url": f"{SITE}/blog/{post.slug}/",
                "datePublished": post.date,
                "author": {"@id": PERSON_ID},
            }
            for post in posts
        ]
    crumbs = (
        '<nav class="crumbs" aria-label="Breadcrumb">\n'
        '  <a href="/">Home</a>\n'
        '  <span aria-hidden="true">/</span>\n'
        '  <span aria-current="page">Blog</span>\n'
        "</nav>"
    )
    return fill(
        INDEX_TEMPLATE,
        TITLE=html.escape(BLOG_H1),
        DESCRIPTION=html.escape(BLOG_DESCRIPTION),
        CANONICAL=f"{SITE}/blog/",
        JSONLD=json_script({"@context": "https://schema.org", "@graph": graph}),
        NAV=nav_html("blog"),
        FOOTER=footer_html(),
        CRUMBS=crumbs,
        H1=html.escape(BLOG_H1),
        LEDE=html.escape(BLOG_LEDE),
        LISTING=listing,
    )


def write_sitemap(root: Path, posts: list[Post]) -> None:
    urls = []
    for path, lastmod, changefreq, priority in STATIC_PAGES:
        urls.append((f"{SITE}{path}", lastmod, changefreq, priority))
    for post in sorted(posts, key=lambda item: item.slug):
        urls.append((f"{SITE}/blog/{post.slug}/", post.updated, "monthly", "0.7"))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod, changefreq, priority in urls:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{html.escape(loc)}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                f"    <changefreq>{changefreq}</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    (root / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def inject_spokes(root: Path, posts: list[Post]) -> None:
    page = root / "advisory" / "index.html"
    if not page.is_file():
        return
    text = page.read_text(encoding="utf-8")
    start = "<!-- blog-spokes:start -->"
    end = "<!-- blog-spokes:end -->"
    if start not in text or end not in text:
        return
    spokes = [post for post in posts if post.hub.split("#", 1)[0].rstrip("/") == "/advisory"]
    if spokes:
        items = []
        for post in spokes:
            items.append(
                "<li>\n"
                f'  <a href="/blog/{html.escape(post.slug, quote=True)}/">{html.escape(post.title)}</a>\n'
                f"  <p>{html.escape(post.description)}</p>\n"
                "</li>"
            )
        inner = '<ul class="spoke-list">\n' + "\n".join(items) + "\n</ul>"
    else:
        inner = '<p class="section-body">No notes published yet.</p>'
    replacement = f"{start}\n{inner}\n{end}"
    updated = re.sub(re.escape(start) + r".*?" + re.escape(end), replacement, text, count=1, flags=re.S)
    page.write_text(updated, encoding="utf-8")


def build(root: Path) -> list[Post]:
    posts = load_posts(root)
    blog = root / "blog"
    blog.mkdir(exist_ok=True)
    slugs = {post.slug for post in posts}
    for child in list(blog.iterdir()):
        if child.is_dir() and child.name not in slugs:
            shutil.rmtree(child)
    for post in posts:
        destination = blog / post.slug / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_post(post, posts), encoding="utf-8")
    (blog / "index.html").write_text(render_index(posts), encoding="utf-8")
    write_sitemap(root, posts)
    inject_spokes(root, posts)
    return posts


PAGE_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --black: #080808;
    --off-black: #111111;
    --white: #F5F5F0;
    --gold: #C9A84C;
    --gold-dim: #8A6F33;
    --rule: rgba(201,168,76,0.18);
    --text-dim: rgba(245,245,240,0.66);
    --text-mid: rgba(245,245,240,0.86);
  }
  html { scroll-behavior: smooth; }
  body {
    background: var(--black);
    color: var(--white);
    font-family: 'Manrope', sans-serif;
    font-weight: 300;
    font-size: 17px;
    line-height: 1.7;
    -webkit-font-smoothing: antialiased;
  }
  a:focus-visible, button:focus-visible { outline: 2px solid var(--gold); outline-offset: 3px; }
  .site-nav {
    position: fixed;
    top: 0; left: 0; right: 0;
    z-index: 100;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1.5rem;
    padding: 1.4rem 4rem;
    background: rgba(8,8,8,0.92);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--rule);
  }
  .nav-logo {
    font-weight: 300;
    font-size: 0.8rem;
    letter-spacing: 0.35em;
    text-transform: uppercase;
    color: var(--white);
    text-decoration: none;
    white-space: nowrap;
    flex: 0 0 auto;
  }
  .nav-logo span { color: var(--gold); }
  .nav-logo:visited { color: var(--white); }
  .nav-logo:visited span { color: var(--gold); }
  .nav-links { display: flex; align-items: center; gap: 1.6rem; flex-wrap: wrap; justify-content: flex-end; }
  .nav-link {
    font-size: 0.72rem;
    font-weight: 400;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-mid);
    text-decoration: none;
  }
  .nav-link:hover, .nav-link[aria-current="page"] { color: var(--gold); }
  .nav-cta {
    font-size: 0.72rem;
    font-weight: 400;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--gold);
    text-decoration: none;
    border: 1px solid var(--gold-dim);
    padding: 0.5rem 1.4rem;
    transition: background 0.2s, color 0.2s;
  }
  .nav-cta:hover { background: var(--gold); color: var(--black); }
  .page { max-width: 760px; margin: 0 auto; padding: 8.5rem 1.5rem 5rem; }
  .crumbs { font-size: 0.68rem; letter-spacing: 0.16em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 1.6rem; display: flex; flex-wrap: wrap; gap: 0.55rem; }
  .crumbs a { color: var(--text-dim); text-decoration: none; }
  .crumbs a:hover { color: var(--gold); }
  .section-eyebrow { font-size: 0.68rem; font-weight: 400; letter-spacing: 0.4em; text-transform: uppercase; color: var(--gold); margin-bottom: 1rem; }
  h1 { font-family: 'Cormorant Garamond', serif; font-weight: 500; font-size: clamp(2.2rem, 5vw, 3.5rem); line-height: 1.12; margin-bottom: 1rem; }
  .deck, .lede { color: var(--text-mid); font-size: 1.05rem; line-height: 1.75; max-width: 62ch; }
  .post-meta { margin: 1.1rem 0 0; font-size: 0.75rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-dim); }
  .post-meta a { color: var(--gold); text-decoration: none; text-transform: none; letter-spacing: 0.02em; }
  .post-meta a:hover { text-decoration: underline; }
  .nav-link:visited { color: var(--text-mid); }
  .nav-link[aria-current="page"]:visited { color: var(--gold); }
  .updated { margin-left: 0.6rem; }
  .takeaways { border: 1px solid var(--rule); background: rgba(201,168,76,0.04); padding: 1.5rem 1.6rem 1.2rem; margin: 2rem 0 2.2rem; }
  .takeaways ul { list-style: none; }
  .takeaways li { position: relative; padding: 0.45rem 0 0.45rem 1.2rem; color: var(--text-mid); font-size: 0.95rem; }
  .takeaways li::before { content: '—'; position: absolute; left: 0; color: var(--gold); }
  .video-slot { margin: 0 0 2.2rem; }
  .video-facade { position: relative; display: block; width: 100%; aspect-ratio: 16 / 9; padding: 0; border: 1px solid var(--rule); background: #000; cursor: pointer; }
  .video-facade img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .video-play { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); border: 1px solid var(--gold); color: var(--gold); letter-spacing: 0.18em; text-transform: uppercase; font-size: 0.72rem; padding: 0.7rem 1.1rem; background: rgba(8,8,8,0.72); }
  .video-frame { width: 100%; aspect-ratio: 16 / 9; border: 0; display: block; }
  .video-slot figcaption { margin-top: 0.7rem; font-size: 0.95rem; }
  .video-desc { color: var(--text-dim); font-size: 0.88rem; margin-top: 0.25rem; }
  .post-body h2, .cta-title, .post-list h2 { font-family: 'Cormorant Garamond', serif; font-weight: 500; line-height: 1.2; }
  .post-body h2 { font-size: clamp(1.7rem, 3vw, 2.25rem); margin: 2.3rem 0 0.9rem; }
  .post-body h3 { font-size: 1rem; font-weight: 500; margin: 1.6rem 0 0.5rem; }
  .post-body p, .post-body li { color: var(--text-mid); }
  .post-body p { margin: 0 0 1rem; }
  .post-body a, .related a, .post-list a { color: var(--gold); text-underline-offset: 0.18em; }
  .post-body ul, .post-body ol, .related ul { list-style: none; margin: 0 0 1.2rem; }
  .post-body li, .related li { position: relative; padding: 0.35rem 0 0.35rem 1.2rem; }
  .post-body li::before, .related li::before { content: '—'; position: absolute; left: 0; color: var(--gold); }
  .post-body blockquote { border-left: 1px solid var(--gold); margin: 1.4rem 0; padding-left: 1.2rem; }
  .post-body blockquote p { font-family: 'Cormorant Garamond', serif; font-style: italic; font-size: 1.35rem; line-height: 1.45; color: var(--white); }
  .post-cta { border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); padding: 2rem 0; margin: 2.2rem 0; }
  .cta-title { font-size: clamp(1.8rem, 3vw, 2.4rem); margin-bottom: 0.8rem; }
  .post-cta p { color: var(--text-mid); max-width: 58ch; margin-bottom: 1.3rem; }
  .cta-actions { display: flex; flex-wrap: wrap; gap: 0.8rem; align-items: center; }
  .btn-primary, .btn-outline { display: inline-block; font-weight: 500; font-size: 0.75rem; letter-spacing: 0.16em; text-transform: uppercase; text-decoration: none; padding: 1rem 1.6rem; }
  .btn-primary { background: var(--gold); color: var(--black); }
  .btn-primary:hover { opacity: 0.85; }
  .btn-outline { background: transparent; color: var(--gold); border: 1px solid var(--gold-dim); }
  .btn-outline:hover { background: var(--gold); color: var(--black); }
  .post-faq { margin-top: 2.5rem; }
  .post-faq h2 { font-family: 'Cormorant Garamond', serif; font-weight: 500; font-size: clamp(1.7rem, 3vw, 2.25rem); margin-bottom: 0.4rem; }
  .faq-item { border-top: 1px solid var(--rule); padding: 1.15rem 0; }
  .faq-item:last-child { border-bottom: 1px solid var(--rule); }
  .faq-item h3 { font-family: 'Cormorant Garamond', serif; font-weight: 500; font-size: 1.35rem; line-height: 1.3; margin-bottom: 0.45rem; }
  .faq-item p { color: var(--text-mid); font-size: 0.95rem; }
  .related { margin-top: 2.4rem; }
  .post-list { list-style: none; border-top: 1px solid var(--rule); margin-top: 2.5rem; }
  .post-list li { padding: 1.7rem 0; border-bottom: 1px solid var(--rule); }
  .post-list h2 { font-size: clamp(1.7rem, 3vw, 2.3rem); margin: 0.35rem 0 0.45rem; }
  .post-list h2 a { color: var(--white); text-decoration: none; }
  .post-list h2 a:hover { color: var(--gold); }
  .post-list p { color: var(--text-mid); }
  .empty { margin-top: 2rem; color: var(--text-dim); }
  footer { border-top: 1px solid var(--rule); padding: 2.2rem 4rem; display: flex; justify-content: space-between; align-items: center; gap: 1.2rem; flex-wrap: wrap; font-size: 0.68rem; font-weight: 300; color: var(--text-dim); letter-spacing: 0.08em; }
  footer .nav-logo { color: var(--text-dim); letter-spacing: 0.28em; }
  .footer-links { display: flex; gap: 1.2rem; flex-wrap: wrap; }
  .footer-links a { color: var(--text-dim); text-decoration: none; letter-spacing: 0.14em; text-transform: uppercase; }
  .footer-links a:hover { color: var(--gold); }
  @media (max-width: 900px) {
    .site-nav { padding: 1rem 1.25rem; flex-wrap: wrap; }
    .page { padding: 12rem 1.25rem 3.5rem; }
    footer { padding: 1.6rem 1.25rem 2rem; }
  }
  @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
"""

POST_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>@@TITLE@@ | AIReady Executive</title>
<meta name="description" content="@@DESCRIPTION@@">
<meta name="robots" content="index, follow">
<link rel="canonical" href="@@CANONICAL@@">
<meta name="theme-color" content="#080808">
<meta name="author" content="AIReady Executive">
<meta property="og:type" content="article">
<meta property="og:site_name" content="AIReady Executive">
<meta property="og:title" content="@@TITLE@@">
<meta property="og:description" content="@@DESCRIPTION@@">
<meta property="og:url" content="@@CANONICAL@@">
<meta property="og:image" content="https://theaireadyexecutive.com/assets/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Boardroom photograph used on the AIReady Executive homepage.">
<meta property="article:published_time" content="@@DATE_ISO@@">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="@@TITLE@@">
<meta name="twitter:description" content="@@DESCRIPTION@@">
<meta name="twitter:image" content="https://theaireadyexecutive.com/assets/og.jpg">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600&family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap" rel="stylesheet">
@@JSONLD@@
<style>
@@CSS@@
</style>
</head>
<body>
@@NAV@@
<article class="page">
@@CRUMBS@@
<p class="section-eyebrow">@@TOPIC@@</p>
<h1>@@TITLE@@</h1>
<p class="deck">@@DECK@@</p>
<p class="post-meta"><time datetime="@@DATE_ISO@@">@@DATE_DISPLAY@@</time> <span aria-hidden="true">·</span> <a href="/about/">Colin Dowling</a>@@UPDATED_NOTE@@</p>
<aside class="takeaways">
  <p class="section-eyebrow">Key takeaways</p>
  <ul>
@@TAKEAWAYS@@
  </ul>
</aside>
@@VIDEO@@
<div class="post-body">
@@BODY@@
</div>
@@END_CTA@@
<section class="post-faq" aria-labelledby="faq-heading">
  <h2 id="faq-heading">Questions</h2>
@@FAQS@@
</section>
@@RELATED@@
</article>
@@FOOTER@@
@@VIDEO_SCRIPT@@
</body>
</html>
""".replace("@@CSS@@", PAGE_CSS)

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>@@TITLE@@ | AIReady Executive</title>
<meta name="description" content="@@DESCRIPTION@@">
<meta name="robots" content="index, follow">
<link rel="canonical" href="@@CANONICAL@@">
<meta name="theme-color" content="#080808">
<meta name="author" content="AIReady Executive">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AIReady Executive">
<meta property="og:title" content="@@TITLE@@ | AIReady Executive">
<meta property="og:description" content="@@DESCRIPTION@@">
<meta property="og:url" content="@@CANONICAL@@">
<meta property="og:image" content="https://theaireadyexecutive.com/assets/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Boardroom photograph used on the AIReady Executive homepage.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="@@TITLE@@ | AIReady Executive">
<meta name="twitter:description" content="@@DESCRIPTION@@">
<meta name="twitter:image" content="https://theaireadyexecutive.com/assets/og.jpg">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600&family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap" rel="stylesheet">
@@JSONLD@@
<style>
@@CSS@@
</style>
</head>
<body>
@@NAV@@
<main class="page">
@@CRUMBS@@
<p class="section-eyebrow">Blog</p>
<h1>@@H1@@</h1>
<p class="lede">@@LEDE@@</p>
@@LISTING@@
</main>
@@FOOTER@@
</body>
</html>
""".replace("@@CSS@@", PAGE_CSS)


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        blog = root / "content" / "blog"
        blog.mkdir(parents=True)
        (root / "advisory").mkdir()
        (root / "advisory" / "index.html").write_text(
            "<html><body><!-- blog-spokes:start -->\nplaceholder\n<!-- blog-spokes:end --></body></html>\n",
            encoding="utf-8",
        )
        (blog / "_template.md").write_text(
            "---\ntitle: \"Skip me\"\ndescription: \"no\"\nslug: skip-me\ndate: 2026-01-01\ntopic: engagement\nfaqs:\n  - q: \"Q one\"\n    a: \"A one\"\n  - q: \"Q two\"\n    a: \"A two\"\n  - q: \"Q three\"\n    a: \"A three\"\ntakeaways:\n  - \"One\"\n---\n## A\n\nText.\n\n## B\n\nText.\n",
            encoding="utf-8",
        )
        (blog / "draft-note.md").write_text(
            "---\npublished: false\ntitle: \"Hidden\"\ndescription: \"no\"\nslug: draft-note\ndate: 2026-01-02\ntopic: engagement\nfaqs:\n  - q: \"Q one\"\n    a: \"A one\"\n  - q: \"Q two\"\n    a: \"A two\"\n  - q: \"Q three\"\n    a: \"A three\"\ntakeaways:\n  - \"One\"\n---\n## A\n\nText.\n\n## B\n\nText.\n",
            encoding="utf-8",
        )
        good = """---
title: "A real note"
description: "Description of the note."
slug: a-real-note
date: 2026-10-31
topic: engagement
faqs:
  - q: "First question?"
    a: "First answer."
  - q: "Second question?"
    a: >
      Second answer that
      wraps.
  - q: "Third question?"
    a: "Third answer with <script>alert(1)</script>."
  - q: "Fourth question?"
    a: "Fourth answer."
takeaways:
  - "Takeaway one"
  - "Takeaway two"
video:
  youtube_id: abcdefghijk
  name: "A titled video"
  description: "What the video shows."
  upload_date: 2026-10-01
  duration: PT4M12S
---
See the [advisory page](/advisory/) and a **bold** word.

## Section one

Opening paragraph.

## Section two

Middle paragraph.

## Section three

Closing paragraph.
"""
        (blog / "a-real-note.md").write_text(good, encoding="utf-8")
        posts = build(root)
        assert [post.slug for post in posts] == ["a-real-note"]
        page = (root / "blog" / "a-real-note" / "index.html").read_text(encoding="utf-8")
        assert "skip-me" not in page
        assert "Hidden" not in (root / "blog" / "index.html").read_text(encoding="utf-8")
        assert "<script>alert" not in page
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
        assert page.find("<h2>Section two</h2>") < page.find("utm_content=inbody") < page.find("<h2>Section three</h2>")
        assert "utm_source=blog&amp;utm_medium=internal&amp;utm_campaign=blog_a-real-note&amp;utm_content=inbody" in page
        assert "utm_source=blog&amp;utm_medium=internal&amp;utm_campaign=blog_a-real-note&amp;utm_content=post_end" in page
        assert 'href="/15minutesairoadmap/?utm_source=blog' in page
        assert 'href="/contact/?utm_source=blog' in page
        assert "Book an Assessment" in page
        assert "Key takeaways" in page
        assert "youtube-nocookie.com/embed/abcdefghijk?autoplay=1" in page
        data = json.loads(re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', page, re.S).group(1))
        types = [node["@type"] for node in data["@graph"]]
        assert types == ["Organization", "Person", "BlogPosting", "FAQPage", "BreadcrumbList", "VideoObject"]
        posting = next(node for node in data["@graph"] if node["@type"] == "BlogPosting")
        assert posting["author"]["@id"] == PERSON_ID
        assert 'href="/about/"' in page
        assert "Colin Dowling" in page
        video = data["@graph"][-1]
        assert video["embedUrl"] == "https://www.youtube-nocookie.com/embed/abcdefghijk"
        assert video["thumbnailUrl"] == "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"
        assert video["duration"] == "PT4M12S"
        faq = next(node for node in data["@graph"] if node["@type"] == "FAQPage")
        assert len(faq["mainEntity"]) == 4
        assert "Second answer that wraps." in faq["mainEntity"][1]["acceptedAnswer"]["text"]
        index_raw = (root / "blog" / "index.html").read_text(encoding="utf-8")
        index_data = json.loads(re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', index_raw, re.S).group(1))
        index_types = []
        for node in index_data["@graph"]:
            kind = node["@type"]
            index_types.extend(kind if isinstance(kind, list) else [kind])
        assert {"Blog", "CollectionPage", "ItemList", "BreadcrumbList", "Person"} <= set(index_types)
        sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
        assert f"{SITE}/blog/a-real-note/" in sitemap
        assert f"{SITE}/advisory/" in sitemap
        assert f"{SITE}/about/" in sitemap
        assert "skip-me" not in sitemap
        services = (root / "advisory" / "index.html").read_text(encoding="utf-8")
        assert 'href="/blog/a-real-note/"' in services
        assert "placeholder" not in services
        first = (root / "blog" / "index.html").read_text(encoding="utf-8")
        build(root)
        assert (root / "blog" / "index.html").read_text(encoding="utf-8") == first

        def fails(name: str, text: str) -> None:
            target = blog / name
            target.write_text(text, encoding="utf-8")
            try:
                load_posts(root)
            except BuildError:
                target.unlink()
                return
            target.unlink()
            raise AssertionError(f"expected failure for {name}")

        fails(
            "short-faq.md",
            good.replace(
                '  - q: "Third question?"\n    a: "Third answer with <script>alert(1)</script>."\n  - q: "Fourth question?"\n    a: "Fourth answer."\n',
                "",
            ).replace("slug: a-real-note", "slug: short-faq"),
        )
        one_section = good.replace("## Section two\n\nMiddle paragraph.\n\n## Section three\n\nClosing paragraph.\n", "")
        one_section = one_section.replace("slug: a-real-note", "slug: one-section")
        (blog / "one-section.md").write_text(one_section, encoding="utf-8")
        try:
            build(root)
            raise AssertionError("one section should fail")
        except BuildError:
            pass
        (blog / "one-section.md").unlink()
    print("self-test ok")


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        self_test()
        return 0
    try:
        posts = build(ROOT)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"built {len(posts)} post{'s' if len(posts) != 1 else ''}: {', '.join(post.slug for post in posts) or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
