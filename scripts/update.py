import json
import shutil
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
from tree import build_tree, compute_all_paths


def load_index(index_path):
    if not index_path.exists():
        print("No existing index found. Run export.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(index_path.read_text(encoding="utf-8"))


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


def build_frontmatter(title, page_id, space_key, space_name,
                      parent_id, parent_title, url, last_modified, labels):
    """Build a consistent YAML frontmatter string."""
    return (
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


def cleanup_empty_dirs(root_dir):
    """Remove empty directories bottom-up under *root_dir*."""
    for dirpath in sorted(root_dir.rglob("*"), reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            dirpath.rmdir()


def update():
    session = get_session()

    space_dir = PAGES_DIR / SPACE_KEY
    index_path = space_dir / "_index.json"

    index = load_index(index_path)
    last_export = index["exported_at"]
    space_key = index.get("space_key", SPACE_KEY)
    space_name = index.get("space_name", SPACE_KEY)

    print(f"Last export: {last_export}")
    print(f"Space: {space_key} ({space_name})")
    print("Checking for modified pages...")

    # ------------------------------------------------------------------
    # 1. Load existing index into pages_by_id
    # ------------------------------------------------------------------
    pages_by_id = {}
    for entry in index["pages"]:
        pages_by_id[entry["id"]] = {
            "id": entry["id"],
            "title": entry["title"],
            "parent_id": entry.get("parent_id", ""),
            "labels": entry.get("labels", []),
            "last_modified": entry.get("last_modified", ""),
        }

    old_paths = {entry["id"]: entry["path"] for entry in index["pages"]}

    # ------------------------------------------------------------------
    # 2. Fetch and process modified pages
    # ------------------------------------------------------------------
    modified_pages = fetch_modified_pages(session, last_export)
    print(f"Found {len(modified_pages)} modified pages")

    modified_content = {}   # page_id → markdown body text
    modified_ids = set()
    updated_count = 0

    for page in modified_pages:
        page_id = page["id"]
        title = page["title"]
        space_id = page.get("spaceId")

        space_info = fetch_space(session, space_id)
        space_key = space_info["key"]
        space_name = space_info["name"]

        labels = fetch_page_labels(session, page_id)

        parent_id = page.get("parentId") or ""

        body_html = page.get("body", {}).get("storage", {}).get("value", "")
        last_modified = page.get("version", {}).get("createdAt", "")
        content_md = md(body_html, heading_style="ATX",
                        strip=["script", "style"])

        # Update the in-memory entry
        pages_by_id[page_id] = {
            "id": page_id,
            "title": title,
            "parent_id": parent_id,
            "labels": labels,
            "last_modified": last_modified,
        }

        modified_content[page_id] = content_md
        modified_ids.add(page_id)
        updated_count += 1
        print(f"  Updated: {title}")

    # ------------------------------------------------------------------
    # 3. Detect and remove deleted pages
    # ------------------------------------------------------------------
    print("Checking for deleted pages...")
    current_ids = fetch_all_current_page_ids(session)
    deleted_count = 0
    for page_id in list(pages_by_id.keys()):
        if page_id not in current_ids:
            old = old_paths.get(page_id)
            if old:
                old_file = space_dir / old
                if old_file.exists():
                    old_file.unlink()
            del pages_by_id[page_id]
            old_paths.pop(page_id, None)
            deleted_count += 1

    if deleted_count:
        print(f"  Removed {deleted_count} deleted pages")

    # ------------------------------------------------------------------
    # 4. Rebuild tree and compute all new paths
    # ------------------------------------------------------------------
    children, roots = build_tree(pages_by_id)
    new_paths = compute_all_paths(pages_by_id, children)

    # ------------------------------------------------------------------
    # 5. Handle path changes and write files
    # ------------------------------------------------------------------
    moved_count = 0
    for pid, info in pages_by_id.items():
        new_path = new_paths[pid]
        old_path = old_paths.get(pid)

        new_file = space_dir / new_path
        old_file = space_dir / old_path if old_path else None

        # Resolve parent_title
        parent_id = info["parent_id"]
        if parent_id and parent_id in pages_by_id:
            parent_title = pages_by_id[parent_id]["title"]
        else:
            parent_title = ""

        if pid in modified_ids:
            # Modified page — write new content to (possibly new) path
            new_file.parent.mkdir(parents=True, exist_ok=True)
            url = f"{BASE_URL}/spaces/{space_key}/pages/{pid}"
            fm = build_frontmatter(
                info["title"], pid, space_key, space_name,
                parent_id, parent_title, url, info["last_modified"],
                info["labels"],
            )
            new_file.write_text(
                fm + f"# {info['title']}\n\n" + modified_content[pid],
                encoding="utf-8",
            )
            # Clean up old location if it moved
            if old_file and old_file != new_file and old_file.exists():
                old_file.unlink()
                moved_count += 1

        elif old_path and new_path != old_path:
            # Unmodified page whose path changed (parent renamed, leaf↔parent
            # flip, etc.) — move the file.
            if old_file and old_file.exists():
                new_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_file), str(new_file))
                moved_count += 1

    if moved_count:
        print(f"  Moved {moved_count} pages to new paths")

    # Clean up empty directories left behind by moves/deletes.
    if space_dir.exists():
        cleanup_empty_dirs(space_dir)

    # ------------------------------------------------------------------
    # 6. Write updated index
    # ------------------------------------------------------------------
    all_metadata = []
    for pid, info in pages_by_id.items():
        parent_id = info["parent_id"]
        if parent_id and parent_id in pages_by_id:
            parent_title = pages_by_id[parent_id]["title"]
        else:
            parent_title = ""

        all_metadata.append({
            "id": pid,
            "title": info["title"],
            "parent_id": parent_id,
            "parent_title": parent_title,
            "path": new_paths[pid],
            "children": children.get(pid, []),
            "labels": info.get("labels", []),
            "last_modified": info.get("last_modified", ""),
        })

    new_index = {
        "space_key": space_key,
        "space_name": space_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_pages": len(all_metadata),
        "pages": all_metadata,
    }
    index_path.write_text(json.dumps(new_index, indent=2,
                          ensure_ascii=False), encoding="utf-8")

    print(
        f"\nUpdate complete: {updated_count} updated, "
        f"{deleted_count} deleted, {moved_count} moved")


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
