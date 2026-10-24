"""Behavior tests use isolated source snapshots; never edit the actual website."""
import copy
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publications_sync", ROOT / "scripts/publications_sync.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)
TODAY = dt.date(2026, 10, 24)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name) / "repo"
        self.stage = Path(self.directory.name) / "stage"
        fixtures = ROOT / "tests/fixtures/publications-sync"
        for name, fixture in zip(sync.FILES, ("conferences.yaml", "journals.yaml", "patent.md")):
            destination = self.repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((fixtures / fixture).read_bytes())
        self.baseline = sync.bootstrap(self.repo)
        schema = self.repo / "docs/publications-sync.schema.json"
        schema.parent.mkdir(parents=True, exist_ok=True)
        schema.write_bytes((ROOT / "docs/publications-sync.schema.json").read_bytes())
        for row in self.baseline["sheets"]["journals"]:
            for key in ("image", "cover_image"):
                if row.get(key):
                    image = self.repo / "assets" / row[key]
                    image.parent.mkdir(parents=True, exist_ok=True)
                    image.write_bytes(b"fixture")
        self.payload = {"schema_version": 1, "sheets": copy.deepcopy(self.baseline["sheets"])}

    def run_sync(self, **kwargs):
        return sync.run_sync(self.repo, self.payload, self.baseline, self.stage, TODAY, **kwargs)

    def test_import_and_noop_preserve_every_source_byte(self):
        imported = sync.bootstrap(self.repo)
        self.assertEqual({k: len(v) for k, v in imported["sheets"].items()},
                         {"conferences": 6, "journals": 7, "patents": 15, "schedule": 0})
        for row in imported["sheets"]["conferences"]:
            self.assertEqual(sync.conference_text(row), row["citation_raw"])
        report, _ = self.run_sync()
        self.assertTrue(all(not f["changed"] for f in report["files"]))
        self.assertEqual(len(report["review_warnings"]), 1)
        for name in sync.FILES:
            self.assertEqual((self.repo / name).read_bytes(), (self.stage / name).read_bytes())

    def test_user_structured_edit_overrides_archived_citation(self):
        self.payload["sheets"]["conferences"][0]["title"] = "New structured title"
        self.run_sync()
        output = (self.stage / sync.FILES[0]).read_text(encoding="utf-8")
        self.assertIn("New structured title", output)
        self.assertNotIn(self.baseline["sheets"]["conferences"][0]["title"], output)

    def test_partial_future_draft_never_leaks(self):
        self.payload["sheets"]["conferences"].append({
            "record_id": "future-draft", "publication_status": "검토 중", "progress_status": "예정",
            "legacy_order": 200, "event_date": "2027-04", "title": "PRIVATE DRAFT TITLE"})
        report, _ = self.run_sync()
        self.assertEqual(len(report["blocked"]), 2)
        self.assertNotIn("PRIVATE DRAFT TITLE", (self.stage / sync.FILES[0]).read_text(encoding="utf-8"))

    def test_approved_future_completed_record_is_still_blocked(self):
        new = copy.deepcopy(self.payload["sheets"]["conferences"][0])
        new.update(record_id="future-confirmed", title="FUTURE SECRET", event_date="2027-01", legacy_order=201)
        self.payload["sheets"]["conferences"].append(new)
        report, _ = self.run_sync()
        self.assertIn("future_date", next(r["reasons"] for r in report["blocked"] if r["record_id"] == new["record_id"]))
        self.assertNotIn("FUTURE SECRET", (self.stage / sync.FILES[0]).read_text(encoding="utf-8"))

    def test_unapproved_past_record_is_blocked(self):
        self.payload["sheets"]["conferences"][0]["publication_status"] = "보류"
        report, _ = self.run_sync()
        self.assertEqual(len(report["blocked"]), 2)

    def test_program_confirmation_allows_past_approved_record(self):
        row = self.payload["sheets"]["conferences"][-1]
        row.update(publication_status="게시 승인", progress_status="프로그램·프로시딩 확인", event_date="2026-10-20")
        report, _ = self.run_sync()
        self.assertEqual(report["blocked"], [])
        self.assertIn(row["title"], (self.stage / sync.FILES[0]).read_text(encoding="utf-8"))

    def test_missing_rows_rejected(self):
        self.payload["sheets"]["conferences"].pop()
        with self.assertRaisesRegex(sync.ValidationError, "Missing rows"):
            self.run_sync()

    def test_missing_sheet_rejected(self):
        del self.payload["sheets"]["patents"]
        with self.assertRaisesRegex(sync.ValidationError, "Missing sheet"):
            self.run_sync()

    def test_duplicate_ids_and_content_rejected(self):
        self.payload["sheets"]["conferences"].append(copy.deepcopy(self.payload["sheets"]["conferences"][0]))
        with self.assertRaisesRegex(sync.ValidationError, "Duplicate stable ID"):
            self.run_sync()
        self.payload["sheets"]["conferences"][-1]["record_id"] = "new-duplicate-content"
        with self.assertRaisesRegex(sync.ValidationError, "Duplicate record"):
            self.run_sync()

    def test_source_conflict_rejected_before_staging(self):
        (self.repo / sync.FILES[0]).write_text("presentations: []", encoding="utf-8")
        with self.assertRaisesRegex(sync.ValidationError, "Repository changed"):
            self.run_sync()
        self.assertFalse(self.stage.exists())

    def test_private_columns_and_ack_tab_never_enter_public_files(self):
        row = self.payload["sheets"]["conferences"][0]
        for key in ("acknowledgements", "acknowledgement_source", "grant_ids", "venue", "private_internal"):
            row[key] = "PRIVATE CANARY"
        self.payload["sheets"]["사사"] = [{"secret": "PRIVATE CANARY"}]
        # Display sequence is deliberately unrelated to publication order. Both
        # machine and Korean headers must be accepted without changing output.
        for index, conference in enumerate(self.payload["sheets"]["conferences"]):
            conference["순번" if index % 2 else "private_sequence"] = 1000 + index
        self.payload["sheets"]["conferences"].reverse()
        report, _ = self.run_sync()
        self.assertEqual(report["ignored_sheets"], ["사사"])
        self.assertFalse(any(item["changed"] for item in report["files"]))
        self.assertEqual(report["conference_renumbered_ids"], [])
        for name in sync.FILES:
            self.assertNotIn("PRIVATE CANARY", (self.stage / name).read_text(encoding="utf-8"))
            self.assertEqual((self.stage / name).read_bytes(), (self.repo / name).read_bytes())

    def test_korean_headers_and_keys_have_identical_result(self):
        schema = sync.read_json(ROOT / "docs/publications-sync.schema.json")
        translated = {}
        for sheet in schema["sheets"]:
            mapping = {c["key"]: c["header"] for c in sheet["columns"]}
            translated[sheet["title"]] = [{mapping[k]: v for k, v in row.items()} for row in self.payload["sheets"][sheet["key"]]]
        self.payload["sheets"] = translated
        report, _ = self.run_sync()
        self.assertFalse(any(f["changed"] for f in report["files"]))

    def test_duplicate_header_names_rejected(self):
        self.payload["sheets"]["conferences"][0]["관리 ID"] = "another-id"
        with self.assertRaisesRegex(sync.ValidationError, "duplicate translated"):
            self.run_sync()

    def test_journal_rich_markdown_and_numbers_preserved(self):
        row = self.payload["sheets"]["journals"][4]
        row["note_md"] = "A new [note](https://example.org/)."
        self.run_sync()
        parsed = sync.yaml.safe_load((self.stage / sync.FILES[1]).read_text(encoding="utf-8"))
        self.assertEqual(parsed["published"][0]["authors"], row["authors_md"])
        self.assertIn("**Sukkyung Kang**", parsed["published"][0]["authors"])
        row["display_order"] = 99
        with self.assertRaisesRegex(sync.ValidationError, "number cannot change"):
            self.run_sync()

    def test_unsafe_public_markup_and_urls_rejected(self):
        self.payload["sheets"]["conferences"][0]["title"] = "<script>alert(1)</script>"
        with self.assertRaisesRegex(sync.ValidationError, "raw HTML"):
            self.run_sync()
        self.payload["sheets"]["conferences"][0]["title"] = "[x](jav&#x61;script:alert)"
        with self.assertRaisesRegex(sync.ValidationError, "raw HTML"):
            self.run_sync()
        self.payload["sheets"]["conferences"][0]["title"] = "Safe title"
        self.payload["sheets"]["journals"][4]["doi_url"] = "javascript:alert(1)"
        with self.assertRaises(sync.ValidationError):
            self.run_sync()

    def test_backdated_insert_warns_about_numbers(self):
        new = copy.deepcopy(self.payload["sheets"]["conferences"][0])
        new.update(record_id="new-backdated", title="A historical addition", event_date="2024-03", legacy_order=200)
        self.payload["sheets"]["conferences"].append(new)
        report, _ = self.run_sync()
        self.assertTrue(report["conference_renumbered_ids"])

    def test_patent_families_counts_and_pct_not_counted(self):
        self.payload["sheets"]["patents"][0]["family_title"] = "Edited family title"
        self.run_sync()
        body = sync.patent_body((self.stage / sync.FILES[2]).read_text(encoding="utf-8"))
        self.assertTrue(body.startswith("(Total: 15, Granted: KR 3 / JP 1"))
        self.assertEqual(body.count("PCT/"), 2)
        self.assertIn("Edited family title", body)

    def test_reminders_only_due_and_explicit_delivery_deduplication(self):
        self.payload["sheets"]["schedule"].append({"record_id": "schedule-one", "related_record_id": "",
            "title": "Event", "start_date": "2026-10-31", "end_date": "", "progress_status": "예정", "remind_days": "7,1,0"})
        report, _ = self.run_sync()
        self.assertEqual(len(report["notifications"]), 1)
        notification_id = report["notifications"][0]["notification_id"]
        report, _ = self.run_sync(delivered=[notification_id])
        self.assertEqual(report["notifications"], [])

    def test_apply_is_explicit_and_advances_baseline(self):
        self.payload["sheets"]["conferences"][0]["title"] = "Applied update"
        original = (self.repo / sync.FILES[0]).read_bytes()
        report, next_baseline = self.run_sync()
        self.assertEqual((self.repo / sync.FILES[0]).read_bytes(), original)
        baseline_path = Path(self.directory.name) / "state.json"
        sync.write_json(baseline_path, self.baseline)
        sync.apply_staging(self.repo, baseline_path, self.baseline, self.stage, report, next_baseline)
        self.assertIn(b"Applied update", (self.repo / sync.FILES[0]).read_bytes())
        self.assertFalse((self.repo / ".publications-sync.lock").exists())
        self.baseline = sync.read_json(baseline_path)
        report, _ = self.run_sync()
        self.assertFalse(any(f["changed"] for f in report["files"]))

    def test_concurrent_apply_lock_rejected(self):
        report, next_baseline = self.run_sync()
        (self.repo / ".publications-sync.lock").write_text("another run", encoding="utf-8")
        with self.assertRaisesRegex(sync.ValidationError, "Another apply"):
            sync.apply_staging(self.repo, Path(self.directory.name) / "state.json",
                               self.baseline, self.stage, report, next_baseline)

    def test_after_event_waits_for_end_and_catches_up_once(self):
        row = {"record_id": "schedule-ended", "related_record_id": "", "title": "Past conference",
               "start_date": "2026-10-20", "end_date": "2026-10-22", "progress_status": "예정", "remind_days": ""}
        self.assertEqual(sync.notifications([row], dt.date(2026, 10, 22), set()), [])
        next_day = sync.notifications([row], dt.date(2026, 10, 23), set())
        overdue = sync.notifications([row], TODAY, set())
        self.assertEqual(next_day, overdue)
        self.assertEqual(len(overdue), 1)
        notice = overdue[0]
        self.assertEqual(notice["notification_id"], "schedule-ended:2026-10-22:after_event")
        self.assertEqual(notice["kind"], "after_event")
        self.assertIn("확인", notice["message"])
        self.assertEqual(sync.notifications([row], TODAY, {notice["notification_id"]}), [])
        self.assertEqual(row["progress_status"], "예정")

    def test_cancelled_and_completed_events_do_not_prompt(self):
        for status in ("취소", "완료", "확인 필요"):
            row = {"record_id": "schedule-ended", "title": "Event", "start_date": "2026-10-20",
                   "end_date": "2026-10-22", "progress_status": status, "remind_days": ""}
            self.assertEqual(sync.notifications([row], TODAY, set()), [])

    def test_staging_under_any_repo_path_including_static_is_rejected(self):
        for relative in ("static/registry", "docs/registry", "build/private", ".hidden"):
            self.stage = self.repo / relative
            with self.assertRaisesRegex(sync.ValidationError, "outside the repository"):
                self.run_sync()
            self.assertFalse(self.stage.exists())

    def test_baseline_under_repository_is_rejected_on_apply(self):
        report, next_baseline = self.run_sync()
        with self.assertRaisesRegex(sync.ValidationError, "Baseline must be outside"):
            sync.apply_staging(self.repo, self.repo / "static/state.json",
                               self.baseline, self.stage, report, next_baseline)

    def test_url_delimiters_and_control_characters_cannot_inject_markup(self):
        for url in ("https://example.org/)\n<script>alert(1)</script>\n(",
                    "https://example.org/<img>", "https://example.org/a b",
                    "https://example.org/a" + chr(96), "https://example.org/a\\b"):
            self.payload["sheets"]["patents"][0]["document_url"] = url
            with self.assertRaisesRegex(sync.ValidationError, "URL contains"):
                self.run_sync()
        # Existing encoded Dropbox URLs pass in every no-op test.

    def test_current_month_program_confirmation_requires_exact_day(self):
        row = self.payload["sheets"]["conferences"][-1]
        row.update(publication_status="게시 승인", progress_status="프로그램·프로시딩 확인", event_date="2026-10")
        report, _ = self.run_sync()
        reasons = next(r["reasons"] for r in report["blocked"] if r["record_id"] == row["record_id"])
        self.assertIn("exact_event_date_required", reasons)
        row["event_date"] = "2026-09"
        report, _ = self.run_sync()
        self.assertFalse(any(r["record_id"] == row["record_id"] for r in report["blocked"]))

    def test_native_korean_schedule_dates_normalize_only_date_columns(self):
        self.payload["sheets"]["schedule"].append({"record_id": "native-date-event", "title": "2026. 10. 27",
            "start_date": "2026. 10. 27", "end_date": "2026. 10. 29.", "progress_status": "예정",
            "remind_days": "", "notes": "2026. 10. 27", "related_record_id": ""})
        _, state = self.run_sync()
        row = state["sheets"]["schedule"][0]
        self.assertEqual(row["start_date"], "2026-10-27")
        self.assertEqual(row["end_date"], "2026-10-29")
        self.assertEqual(row["title"], "2026. 10. 27")
        self.assertEqual(row["notes"], "2026. 10. 27")
        self.assertEqual(state["sheets"]["conferences"][0]["event_date"], self.payload["sheets"]["conferences"][0]["event_date"])

    def test_journal_and_patent_private_fields_do_not_change_public_output(self):
        for kind in ("journals", "patents"):
            self.payload["sheets"][kind].reverse()
            for i, row in enumerate(self.payload["sheets"][kind]):
                row.update(acknowledgements="PRIVATE FUNDING", grant_ids="PRIVATE PROJECT")
                if kind == "journals":
                    row["private_sequence"] = i + 1
        report, state = self.run_sync()
        self.assertFalse(any(f["changed"] for f in report["files"]))
        self.assertEqual(state["sheets"]["journals"][0]["acknowledgements"], "PRIVATE FUNDING")
        for name in sync.FILES:
            self.assertNotIn("PRIVATE", (self.stage / name).read_text(encoding="utf-8"))

    def test_previous_korean_headers_still_normalize_and_duplicates_fail(self):
        row = self.payload["sheets"]["journals"][0]
        row["논문 날짜"] = row.pop("publication_date")
        row["저자 (Markdown)"] = row.pop("authors_md")
        report, _ = self.run_sync()
        self.assertFalse(any(f["changed"] for f in report["files"]))
        row["게재 날짜"] = row["논문 날짜"]
        with self.assertRaisesRegex(sync.ValidationError, "duplicate translated field"):
            self.run_sync()

    def test_ambiguous_and_invalid_schedule_dates_are_not_guessed(self):
        row = {"record_id": "native-date-event", "title": "Event", "start_date": "10/27/2026",
               "end_date": "", "progress_status": "예정", "remind_days": "", "related_record_id": ""}
        self.payload["sheets"]["schedule"].append(row)
        with self.assertRaises(ValueError):
            self.run_sync()
        row["start_date"] = "2026. 2. 30"
        with self.assertRaises(ValueError):
            self.run_sync()


if __name__ == "__main__":
    unittest.main()
