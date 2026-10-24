#!/usr/bin/env python3
"""Private Sheet JSON to validated website staging; no network or credentials."""
import argparse
import calendar
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

import yaml

FILES = ("data/conferences.yaml", "data/journals.yaml", "content/publications/patent/_index.md")
APPROVED = "게시 승인"
STATES = {
    "conferences": {"기존 실적", "발표 완료", "프로그램·프로시딩 확인", "예정", "발표 여부 확인", "취소"},
    "journals": {"투고", "심사 중", "수정 중", "게재 승인", "출판"},
    "patents": {"출원", "등록"},
    "schedule": {"예정", "완료", "취소", "확인 필요"},
}
MONTHS = {name: i for i, name in enumerate(calendar.month_name) if name}
NAMESPACE = uuid.UUID("4dc0943f-29d8-490e-8b7c-98e6146782ba")


class ValidationError(ValueError):
    pass


def check(condition, message):
    if not condition:
        raise ValidationError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_id(kind, locator):
    """One-time import ID; retained permanently, not recomputed after edits."""
    return kind + "-" + str(uuid.uuid5(NAMESPACE, kind + ":" + locator))


def snapshot(repo):
    return {name: {"sha256": digest((repo / name).read_bytes()),
                   "text": (repo / name).read_bytes().decode("utf-8")} for name in FILES}


