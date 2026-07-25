"""Poll deal-site RSS/Atom feeds and alert on entries matching NYC keywords."""

import hashlib
import xml.etree.ElementTree as ET

import requests

from . import alerts, db

_ATOM = "{http://www.w3.org/2005/Atom}"


def _parse_entries(xml_text):
    """Yield (title, link) from an RSS or Atom feed."""
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):  # RSS
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        yield title.strip(), link.strip()
    for entry in root.iter(f"{_ATOM}entry"):  # Atom
        title = entry.findtext(f"{_ATOM}title") or ""
        link_el = entry.find(f"{_ATOM}link")
        link = link_el.get("href", "") if link_el is not None else ""
        yield title.strip(), link.strip()


def run(conn, cfg):
    feed_cfg = cfg["feeds"]
    keywords = [k.lower() for k in feed_cfg["keywords"]]
    matched = 0
    for url in feed_cfg["urls"]:
        try:
            resp = requests.get(
                url, headers={"User-Agent": "farewatch/1.0 (personal deal monitor)"},
                timeout=30,
            )
            resp.raise_for_status()
            entries = list(_parse_entries(resp.text))
        except (requests.RequestException, ET.ParseError) as e:
            print(f"feed error {url}: {e}")
            continue
        for title, link in entries:
            if not any(k in title.lower() for k in keywords):
                continue
            fingerprint = "feed:" + hashlib.sha256(link.encode()).hexdigest()
            if db.already_alerted(conn, fingerprint):
                continue
            alerts.send("Fare deal spotted (feed)", f"{title}\n{link}")
            db.record_alert(conn, fingerprint, "feed", title)
            matched += 1
    print(f"feeds: done, {matched} new matching deal(s).")
