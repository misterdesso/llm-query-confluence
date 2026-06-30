import json
import sys
from datetime import datetime, timezone

from markdownify import markdownify as md

from config import (
    BASE_URL,
    PAGES_DIR,
    SPACE_KEY,
    get_session,
    paginate,
)
from spinner import Spinner
from tree import build_tree, compute_all_paths


def fetch_space(session):
    url = f"{BASE_URL}/api/v2/spaces"
    params = {"limit": 250, "keys": SPACE_KEY}
    spaces = list(paginate(session, url, params))
    if not spaces:
        print(f"Space {SPACE_KEY} not found", file=sys.stderr)
        sys.exit(1)
    return spaces[0]


def fetch_pages_for_space(session, space_id):
    url = f"{BASE_URL}/api/v2/spaces/{space_id}/pages"
    return list(paginate(session, url, {"limit": 250, "body-format": "storage"}))


def fetch_page_labels(session, page_id):
    url = f"{BASE_URL}/api/v2/pages/{page_id}/labels"
    resp = session.get(url)
    if resp.status_code == 200:
        return [label["name"] for label in resp.json().get("results", [])]
    return []


def convert_page(page, space_key, space_name, labels,
                 parent_id, parent_title):
    """Convert a Confluence page to markdown with frontmatter."""
    title = page["title"]
    page_id = page["id"]
    body_html = page.get("body", {}).get("storage", {}).get("value", "")
    last_modified = page.get("version", {}).get("createdAt", "")

    content_md = md(body_html, heading_style="ATX", strip=["script", "style"])

    url = f"{BASE_URL}/spaces/{space_key}/pages/{page_id}"

    frontmatter = (
        f"---\n"
        f'title: "{title}"\n'
        f'page_id: "{page_id}"\n'
        f'space_key: "{space_key}"\n'
        f'space_name: "{space_name}"\n'
        f'parent_id: "{parent_id}"\n'
        f'parent_title: "{parent_title}"\n'
        f'url: "{url}"\n'
        f'last_modified: "{last_modified}"\n'
        f"labels: {json.dumps(labels)}\n"
        f"---\n\n"
    )

    return {
        "frontmatter": frontmatter,
        "content": content_md,
        "last_modified": last_modified,
    }


def export_all():
    session = get_session()
    space = fetch_space(session)
    space_key = space["key"]
    space_name = space["name"]
    space_id = space["id"]

    print(f"Exporting space: {space_name} ({space_key})")

    space_dir = PAGES_DIR / space_key
    space_dir.mkdir(parents=True, exist_ok=True)
    index_path = space_dir / "_index.json"

    spinner = Spinner("Fetching pages...")
    spinner.start()
    try:
        pages = fetch_pages_for_space(session, space_id)
    finally:
        spinner.stop()
    print(f"  {len(pages)} pages fetched")

    # Build pages_by_id from the API response.
    # The Confluence v2 API uses camelCase `parentId`.
    pages_by_id = {}
    raw_pages_by_id = {}
    for page in pages:
        pid = page["id"]
        pages_by_id[pid] = {
            "id": pid,
            "title": page["title"],
            "parent_id": page.get("parentId") or "",
        }
        raw_pages_by_id[pid] = page

    # Build tree structure and compute nested paths.
    children, roots = build_tree(pages_by_id)
    paths = compute_all_paths(pages_by_id, children)

    all_metadata = []
    
    spinner = Spinner("Processing pages...")
    spinner.start()
    try:
        for page_id, page_info in pages_by_id.items():
            raw_page = raw_pages_by_id[page_id]
            labels = fetch_page_labels(session, page_id)

            # Resolve parent title from the tree.
            parent_id = page_info["parent_id"]
            if parent_id and parent_id in pages_by_id:
                parent_title = pages_by_id[parent_id]["title"]
            else:
                parent_title = ""

            rel_path = paths[page_id]

            result = convert_page(
                raw_page, space_key, space_name, labels,
                parent_id, parent_title,
            )

            # Create nested directory structure and write the file.
            file_path = space_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                result["frontmatter"]
                + f"# {page_info['title']}\n\n"
                + result["content"],
                encoding="utf-8",
            )

            child_ids = children.get(page_id, [])

            all_metadata.append({
                "id": page_id,
                "title": page_info["title"],
                "parent_id": parent_id,
                "parent_title": parent_title,
                "path": rel_path,
                "children": child_ids,
                "labels": labels,
                "last_modified": result["last_modified"],
            })
    finally:
        spinner.stop()

    index = {
        "space_key": space_key,
        "space_name": space_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_pages": len(all_metadata),
        "pages": all_metadata,
    }
    index_path.write_text(json.dumps(
        index, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nExport complete: {len(all_metadata)} pages")
    print(f"Index written to: {index_path}")


if __name__ == "__main__":
    try:
        export_all()
    except KeyError as e:
        print(f"Missing environment variable: {e}", file=sys.stderr)
        print("Fill your credentials in a .env file (refer to .env.example)",
              file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
