# Internal linking plan

AIReady Executive is a short hub-and-spoke set. Hubs are pages that already describe an offer. Spokes are blog posts. Anchor text should use words the destination already uses.

Problem pages (`/ai-readiness-assessment/`, `/ai-strategy-for-ceos/`) are not on the site yet. Until they exist, a post's hub is the offer or the session page below, not a new URL. Topic hubs at `/topics/` wait until a topic has three or more posts.

## Hubs

| Hub | URL | What it is |
| --- | --- | --- |
| Home | `/` | The engagement narrative, the 30-day sequence, and the three fees |
| Advisory | `/advisory/` | The offer: the same fees, the free session, the homepage FAQ, and a calendar |
| 15-minute roadmap | `/15minutesairoadmap/` | Default destination for blog calls to action |
| About | `/about/` | Author page. Every post byline points here |
| Blog | `/blog/` | Index of spokes |
| Contact | `/contact/` | The readiness-conversation form and the same calendar |

The roadmap page stays without the brochure nav. It is a single-action page. The other brochure pages link to it.

## Every post

1. Front matter `topic` selects one hub (see `content/blog/README.md`). The generated page links to that hub. Set `hub` when the table is wrong for the piece.
2. The mid-article and end calls to action each link to `/15minutesairoadmap/` (unless `cta` says otherwise) and to Book an Assessment at `/contact/`. Parameters: `utm_source=blog`, `utm_medium=internal`, `utm_campaign=blog_<slug>`, `utm_content=inbody` or `post_end`. Posts with `hide_cta: true` skip both blocks. Do not invent fees or offers to replace them.
3. The related list also links the call-to-action page when it is not the hub, plus up to two other posts with the same topic. A `hide_cta` post does not link the call-to-action page from that list. Point `hub` at another post or `/blog/` when the offer page would be a hard sell.
4. Breadcrumbs are Home / Blog / the post. The byline is Colin Dowling and links to `/about/`.
5. Posts whose hub is `/advisory/` are listed on the advisory page. The roadmap page does not list spokes.
6. Do not link a Modern Business Life episode until that episode exists for the post. The show itself is linked from `/about/`. One cross-site link is the ceiling, and only when the topic is actually on the other site.

## Brochure nav and footer

Home, advisory, blog, about, and contact use the same links: Advisory, Blog, 15-Min Roadmap, About, and Apply Now. The footer repeats Advisory, Blog, 15-Min Roadmap, About, and Contact.

## Topic coverage to aim for

| Cluster | Hub until a problem page exists | Spoke job |
| --- | --- | --- |
| The engagement | `/advisory/` | The 30 days, the five deliverables, and the three fees |
| Who it is for | `/advisory/` | The four seats named on the homepage, and the Chief AI Officer question |
| The free session | `/15minutesairoadmap/` | What the 15-minute session hands over |
| Readiness | `/advisory/#framework` | The six published parts of the framework |

A new spoke links up to its hub and across to two posts in the same cluster once those posts exist. The advisory page lists spokes whose hub is `/advisory/`.

## Cross-site

Do not add a link to another property unless the post is about something that page actually covers. Nothing in the current posts does, other than the author page linking the Modern Business Life show.

## Video

When a post sets `video`, the page embeds it and the YouTube description should link back to the post. No post has a video yet. Do not invent one.
