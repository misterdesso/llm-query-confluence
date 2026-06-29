# Confluence Knowledge Base

This directory contains exported Confluence pages converted to markdown for LLM querying. The target space is configured via the `CONFLUENCE_SPACE_KEY` environment variable.

## How to find information

1. **Start with the index** — read `pages/<SPACE_KEY>/_index.json` for the full list of pages with titles, labels, hierarchy, and file paths. Use this to quickly locate relevant pages without scanning every file.

2. **Browse the tree** — pages are organised in nested folders that mirror the Confluence page hierarchy. Parent pages are stored as `_index.md` inside their folder; leaf pages are regular `.md` files alongside them.

3. **Search by keyword** — use `grep` across `pages/<SPACE_KEY>/` for specific terms. All page content is plain markdown.

4. **Filter by label** — the index and each page's frontmatter include labels where available.

5. **Read the page** — once you identify a candidate, read the full markdown file at the path listed in the index (relative to the space folder).

## Directory layout

```
pages/
└── <SPACE_KEY>/
    ├── _index.json                      # Space index (all pages, hierarchy)
    ├── top-level-parent/
    │   ├── _index.md                    # Parent page content
    │   ├── child-leaf-page.md           # Leaf page
    │   └── child-parent-page/
    │       ├── _index.md                # Nested parent content
    │       └── grandchild-page.md
    └── standalone-leaf-page.md          # Root-level leaf page
```

- **`_index.json`** — the space index, one per space. Contains every page's metadata, hierarchy (`parent_id`, `children`), and file path.
- **`_index.md`** — a page that has children. Its content lives here; its children live as siblings in the same folder.
- **`<slug>.md`** — a leaf page (no children).

## Page format

Each `.md` file has YAML frontmatter:
- `title` — page title
- `page_id` — Confluence page ID
- `space_key` — the Confluence space key
- `space_name` — human-readable space name
- `parent_id` — the parent page's ID (empty for root pages)
- `parent_title` — the parent page's title (empty for root pages)
- `labels` — topic tags
- `last_modified` — when the page was last updated in Confluence
- `url` — direct link to the original Confluence page

## Index format (`_index.json`)

Top-level fields:
- `space_key` — the Confluence space key
- `space_name` — human-readable space name
- `exported_at` — ISO timestamp of the last export/update
- `total_pages` — number of pages in the index

Each entry in the `pages` array contains:
- `id` — page ID
- `title` — page title
- `parent_id` — ID of the parent page (empty string for roots)
- `parent_title` — title of the parent page
- `path` — file path relative to the space folder (e.g. `parent-slug/child-slug.md`)
- `children` — list of child page IDs (empty list for leaves)
- `labels` — topic tags
- `last_modified` — ISO timestamp

## Tips for querying

- When asked about a topic, check the index first to find candidate pages by title, then read those files.
- Use the folder hierarchy to explore related pages — children of a parent page often cover sub-topics in detail.
- If a page references another page by title, search the index for that title to find the linked content.
- Pages may be outdated — check `last_modified` dates and mention the caveat if a page is old.
- The `parent_id` and `children` fields let you navigate the page tree from the index without reading individual files.
- Always provide the Confluence URL from frontmatter so the user can open the original page if needed.
