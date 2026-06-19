# Confluence Knowledge Base

This directory contains exported Confluence pages converted to markdown for LLM querying. The target space is configured via the `CONFLUENCE_SPACE_KEY` environment variable.

## How to find information

1. **Start with the index** — read `pages/_index.json` for the full list of pages with titles, labels, and file paths. Use this to quickly locate relevant pages without scanning every file.

2. **Search by keyword** — use `grep` across `pages/` for specific terms. All page content is plain markdown.

3. **Filter by label** — the index and each page's frontmatter include labels where available.

4. **Read the page** — once you identify a candidate, read the full markdown file at `pages/<space_key>/<slug>.md`.

## Page format

Each `.md` file has YAML frontmatter:
- `title` — page title
- `page_id` — Confluence page ID
- `space_key` — the Confluence space key
- `parent_title` — the parent page (helps understand hierarchy)
- `labels` — topic tags
- `last_modified` — when the page was last updated in Confluence
- `url` — direct link to the original Confluence page

## Tips for querying

- When asked about a topic, check the index first to find candidate pages by title, then read those files.
- If a page references another page by title, search the index for that title to find the linked content.
- Pages may be outdated — check `last_modified` dates and mention the caveat if a page is old.
- The `parent_title` field reveals page hierarchy — child pages often contain details for a parent topic.
- Always provide the Confluence URL from frontmatter so the user can open the original page if needed.
