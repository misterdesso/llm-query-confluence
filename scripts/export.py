import json
import sys
from datetime import datetime, timezone

from markdownify import markdownify as md
from slugify import slugify

from config import (
    BASE_URL,
    INDEX_PATH,
    PAGES_DIR,
    SPACE_KEY,
    get_session,
    paginate,
)


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


def fetch_page_ancestors(session, page_id):
    url = f"{BASE_URL}/api/v2/pages/{page_id}/ancestors"
    resp = session.get(url)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[-1].get("title", "")
    return ""


def convert_page(page, space_key, space_name, labels, parent_title):
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
        f'parent_title: "{parent_title}"\n'
        f'url: "{url}"\n'
        f'last_modified: "{last_modified}"\n'
        f"labels: {json.dumps(labels)}\n"
        f"---\n\n"
    )

    filename = f"{slugify(title, max_length=80)}.md"

    return {
        "frontmatter": frontmatter,
        "content": content_md,
        "filename": filename,
        "metadata": {
            "id": page_id,
            "title": title,
            "space_key": space_key,
            "space_name": space_name,
            "parent_title": parent_title,
            "path": f"{space_key}/{filename}",
            "labels": labels,
            "last_modified": last_modified,
        },
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

    pages = fetch_pages_for_space(session, space_id)
    print(f"  {len(pages)} pages")

    all_metadata = []

    for page in pages:
        labels = fetch_page_labels(session, page["id"])
        parent_title = fetch_page_ancestors(session, page["id"])

        result = convert_page(page, space_key, space_name,
                              labels, parent_title)

        file_path = space_dir / result["filename"]
        file_path.write_text(
            result["frontmatter"] +
            f"# {page['title']}\n\n" + result["content"],
            encoding="utf-8",
        )

        all_metadata.append(result["metadata"])

    index = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_pages": len(all_metadata),
        "pages": all_metadata,
    }
    INDEX_PATH.write_text(json.dumps(
        index, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nExport complete: {len(all_metadata)} pages")
    print(f"Index written to: {INDEX_PATH}")


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
