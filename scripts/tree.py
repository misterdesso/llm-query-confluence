"""Shared tree-building and path-computation utilities.

Functions here operate on a ``pages_by_id`` dict whose values are page
metadata dicts with at least ``id``, ``title``, and ``parent_id`` keys.
"""

from collections import defaultdict

from slugify import slugify


# ---------------------------------------------------------------------------
# Tree construction
# ---------------------------------------------------------------------------

def build_tree(pages_by_id):
    """Build parent→children mapping and identify root pages.

    A page is considered a *root* if its ``parent_id`` is falsy **or**
    points to a page that is not present in *pages_by_id* (i.e. the
    parent lives outside the exported set).

    Returns:
        children: ``defaultdict(list)`` mapping page_id → [child_id, …]
        roots:    list of page_ids that have no (known) parent
    """
    children = defaultdict(list)
    roots = []

    for page_id, page in pages_by_id.items():
        parent_id = page.get("parent_id")
        if parent_id and parent_id in pages_by_id:
            children[parent_id].append(page_id)
        else:
            roots.append(page_id)

    return children, roots


# ---------------------------------------------------------------------------
# Path computation
# ---------------------------------------------------------------------------

def _ancestor_chain(page_id, pages_by_id):
    """Return IDs from the root ancestor down to *page_id* (inclusive)."""
    chain = []
    current = page_id
    visited = set()
    while current and current in pages_by_id:
        if current in visited:
            break  # guard against cycles
        visited.add(current)
        chain.append(current)
        current = pages_by_id[current].get("parent_id")
    chain.reverse()
    return chain


def compute_page_path(page_id, pages_by_id, children):
    """Compute the nested file path for a single page.

    * Pages **with** children → ``<ancestor…>/<slug>/_index.md``
    * Leaf pages              → ``<ancestor…>/<slug>.md``

    The returned path is relative to the space directory
    (i.e. ``pages/<SPACE_KEY>/``).
    """
    chain = _ancestor_chain(page_id, pages_by_id)
    has_children = bool(children.get(page_id))

    if has_children:
        # Parent page: lives as _index.md inside its own folder
        segments = [slugify(pages_by_id[pid]["title"], max_length=80)
                    for pid in chain]
        return f"{'/'.join(segments)}/_index.md"
    else:
        if len(chain) > 1:
            # Leaf under one or more ancestors
            parent_segments = [
                slugify(pages_by_id[pid]["title"], max_length=80)
                for pid in chain[:-1]
            ]
            filename = slugify(
                pages_by_id[page_id]["title"], max_length=80) + ".md"
            return f"{'/'.join(parent_segments)}/{filename}"
        else:
            # Root-level leaf (no parent, no children)
            filename = slugify(
                pages_by_id[page_id]["title"], max_length=80) + ".md"
            return filename


def compute_all_paths(pages_by_id, children):
    """Return ``{page_id: relative_path}`` for every page."""
    return {
        pid: compute_page_path(pid, pages_by_id, children)
        for pid in pages_by_id
    }