def parse_date(value, required=False):
    value = str(value or "").strip()
    if not value:
        check(not required, "Missing date")
        return None
    check(bool(re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", value)), "Invalid date: " + value)
    parts = list(map(int, value.split("-")))
    return dt.date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)


def integer(value, label, minimum=1):
    check(not isinstance(value, bool) and bool(re.fullmatch(r"\d+", str(value))), label + " must be an integer")
    value = int(value)
    check(value >= minimum, label + " is too small")
    return value


def parse_conference(citation):
    match = re.search(r", ((?:oral|poster)(?: \(online\))? (?:presentation|prestation)) in ", citation)
    check(match is not None, "Conference format needs review")
    tokens = citation[:match.start()].split(", ")
    author = re.compile(r"^(?:(?:[A-Za-z]\.-)?[A-Za-z]\.\s*)+[A-Za-z][A-Za-z-]*\*?$")
    count = 0
    while count < len(tokens) and author.fullmatch(tokens[count]):
        count += 1
    check(0 < count < len(tokens), "Conference author/title boundary needs review")
    tail = citation[match.end():]
    date_match = re.search(r", (" + "|".join(MONTHS) + r") (\d{4})$", tail)
    check(date_match is not None, "Conference date needs review")
    event_location = tail[:date_match.start()]
    event_match = re.match(r"^(.+\([^)]*\)(?: \d{4})?), (.+)$", event_location)
    if event_match:
        event, location = event_match.groups()
    else:
        event, separator, location = event_location.partition(", ")
        check(bool(separator), "Conference location needs review")
    return {"authors": ", ".join(tokens[:count]), "title": ", ".join(tokens[count:]),
            "presentation_type": match.group(1), "event_name": event, "location": location,
            "event_date": f"{date_match.group(2)}-{MONTHS[date_match.group(1)]:02d}", "format_mode": "structured"}


def conference_text(row):
    if row.get("format_mode") == "legacy":
        check(not any(row.get(k) for k in ("authors", "title", "event_name", "location", "presentation_type")),
              row["record_id"] + ": legacy mode cannot silently ignore structured edits")
        check(bool(row.get("citation_raw")), "Empty legacy citation")
        return row["citation_raw"]
    date = parse_date(row.get("event_date"), True)
    check(len(str(row["event_date"])) >= 7, "Conference needs at least month precision")
    for key in ("authors", "title", "event_name", "location", "presentation_type"):
        check(bool(row.get(key)), row["record_id"] + ": missing " + key)
    return f"{row['authors']}, {row['title']}, {row['presentation_type']} in {row['event_name']}, {row['location']}, {calendar.month_name[date.month]} {date.year}"


def patent_body(text):
    return yaml.safe_load(text.split("---", 2)[1])["sections"][0]["content"]["text"]


def import_patents(text):
    pieces = patent_body(text).strip().split("\n\n<br>\n\n")
    pieces[0] = pieces[0].split("\n\n", 1)[1]
    rows = []
    for order, piece in enumerate(pieces, 1):
        family_id = stable_id("family", str(order))
        filings, pct, extra = [], "", []
        for line in piece.splitlines():
            match = re.match(r"^- \*\*(.*?)\*\*(.*)$", line)
            if not match:
                if line.strip():
                    extra.append(line.strip().removesuffix("<br>"))
                continue
            label, note = match.groups()
            if label.startswith("(PCT/"):
                pct = label[1:-1]
                continue
            link = re.fullmatch(r"\[([^\]]+)\]\((.+)\)", label)
            label, url = link.groups() if link else (label, "")
            filing = re.fullmatch(r"([A-Z]{2}) Patent( Application)? (.+)", label)
            check(filing is not None, "Unrecognized patent: " + label)
            country, application, number = filing.groups()
            filings.append({"record_id": stable_id("patent", country + ":" + number),
                "publication_status": APPROVED, "family_id": family_id, "family_order": order,
                "filing_order": len(filings) + 1, "progress_status": "출원" if application else "등록",
                "jurisdiction": country, "number": number, "family_title": "", "pct_reference": "",
                "document_url": url, "filing_note_md": note.removesuffix("<br>").strip(),
                "family_note_md": "", "evidence_url": ""})
        check(bool(filings) and bool(extra), "Patent family needs filings and title")
        filings[0].update(family_title=extra[0], pct_reference=pct, family_note_md="\n".join(extra[1:]))
        rows.extend(filings)
    return rows


def bootstrap(repo):
    sources = snapshot(repo)
    raw = sources[FILES[0]]["text"]
    citations = yaml.safe_load(raw)["presentations"]
    comments = [yaml.safe_load(line.lstrip("# "))[0] for line in raw.splitlines() if re.match(r"^#\s+- ", line)]
    conferences = []
    for i, citation in enumerate(citations + comments, 1):
        live = i <= len(citations)
        row = {"record_id": stable_id("conference", str(i)), "publication_status": APPROVED if live else "검토 중",
            "progress_status": "기존 실적" if live else "발표 여부 확인", "legacy_order": i,
            "presenter": "", "professor_role": "", "evidence_url": "", "citation_raw": citation,
            "venue": "", "scope": "미확인", "acknowledgements": "", "acknowledgement_status": "",
            "acknowledgement_source": "", "grant_ids": ""}
        row.update(parse_conference(citation))
        check(conference_text(row) == citation, "Conference round-trip changed record " + str(i))
        conferences.append(row)
    data = yaml.safe_load(sources[FILES[1]]["text"])
    journals = []
    for i, citation in enumerate(data["submitted"], 1):
        title, separator, details = citation.rpartition(", ")
        check(bool(separator), "Submitted title needs review")
        journals.append({"record_id": stable_id("journal", "submitted:" + str(i)), "publication_status": APPROVED,
            "progress_status": "심사 중" if "under review" in details else "수정 중" if "revision" in details else "투고",
            "publication_date": "", "display_order": "", "legacy_order": i, "title": title, "authors_md": "",
            "journal": "", "details": details, "note_md": "", "image": "", "cover_image": "",
            "doi_url": "", "pdf_url": "", "links_extra_json": "[]", "evidence_url": "", "citation_raw": citation})
    for i, pub in enumerate(data["published"], 1):
        check(not set(pub) - {"order", "title", "image", "cover_image", "authors", "journal", "details", "note", "links"},
              "Unmapped journal field")
        standard = {link["label"]: link for link in pub.get("links", []) if link["label"] in {"doi", "pdf"}}
        for label, icon in (("doi", "arrow-top-right-on-square"), ("pdf", "document-arrow-down")):
            if label in standard:
                check(standard[label]["pack"] == "hero" and standard[label]["icon"] == icon, "Nonstandard link metadata")
        years = re.findall(r"\b(20\d{2})\b", pub.get("details", ""))
        journals.append({"record_id": stable_id("journal", "published:" + str(pub["order"])), "publication_status": APPROVED,
            "progress_status": "게재 승인" if pub.get("details") == "accepted" else "출판", "publication_date": years[-1] if years else "",
            "display_order": pub["order"], "legacy_order": i, "title": pub["title"], "authors_md": pub.get("authors", ""),
            "journal": pub.get("journal", ""), "details": pub.get("details", ""), "note_md": pub.get("note", ""),
            "image": pub.get("image", ""), "cover_image": pub.get("cover_image", ""),
            "doi_url": standard.get("doi", {}).get("url", ""), "pdf_url": standard.get("pdf", {}).get("url", ""),
            "links_extra_json": json.dumps([link for link in pub.get("links", []) if link["label"] not in {"doi", "pdf"}], ensure_ascii=False),
            "evidence_url": "", "citation_raw": ""})
    return {"schema_version": 1, "source_snapshot": sources, "sheets": {"conferences": conferences,
        "journals": journals, "patents": import_patents(sources[FILES[2]]["text"]), "schedule": []}}


def normalize(payload, spec):
    check(payload.get("schema_version") == 1, "Unsupported schema_version")
    check(isinstance(payload.get("sheets"), dict), "Missing sheets object")
    result = {}
    for sheet in spec["sheets"]:
        key, title = sheet["key"], sheet["title"]
        check(not (key in payload["sheets"] and title in payload["sheets"]), "Duplicate sheet key/title")
        rows = payload["sheets"].get(key, payload["sheets"].get(title))
        check(isinstance(rows, list), "Missing sheet: " + key)
        columns = [c["key"] for c in sheet["columns"]]
        mapping = {name: c["key"] for c in sheet["columns"]
                   for name in [c["header"], *c.get("aliases", [])]}
        converted = []
        for row in rows:
            check(isinstance(row, dict), "Rows must be objects")
            if not any(v not in (None, "") for v in row.values()):
                continue
            item = {}
            for name, value in row.items():
                field = mapping.get(name, name)
                check(field in columns or field.startswith("private_"), key + ": unknown field " + name)
                check(field not in item, key + ": duplicate translated field")
                check(value is None or isinstance(value, (str, int, float)) and not isinstance(value, bool),
                      key + ": cell must be plain text/number")
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
                if key == "schedule" and field in {"start_date", "end_date"} and isinstance(value, str):
                    localized = re.fullmatch(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?", value.strip())
                    if localized:
                        value = dt.date(*map(int, localized.groups())).isoformat()
                item[field] = "" if value is None else value
            converted.append({field: item.get(field, "") for field in columns + sorted(set(item) - set(columns))})
        result[key] = converted
    known = {s["key"] for s in spec["sheets"]} | {s["title"] for s in spec["sheets"]} | set(spec.get("optional_ignored_sheets", []))
    check(not set(payload["sheets"]) - known, "Unexpected input sheet")
    return result


def validate_url(value, label, placeholder=False):
    if not value or placeholder and value == "#":
        return
    check(isinstance(value, str), label + ": URL must be text")
    check(not re.search(r"[\x00-\x20\x7f<>\"'()\\]", value) and chr(96) not in value,
          label + ": URL contains control characters or Markdown/HTML delimiters")
    parsed = urlparse(value)
    check(parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username,
          label + ": expected HTTP(S) URL")


def safe_text(value, label):
    check(isinstance(value, str), label + ": expected text")
    check(not re.search(r"<[/A-Za-z]|\{\{[<%]|(?:javascript|data|vbscript)\s*:", html.unescape(value), re.I),
          label + ": raw HTML, shortcodes and unsafe schemes are unsupported")


def offsets(value):
    if value in (None, ""):
        return []
    return sorted({integer(part.strip(), "remind_days", 0) for part in str(value).split(",")}, reverse=True)


def validate(sheets, baseline, repo, today, allow_missing=False):
    ids, semantic, doi_seen = set(), set(), set()
    original_ids = {r["record_id"] for rows in baseline["sheets"].values() for r in rows}
    old_journals = {r["record_id"]: r for r in baseline["sheets"]["journals"]}
    blocked = []
    for kind, rows in sheets.items():
        for row in rows:
            rid = row.get("record_id", "")
            check(isinstance(rid, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,100}", rid)), "Missing/invalid stable ID")
            check(rid not in ids, "Duplicate stable ID: " + rid)
            ids.add(rid)
            check(row.get("progress_status") in STATES[kind], rid + ": invalid progress state")
            if kind == "schedule":
                start, end = parse_date(row.get("start_date"), True), parse_date(row.get("end_date"))
                check(len(str(row["start_date"])) == 10, rid + ": reminder date needs YYYY-MM-DD")
                check(end is None or end >= start, rid + ": end before start")
                offsets(row.get("remind_days"))
                continue
            check(row.get("publication_status") in {APPROVED, "검토 중", "보류"}, rid + ": invalid publication state")
            date = parse_date(row.get("event_date") if kind == "conferences" else row.get("publication_date"))
            reasons = []
            if row["publication_status"] != APPROVED:
                reasons.append("not_approved")
            if date and date > today:
                reasons.append("future_date")
            if kind == "conferences" and row["progress_status"] not in {"기존 실적", "발표 완료", "프로그램·프로시딩 확인"}:
                reasons.append("presentation_not_confirmed")
            if kind == "conferences" and row["progress_status"] == "프로그램·프로시딩 확인" and date:
                precision = len(str(row["event_date"]))
                if precision < 10:
                    period_end = (dt.date(date.year, 12, 31) if precision == 4 else
                                  dt.date(date.year, date.month, calendar.monthrange(date.year, date.month)[1]))
                    if today <= period_end:
                        reasons.append("exact_event_date_required")
            if reasons:
                blocked.append({"record_id": rid, "reasons": reasons})
            # Draft/planned rows may be incomplete. Only public fields are validated/rendered below.
            if kind == "conferences":
                integer(row["legacy_order"], rid + ":legacy_order")
                if not reasons:
                    check(row.get("format_mode") in {"structured", "legacy"}, rid + ": invalid format_mode")
                    text = conference_text(row)
                    safe_text(text, rid)
                    unique = (kind, text)
                else:
                    unique = (kind, rid)
            elif kind == "journals":
                if reasons:
                    continue
                for key in ("title", "authors_md", "journal", "details", "note_md"):
                    safe_text(row.get(key, ""), rid + ":" + key)
                check(bool(row["title"]), rid + ": missing title")
                integer(row["legacy_order"], rid + ":legacy_order")
                if row["progress_status"] in {"게재 승인", "출판"}:
                    integer(row["display_order"], rid + ":display_order")
                if old_journals.get(rid, {}).get("display_order"):
                    check(str(row["display_order"]) == str(old_journals[rid]["display_order"]), rid + ": existing journal number cannot change")
                for field in ("image", "cover_image"):
                    if row.get(field):
                        asset = (repo / "assets" / row[field]).resolve()
                        check(asset.is_relative_to((repo / "assets/media/publications").resolve()) and asset.is_file(),
                              rid + ": invalid/missing image " + row[field])
                for field in ("doi_url", "pdf_url"):
                    validate_url(row.get(field), rid + ":" + field, field == "pdf_url")
                if row.get("doi_url"):
                    normalized = row["doi_url"].strip().lower().rstrip("/")
                    check(normalized not in doi_seen, "Duplicate DOI/paper URL: " + rid)
                    doi_seen.add(normalized)
                extra = json.loads(row.get("links_extra_json") or "[]")
                check(isinstance(extra, list), rid + ": extra links must be a JSON array")
                for link in extra:
                    check(isinstance(link, dict) and set(link) == {"pack", "icon", "label", "url"}, rid + ": invalid extra link")
                    check(link["label"] not in {"doi", "pdf"}, rid + ": duplicate DOI/PDF field")
                    for key in ("label", "pack", "icon"):
                        check(bool(re.fullmatch(r"[A-Za-z0-9 _-]+", link[key])), rid + ": invalid link metadata")
                    validate_url(link["url"], rid, True)
                unique = (kind, row["title"].strip().casefold())
            else:
                if reasons:
                    continue
                integer(row["family_order"], rid + ":family_order")
                integer(row["filing_order"], rid + ":filing_order")
                check(bool(row["family_id"]) and bool(row["number"]) and isinstance(row["number"], str) and
                      bool(re.fullmatch(r"[A-Z]{2}", str(row["jurisdiction"]))), rid + ": invalid patent identifier")
                for key in ("number", "family_title", "filing_note_md", "family_note_md"):
                    safe_text(row.get(key, ""), rid + ":" + key)
                validate_url(row.get("document_url"), rid)
                unique = (kind, row["jurisdiction"], row["number"])
            check(unique not in semantic, "Duplicate record content: " + rid)
            semantic.add(unique)
    check(allow_missing or original_ids <= ids, "Missing rows would delete records: " + ", ".join(sorted(original_ids - ids)))
    numbers = [int(r["display_order"]) for r in sheets["journals"] if r.get("display_order")]
    check(len(numbers) == len(set(numbers)), "Duplicate journal numbers")
    for row in sheets["schedule"]:
        check(not row.get("related_record_id") or row["related_record_id"] in ids, "Schedule references unknown record")
    return blocked


def export_journals(rows):
    data = {"submitted": [], "published": []}
    for row in sorted(rows, key=lambda r: int(r["legacy_order"])):
        if row["progress_status"] not in {"게재 승인", "출판"}:
            data["submitted"].append(row["title"] + ", " + row["details"])
            continue
        item = {"order": int(row["display_order"]), "title": row["title"]}
        for source, target in (("image", "image"), ("cover_image", "cover_image"), ("authors_md", "authors"),
                               ("journal", "journal"), ("details", "details"), ("note_md", "note")):
            if row.get(source):
                item[target] = row[source]
        links = []
        for field, label, icon in (("doi_url", "doi", "arrow-top-right-on-square"), ("pdf_url", "pdf", "document-arrow-down")):
            if row.get(field):
                links.append({"pack": "hero", "icon": icon, "label": label, "url": row[field]})
        links.extend(json.loads(row.get("links_extra_json") or "[]"))
        if links:
            item["links"] = links
        data["published"].append(item)
    data["published"].sort(key=lambda item: item["order"])
    return data


def export_patents(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["family_id"]].append(row)
    def counts(state):
        counter = Counter(r["jurisdiction"] for r in rows if r["progress_status"] == state)
        preferred = ["KR", "US", "EP", "JP", "CN", "TW"]
        keys = [k for k in preferred if k in counter] + sorted(set(counter) - set(preferred))
        return " / ".join(f"{k} {counter[k]}" for k in keys) or "0"
    total = f"(Total: {len(rows)}, Granted: {counts('등록')}, Applications: {counts('출원')})"
    pieces, seen_order = [], set()
    for family in sorted(groups.values(), key=lambda group: int(group[0]["family_order"])):
        order = {int(r["family_order"]) for r in family}
        check(len(order) == 1 and not order & seen_order, "Conflicting family order")
        seen_order |= order
        family.sort(key=lambda r: int(r["filing_order"]))
        check(len({int(r["filing_order"]) for r in family}) == len(family), "Duplicate filing order")
        lead = family[0]
        check(bool(lead.get("family_title")), "First visible filing needs family_title: " + lead["family_id"])
        check(all(not any(r.get(k) for k in ("family_title", "pct_reference", "family_note_md")) for r in family[1:]),
              "Family fields belong on first filing only")
        lines = []
        for row in family:
            label = f"{row['jurisdiction']} Patent{' Application' if row['progress_status'] == '출원' else ''} {row['number']}"
            if row.get("document_url"):
                label = f"[{label}]({row['document_url']})"
            lines.append("- **" + label + "**" + (" " + row["filing_note_md"] if row.get("filing_note_md") else ""))
        if lead.get("pct_reference"):
            check(bool(re.fullmatch(r"PCT/[A-Z]{2}\d{4}/\d+", lead["pct_reference"])), "Invalid PCT reference")
            lines.append("- **(" + lead["pct_reference"] + ")**")
        lines[-1] += "<br>"
        lines.append("  " + lead["family_title"])
        if lead.get("family_note_md"):
            lines[-1] += "<br>"
            lines.extend("  " + line for line in lead["family_note_md"].splitlines())
        pieces.append("\n".join(lines))
    return total + "\n\n" + "\n\n<br>\n\n".join(pieces) + "\n"


def generate(sheets, baseline, blocked):
    blocked_ids = {r["record_id"] for r in blocked}
    visible = {kind: [r for r in rows if r["record_id"] not in blocked_ids] for kind, rows in sheets.items()}
    def sort_conferences(rows):
        return sorted(rows, key=lambda r: (-parse_date(r["event_date"], True).toordinal(), int(r["legacy_order"]), r["record_id"]))
    conferences = sort_conferences(visible["conferences"])
    old = sort_conferences([r for r in baseline["sheets"]["conferences"] if r["publication_status"] == APPROVED and
                           r["progress_status"] in {"기존 실적", "발표 완료", "프로그램·프로시딩 확인"}])
    old_numbers = {r["record_id"]: len(old) - i for i, r in enumerate(old)}
    renumbered = [r["record_id"] for i, r in enumerate(conferences) if r["record_id"] in old_numbers and
                  old_numbers[r["record_id"]] != len(conferences) - i]
    result = {}
    for name, data in ((FILES[0], {"presentations": [conference_text(r) for r in conferences]}),
                       (FILES[1], export_journals(visible["journals"]))):
        original = baseline["source_snapshot"][name]["text"]
        result[name] = original if yaml.safe_load(original) == data else yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100000)
    original = baseline["source_snapshot"][FILES[2]]["text"]
    body = export_patents(visible["patents"])
    if patent_body(original).strip() == body.strip():
        result[FILES[2]] = original
    else:
        pattern = re.compile(r"(?m)^(      text: \|\r?\n)(.*?)(?=    design:)", re.S)
        check(bool(pattern.search(original)), "Unexpected patent content location")
        eol = "\r\n" if "\r\n" in original else "\n"
        indented = eol.join("        " + line if line else "" for line in body.rstrip().splitlines()) + eol + eol
        result[FILES[2]] = pattern.sub(lambda m: m.group(1) + indented, original, count=1)
    return result, renumbered


def notifications(rows, today, delivered):
    result = []
    for row in rows:
        if row["progress_status"] != "예정":
            continue
        for offset in offsets(row.get("remind_days")):
            date = parse_date(row["start_date"], True)
            key = f"{row['record_id']}:{row['start_date']}:{offset}"
            if today == date - dt.timedelta(days=offset) and key not in delivered:
                result.append({"notification_id": key, "kind": "before_event", "record_id": row["record_id"], "title": row["title"],
                               "start_date": row["start_date"], "days_before": offset})
        end_text = row.get("end_date") or row["start_date"]
        end = parse_date(end_text, True)
        key = f"{row['record_id']}:{end_text}:after_event"
        if today > end and key not in delivered:
            result.append({"notification_id": key, "kind": "after_event", "record_id": row["record_id"],
                           "related_record_id": row.get("related_record_id", ""),
                           "title": "행사 종료: 참가/발표 확인", "event_title": row["title"], "end_date": end_text,
                           "message": "행사가 종료되었습니다. 실제 참가·발표 여부를 확인해 주세요."})
    return result


def check_baseline(repo, baseline):
    check(set(baseline.get("source_snapshot", {})) == set(FILES), "Invalid baseline file set")
    for name in FILES:
        saved = baseline["source_snapshot"][name]
        check(digest(saved["text"].encode("utf-8")) == saved["sha256"], "Corrupted baseline: " + name)
        check(digest((repo / name).read_bytes()) == saved["sha256"], "Repository changed since baseline: " + name)


def run_sync(repo, payload, baseline, staging, today, allow_missing=False, delivered=()):
    check_baseline(repo, baseline)
    staging = staging.resolve()
    check(not staging.is_relative_to(repo.resolve()), "Staging must be outside the repository")
    spec = read_json(repo / "docs/publications-sync.schema.json")
    sheets = normalize(payload, spec)
    blocked = validate(sheets, baseline, repo, today, allow_missing)
    outputs, renumbered = generate(sheets, baseline, blocked)
    report = {"schema_version": 1, "date": today.isoformat(), "blocked": blocked, "files": [],
              "conference_renumbered_ids": renumbered,
              "review_warnings": [{"record_id": r["record_id"], "field": "event_name", "code": "legacy_duplicate_phrase",
                                   "message": "기존 원문 학회명에 발표 형식 문구가 중복되어 있습니다. 원문을 보존했으며 수동 검토가 필요합니다."}
                                  for r in sheets["conferences"] if re.search(r"(?:presentation|prestation) in ", r.get("event_name", ""))],
              "ignored_sheets": sorted(set(payload["sheets"]) & set(spec.get("optional_ignored_sheets", []))),
              "notifications": notifications(sheets["schedule"], today, set(delivered))}
    for name, text in outputs.items():
        data = text.encode("utf-8")
        destination = staging / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        report["files"].append({"path": name, "sha256": digest(data),
                                "changed": digest(data) != baseline["source_snapshot"][name]["sha256"]})
    next_baseline = {"schema_version": 1, "sheets": sheets,
                    "source_snapshot": {name: {"text": text, "sha256": digest(text.encode("utf-8"))} for name, text in outputs.items()}}
    write_json(staging / "report.json", report)
    write_json(staging / "notifications.json", report["notifications"])
    write_json(staging / "next-baseline.json", next_baseline)
    return report, next_baseline


def apply_staging(repo, baseline_path, baseline, staging, report, next_baseline):
    check(not baseline_path.resolve().is_relative_to(repo.resolve()), "Baseline must be outside the repository")
    check(not staging.resolve().is_relative_to(repo.resolve()), "Staging must be outside the repository")
    lock = repo / ".publications-sync.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValidationError("Another apply may be active; inspect existing sync lock") from exc
    os.close(descriptor)
    originals = {}
    try:
        check_baseline(repo, baseline)
        changed = [item for item in report["files"] if item["changed"]]
        originals = {item["path"]: (repo / item["path"]).read_bytes() for item in changed}
        for item in changed:
            name = item["path"]
            data = (staging / name).read_bytes()
            check(digest(data) == item["sha256"], "Staging changed: " + name)
            backup = staging / "backup" / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(originals[name])
            temporary = (repo / name).with_name((repo / name).name + ".publications-sync.tmp")
            check(not temporary.exists(), "Unexpected temporary file")
            temporary.write_bytes(data)
            temporary.replace(repo / name)
        write_json(staging / "baseline-before-apply.json", baseline)
        state_temp = baseline_path.with_name(baseline_path.name + ".publications-sync.tmp")
        check(not state_temp.exists(), "Unexpected baseline temporary file")
        write_json(state_temp, next_baseline)
        state_temp.replace(baseline_path)
    except Exception:
        for name, data in originals.items():
            (repo / name).write_bytes(data)
        raise
    finally:
        lock.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("bootstrap")
    seed.add_argument("--output", type=Path, required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("--input", type=Path, required=True)
    sync.add_argument("--baseline", type=Path, required=True)
    sync.add_argument("--staging", type=Path, required=True)
    sync.add_argument("--today", default=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat())
    sync.add_argument("--delivered", type=Path)
    sync.add_argument("--apply", action="store_true", help="Explicitly write sources and advance local baseline; no commit/push")
    sync.add_argument("--allow-missing", action="store_true", help="Explicitly permit missing rows to remove records")
    ack = sub.add_parser("ack-notifications")
    ack.add_argument("--state", type=Path, required=True)
    ack.add_argument("--id", action="append", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "bootstrap":
            check(not args.output.resolve().is_relative_to(args.repo.resolve()), "Bootstrap output must be outside the repository")
            value = bootstrap(args.repo)
            write_json(args.output, value)
            print(json.dumps({"result": "imported", "counts": {k: len(v) for k, v in value["sheets"].items()}}))
        elif args.command == "ack-notifications":
            check(not args.state.resolve().is_relative_to(args.repo.resolve()), "Notification state must be outside the repository")
            existing = read_json(args.state) if args.state.exists() else []
            check(isinstance(existing, list), "Notification state must be a list")
            write_json(args.state, sorted(set(existing) | set(args.id)))
        else:
            check(not args.baseline.resolve().is_relative_to(args.repo.resolve()), "Baseline must be outside the repository")
            baseline = read_json(args.baseline)
            delivered = read_json(args.delivered) if args.delivered and args.delivered.exists() else []
            check(isinstance(delivered, list), "Notification state must be a list")
            report, next_baseline = run_sync(args.repo, read_json(args.input), baseline, args.staging,
                dt.date.fromisoformat(args.today), args.allow_missing, delivered)
            if args.apply:
                apply_staging(args.repo, args.baseline, baseline, args.staging, report, next_baseline)
            print(json.dumps({"result": "applied" if args.apply else "staged",
                "changed_files": [f["path"] for f in report["files"] if f["changed"]],
                "blocked_count": len(report["blocked"]), "renumbered_count": len(report["conference_renumbered_ids"]),
                "notifications": len(report["notifications"])}))
        return 0
    except (ValidationError, OSError, ValueError, yaml.YAMLError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
