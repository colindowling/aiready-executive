# Add a blog post

Posts are Markdown files in this folder. The site is static HTML. DigitalOcean App Platform serves the files in this repo; nothing runs a build on deploy. `scripts/build_blog.py` writes the HTML, rebuilds the blog index, refreshes `sitemap.xml`, and refreshes the note list on `/advisory/`. Commit the Markdown and the generated files together.

## Steps

1. Copy `_template.md` to `<slug>.md`. The filename is the slug.
2. Replace the front matter and write the body. Do not invent fees, results, or claims that are not already on the site.
3. From the repository root, run:

   ```bash
   python3 scripts/build_blog.py
   python3 scripts/check_site.py
   ```

4. Open `/blog/` and `/blog/<slug>/`.
5. Commit the Markdown, `blog/`, and `sitemap.xml`.

Files whose names start with `_`, `README.md`, and posts with `published: false` are skipped.

## Front matter

```yaml
---
title: "Post title"
description: "Meta description, ideally under 160 characters."
slug: post-title
date: 2026-10-31
updated: 2026-10-31          # optional; defaults to date
topic: engagement            # engagement, readiness, roadmap, board, or fees
topic_label: Engagement      # optional display label
hub: /advisory/               # optional; otherwise chosen from the topic
cta: /15minutesairoadmap/    # optional; this is the default
hide_cta: false              # optional; true skips the mid-article and end CTA blocks
published: true
takeaways:
  - "One sentence already supported by the site."
  - "Another."
faqs:
  - q: "A question a reader would actually ask?"
    a: "The answer, in one paragraph."
  - q: "Second?"
    a: "Second answer."
  - q: "Third?"
    a: "Third answer."
# video:                     # omit until a real upload exists
#   youtube_id: abcdefghijk
#   name: "Video title"
#   description: "What the video actually shows."
#   upload_date: 2026-10-31
#   thumbnail_url: "https://..."   # optional; defaults to the YouTube thumbnail
#   duration: PT5M30S              # optional ISO 8601 duration
---
```

`faqs` must contain 3 to 5 questions. There is no blank-line support inside the front matter; keep each value on its line, or use a `>` folded value under `a:`.

Topics without an explicit `hub`:

| topic | hub |
| --- | --- |
| engagement | `/advisory/` |
| readiness | `/advisory/#framework` |
| roadmap | `/15minutesairoadmap/` |
| board | `/advisory/` |
| fees | `/advisory/#fees` |

## Body

Supported Markdown: paragraphs, `##` and `###` headings, `-` lists, `1.` lists, `> blockquotes`, `**bold**`, `*italic*`, and `[links](/advisory/)`. Internal links need a trailing slash. The title in the front matter is the only `h1`. Write at least two `##` sections.

The generator inserts the mid-article call to action after the second `##` section, and an end call to action after the body. Each block links to `/15minutesairoadmap/` (or `cta`, if set) and to Book an Assessment at `/contact/`, with:

- `utm_source=blog`
- `utm_medium=internal`
- `utm_campaign=blog_<slug>`
- `utm_content=inbody` on the mid-article links
- `utm_content=post_end` on the closing links

Each post also links to its hub, to the call-to-action page when that is a different URL, and to up to two other posts with the same topic.

Set `hide_cta: true` to skip the mid-article and end blocks. Use it when a product call to action does not belong on the piece. The page still links to its hub and to other posts. Point `hub` at another post, or at `/blog/`, when the offer page would be a hard sell. The site nav and footer keep their usual links. Do not invent fees or offers in the body to replace the blocks.

## Video

Leave `video` out until the upload exists. When it is set, the page gets a click-to-play YouTube embed and `VideoObject` JSON-LD (`name`, `description`, `thumbnailUrl`, `uploadDate`, `embedUrl`, and `duration` when provided). Put the post URL in the video description on YouTube. That step is outside this repo.

## What the script updates

- `blog/index.html`
- `blog/<slug>/index.html`
- `sitemap.xml` (static pages plus every published post)
- the list between `<!-- blog-spokes:start -->` and `<!-- blog-spokes:end -->` on `advisory/index.html`, for posts whose hub is `/advisory/`

`llms.txt` is edited by hand when a post should be listed there. Bump the matching `lastmod` in `STATIC_PAGES` inside `scripts/build_blog.py` when a static page changes.

`python3 scripts/build_blog.py --self-test` checks the generator without touching the site.
