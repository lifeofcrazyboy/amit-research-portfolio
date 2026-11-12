"""Checks for merging external metadata and safely retaining the publication snapshot."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sync_publications as sync


class PublicationSyncTests(unittest.TestCase):
    def test_same_doi_merges_but_distinct_dois_remain(self):
        remote = [{"title": "Same title", "year": 2026, "doi": "https://doi.org/10.1234/ABC", "source": "ORCID"},
                  {"title": "Same title", "year": 2026, "doi": "10.1234/another", "source": "ORCID"}]
        manual = [{"title": "Curated title", "year": 2026, "doi": "10.1234/abc", "source": "CV", "type": "conference-abstract"}]
        merged = sync.merge_records(remote, manual)
        self.assertEqual(len(merged), 2)
        curated = next(x for x in merged if x["doi"] == "10.1234/abc")
        self.assertEqual(curated["title"], "Curated title")
        self.assertEqual(curated["type"], "conference-abstract")
        self.assertEqual(curated["source"], "ORCID + CV")

    def test_remote_content_cannot_inject_markup_or_script_links(self):
        rendered = sync.render_record({"title": '<img src=x onerror="alert(1)">', "authors": '<script>bad</script>',
                                       "journal": "A & B", "type": 'other" onmouseover="bad', "year": None,
                                       "url": "javascript:alert(1)"})
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img", rendered)
        self.assertNotIn('href="javascript:', rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("n.d.", rendered)

    def test_failed_or_empty_fetch_preserves_both_saved_files(self):
        for failure in [RuntimeError("ORCID unavailable"), {"group": []}, {"invalid": True}]:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "data").mkdir()
                (root / "data/manual-publications.json").write_text("[]")
                (root / "data/publications.json").write_text("saved publications")
                (root / "index.html").write_text("saved website")
                options = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
                with patch.object(sync, "ROOT", root), patch.object(sync, "request_json", **options), patch("sys.argv", ["sync"]):
                    with self.assertRaises((RuntimeError, ValueError)):
                        sync.main()
                self.assertEqual((root / "data/publications.json").read_text(), "saved publications")
                self.assertEqual((root / "index.html").read_text(), "saved website")

    def test_successful_new_work_is_rendered_without_browser_javascript(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/manual-publications.json").write_text("[]")
            (root / "index.html").write_text('<!-- PUBLICATIONS:START --><!-- PUBLICATIONS:END -->'
                                             '<!-- ARTICLE_COUNT:START --><!-- ARTICLE_COUNT:END -->'
                                             '<!-- SYNC_STATUS:START --><!-- SYNC_STATUS:END -->')
            work = {"visibility": "public", "put-code": 123, "title": {"title": {"value": "A new paper"}},
                    "publication-date": {"year": {"value": "2027"}}, "type": "journal-article",
                    "external-ids": {"external-id": [{"external-id-type": "doi", "external-id-value": "10.1234/new",
                                                       "external-id-relationship": "self"}]}}
            responses = [{"group": [{"work-summary": [{"put-code": 123}]}]}, work]
            with patch.object(sync, "ROOT", root), patch.object(sync, "request_json", side_effect=responses), patch("sys.argv", ["sync"]), contextlib.redirect_stdout(io.StringIO()):
                sync.main()
            self.assertIn("A new paper", (root / "index.html").read_text())
            self.assertIn("https://doi.org/10.1234/new", (root / "index.html").read_text())
            self.assertEqual(len(json.loads((root / "data/publications.json").read_text())["publications"]), 1)


if __name__ == "__main__":
    unittest.main()
