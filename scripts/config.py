import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT_DIR / "pages"

load_dotenv(ROOT_DIR / ".env")

CONFLUENCE_DOMAIN = os.environ["CONFLUENCE_DOMAIN"]
CONFLUENCE_EMAIL = os.environ["CONFLUENCE_EMAIL"]
CONFLUENCE_API_TOKEN = os.environ["CONFLUENCE_API_TOKEN"]
SPACE_KEY = os.environ["CONFLUENCE_SPACE_KEY"]

SITE_URL = f"https://{CONFLUENCE_DOMAIN}.atlassian.net"
BASE_URL = f"{SITE_URL}/wiki"


def get_session() -> requests.Session:
    session = requests.Session()
    session.auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)
    session.headers.update({"Accept": "application/json"})
    return session


def paginate(session: requests.Session, url: str, params: dict | None = None):
    params = params or {}
    while url:
        resp = session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("results", [])
        links = data.get("_links", {})
        next_path = links.get("next")
        if not next_path:
            break
        url = f"{SITE_URL}{next_path}"
        params = {}
