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


def load_index():
    if not INDEX_PATH.exists():
        print("No existing index found. Run export.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def fetch_all_current_page_ids(session):
    url = f"{BASE_URL}/api/v2/pages"
    params = {"limit": 250, "spaceKey": SPACE_KEY}
    ids = set()
    for page in paginate(session, url, params):
        ids.add(page["id"])
    return ids


def fetch_modified_pages(session, since_iso):
    url = f"{BASE_URL}/api/v2/pages"
    params = {
        "limit": 250,
        "body-format": "storage",
        "sort": "-modified-date",
        "spaceKey": SPACE_KEY,
    }
    modified = []
    for page in paginate(session, url, params):
        page_modified = page.get("version", {}).get("createdAt", "")
        if page_modified and page_modified > since_iso:
            modified.append(page)
        else:
            break
    return modified


def fetch_space(session, space_id):
    url = f"{BASE_URL}/api/v2/spaces/{space_id}"
    resp = session.get(url)
    resp.raise_for_status()
    return resp.json()


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


def update():
    session = get_session()
    index = load_index()
    last_export = index["exported_at"]

    print(f"Last export: {last_export}")
    print(f"Space: {SPACE_KEY}")
    print("Checking for modified pages...")

    modified_pages = fetch_modified_pages(session, last_export)
    print(f"Found {len(modified_pages)} modified pages")

    existing_by_id = {p["id"]: p for p in index["pages"]}
    updated_count = 0

    for page in modified_pages:
        page_id = page["id"]
        title = page["title"]
        space_id = page.get("spaceId")

        space = fetch_space(session, space_id)
        space_key = space["key"]
        space_name = space["name"]

        labels = fetch_page_labels(session, page_id)
        parent_title = fetch_page_ancestors(session, page_id)

        body_html = page.get("body", {}).get("storage", {}).get("value", "")
        last_modified = page.get("version", {}).get("createdAt", "")
        content_md = md(body_html, heading_style="ATX",
                        strip=["script", "style"])
        filename = f"{slugify(title, max_length=80)}.md"
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

        if page_id in existing_by_id:
            old_path = PAGES_DIR / existing_by_id[page_id]["path"]
            new_path = PAGES_DIR / space_key / filename
            if old_path != new_path and old_path.exists():
                old_path.unlink()

        space_dir = PAGES_DIR / space_key
        space_dir.mkdir(parents=True, exist_ok=True)

        file_path = space_dir / filename
        file_path.write_text(
            frontmatter + f"# {title}\n\n" + content_md,
            encoding="utf-8",
        )

        existing_by_id[page_id] = {
            "id": page_id,
            "title": title,
            "space_key": space_key,
            "space_name": space_name,
            "parent_title": parent_title,
            "path": f"{space_key}/{filename}",
            "labels": labels,
            "last_modified": last_modified,
        }
        updated_count += 1
        print(f"  Updated: {title}")

    print("Checking for deleted pages...")
    current_ids = fetch_all_current_page_ids(session)
    deleted_count = 0
    for page_id in list(existing_by_id.keys()):
        if page_id not in current_ids:
            old_path = PAGES_DIR / existing_by_id[page_id]["path"]
            if old_path.exists():
                old_path.unlink()
            del existing_by_id[page_id]
            deleted_count += 1

    if deleted_count:
        print(f"  Removed {deleted_count} deleted pages")

    new_index = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_pages": len(existing_by_id),
        "pages": list(existing_by_id.values()),
    }
    INDEX_PATH.write_text(json.dumps(new_index, indent=2,
                          ensure_ascii=False), encoding="utf-8")

    print(
        f"\nUpdate complete: {updated_count} updated, {deleted_count} deleted")


if __name__ == "__main__":
    try:
        update()
    except KeyError as e:
        print(f"Missing environment variable: {e}", file=sys.stderr)
        print("Copy .env.example to .env and fill in your credentials.",
              file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
