# Confluence Export Tool

Export and incrementally update Confluence pages as markdown for LLM querying.

## Setup

0. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with:
   - `CONFLUENCE_DOMAIN` — your Atlassian subdomain (e.g., `yourcompany` for yourcompany.atlassian.net)
   - `CONFLUENCE_EMAIL` — Atlassian account email
   - `CONFLUENCE_API_TOKEN` — generated at https://id.atlassian.net/manage-profile/security/api-tokens
   - `CONFLUENCE_SPACE_KEY` — the space key to export (visible in the space URL or space settings)

## Usage

### Full export (first time)

```bash
python scripts/export.py
```

Exports all pages from the configured space into `pages/`. May take a few minutes depending on page count.

### Incremental update

```bash
python scripts/update.py
```

Only fetches pages modified since the last export. Also removes pages that have since been deleted on Confluence.

## Querying with an LLM

Launch Claude Code (or any LLM tool) at this directory. The `CLAUDE.md` file provides instructions for navigating the exported pages. The LLM can:

- Read `pages/_index.json` to find pages by title, path, or label
- Read individual markdown files for full page content
- Search across files for specific keywords

## Structure

```
pages/
├── _index.json              # Master index of all pages
└── <SPACE_KEY>/             # Your exported space
    ├── some-page-title.md
    ├── another-page.md
    └── ...
```
