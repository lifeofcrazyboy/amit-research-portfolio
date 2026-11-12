#!/usr/bin/env python3
"""Refresh a static academic portfolio from public ORCID works. Standard library only."""
import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import time
import unicodedata
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ORCID = "0000-0001-5732-4725"
API = f"https://pub.orcid.org/v3.0/{ORCID}"
LABELS = {"journal-article": "Journal article", "conference-paper": "Conference paper",
          "conference-abstract": "Conference abstract", "book-chapter": "Book chapter", "preprint": "Preprint"}


def request_json(url):
    headers = {"Accept": "application/json", "User-Agent": "AmitChandel-AcademicPortfolio/1.0"}
    token = os.environ.get("ORCID_PUBLIC_TOKEN", "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def normalize_doi(value):
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I).lower()


def title_key(value):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower())


def from_work(work):
    if work.get("visibility") != "public":
        raise ValueError("Unexpected non-public ORCID work")
    external = work.get("external-ids") or {}
    dois = [x.get("external-id-value", "") for x in external.get("external-id", [])
            if x.get("external-id-type") == "doi" and x.get("external-id-relationship") == "self"]
    date = work.get("publication-date") or {}
    year = (date.get("year") or {}).get("value", "")
    authors = [(x.get("credit-name") or {}).get("value", "")
               for x in (work.get("contributors") or {}).get("contributor", [])]
    return {"title": work["title"]["title"]["value"], "authors": ", ".join(filter(None, authors)),
            "journal": (work.get("journal-title") or {}).get("value", ""),
            "year": int(year) if str(year).isdigit() else None, "type": work.get("type", "other"),
            "doi": normalize_doi(dois[0]) if dois else "",
            "url": (work.get("url") or {}).get("value", ""), "source": "ORCID",
            "put_code": work.get("put-code")}


def merge_records(remote, manual):
    """Manual curation overrides metadata; DOI first, normalized title when no DOI."""
    result = []
    for record in remote + manual:
        record = dict(record)
        record["doi"] = normalize_doi(record.get("doi", ""))
        match = next((i for i, old in enumerate(result)
                      if (record["doi"] and record["doi"] == old.get("doi"))
                      or (title_key(record["title"]) == title_key(old["title"])
                          and (not record["doi"] or not old.get("doi")))), None)
        if match is None:
            result.append(record)
        else:
            old = result[match]
            result[match] = old | {k: v for k, v in record.items() if v not in (None, "")}
            if old.get("source", "").startswith("ORCID"):
                result[match]["source"] = "ORCID + CV"
    return sorted(result, key=lambda x: (-(x.get("year") or 0), x["title"].casefold()))


def safe_url(value):
    return value if value.startswith(("https://", "http://")) else ""


def render_record(record):
    e = html.escape
    kind = record.get("type", "other")
    doi = record.get("doi", "")
    url = "https://doi.org/" + doi if doi else safe_url(record.get("url", ""))
    title = e(record["title"])
    if url:
        title = f'<a href="{e(url, quote=True)}" target="_blank" rel="noopener noreferrer">{title}<span aria-hidden="true"> ↗</span></a>'
    authors = e(record.get("authors", ""))
    authors = re.sub(r"(Amit Singh Chandel|Chandel, A\.?\s?S\.?)", r"<strong>\1</strong>", authors)
    venue = e(record.get("journal") or "Research output")
    citation = f'{record.get("authors", "")} ({record.get("year") or "n.d."}). {record["title"]}. {record.get("journal", "")}. {url}'.strip()
    return f'''<article class="publication" data-type="{e(kind)}" data-year="{record.get('year') or ''}">
  <div class="pub-year">{record.get('year') or 'n.d.'}</div>
  <div class="pub-content"><span class="pub-type">{e(LABELS.get(kind, kind.replace('-', ' ').title()))}</span>
    <h3>{title}</h3><p class="pub-authors">{authors}</p><p class="pub-venue">{venue}</p>
    <div class="pub-actions">{f'<a href="{e(url, quote=True)}" target="_blank" rel="noopener noreferrer">Read publication ↗</a>' if url else ''}
    <button type="button" class="copy-citation" data-citation="{e(citation, quote=True)}">Copy citation</button></div>
  </div></article>'''


def replace_region(page, name, content):
    pattern = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.S)
    result, count = pattern.subn(lambda m: m[1] + "\n" + content + "\n" + m[2], page)
    if count != 1:
        raise ValueError(f"Expected exactly one {name} region, found {count}")
    return result


def render_page(records, checked):
    page = (ROOT / "index.html").read_text()
    page = replace_region(page, "PUBLICATIONS", "\n".join(map(render_record, records)))
    # Counts describe published journal articles only; proceedings and preprints are separate.
    count = sum(x.get("type") == "journal-article" for x in records)
    page = replace_region(page, "ARTICLE_COUNT", str(count))
    stamp = dt.datetime.fromisoformat(checked.replace("Z", "+00:00"))
    page = replace_region(page, "SYNC_STATUS", f'Public ORCID record checked <time datetime="{checked}">{stamp:%d %b %Y}</time>.')
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Render from the saved snapshot without network access")
    parser.add_argument("--fixture", type=Path, help="Read an ORCID works-summary JSON fixture")
    args = parser.parse_args()
    manual = json.loads((ROOT / "data/manual-publications.json").read_text())
    if args.offline:
        snapshot = json.loads((ROOT / "data/publications.json").read_text())
        records = merge_records(snapshot["publications"], manual)
        checked = snapshot["checked_at"]
    else:
        summary = json.loads(args.fixture.read_text()) if args.fixture else request_json(API + "/works")
        if not isinstance(summary.get("group"), list):
            raise ValueError("Invalid ORCID works response; preserving the previous snapshot")
        remote = []
        for group in summary["group"]:
            summaries = group.get("work-summary", [])
            if not summaries:
                raise ValueError("Empty ORCID work group; preserving the previous snapshot")
            # ORCID uses display-index to identify the researcher's preferred version.
            preferred = max(summaries, key=lambda item: int(item.get("display-index") or 0))
            remote.append(from_work(request_json(API + "/work/" + str(preferred["put-code"]))))
        if not remote:
            raise ValueError("No public works returned; preserving the previous snapshot. Check ORCID visibility.")
        records = merge_records(remote, manual)
        checked = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    page = render_page(records, checked)
    snapshot = {"orcid": ORCID, "checked_at": checked, "publications": records}
    # Fetch and validate everything before replacing either public file.
    data_path = ROOT / "data/publications.json"
    data_temp = data_path.with_suffix(".json.tmp")
    page_temp = ROOT / "index.html.tmp"
    data_temp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    page_temp.write_text(page)
    data_temp.replace(data_path)
    page_temp.replace(ROOT / "index.html")
    print(f"Rendered {len(records)} research outputs; ORCID checked {checked}")


if __name__ == "__main__":
    main()
