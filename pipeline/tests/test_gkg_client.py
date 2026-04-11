"""Unit tests for gkg_client.

No network. All tests use synthetic GKG lines or pre-canned zip bytes injected
via the `url_fetcher` parameter. The integration test that hits the real GKG
CDN lives in test_gkg_client_integration.py and is skipped unless
SALIENT_RUN_NETWORK_TESTS=1 is set.
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import pytest

from src.gkg_client import (
    GKG_BULK_BASE_URL,
    VALID_GKG_MINUTES,
    GkgFileResult,
    GkgRow,
    build_masterfile_url,
    fetch_gkg_file,
    iter_15min_slices,
    parse_gkg_line,
)


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------
class TestBuildMasterfileUrl:
    def test_canonical_noon_slice(self):
        url = build_masterfile_url(
            datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc)
        )
        assert url == f"{GKG_BULK_BASE_URL}/20260409120000.gkg.csv.zip"

    def test_fifteen_min_slice(self):
        url = build_masterfile_url(
            datetime(2026, 4, 9, 12, 15, tzinfo=timezone.utc)
        )
        assert url == f"{GKG_BULK_BASE_URL}/20260409121500.gkg.csv.zip"

    def test_every_valid_minute(self):
        for minute in VALID_GKG_MINUTES:
            url = build_masterfile_url(
                datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)
            )
            assert url.endswith(f"2026010100{minute:02d}00.gkg.csv.zip")

    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            build_masterfile_url(datetime(2026, 4, 9, 12, 0))

    def test_rejects_invalid_minute(self):
        with pytest.raises(ValueError, match="must be one of"):
            build_masterfile_url(
                datetime(2026, 4, 9, 12, 7, tzinfo=timezone.utc)
            )

    def test_converts_from_local_tz_to_utc(self):
        # A "local" EST 7am datetime should convert to UTC 12:00
        from datetime import timezone as tz, timedelta
        est = tz(timedelta(hours=-5))
        url = build_masterfile_url(
            datetime(2026, 4, 9, 7, 0, tzinfo=est)
        )
        assert url.endswith("20260409120000.gkg.csv.zip")


class TestIter15MinSlices:
    def test_yields_four_per_hour(self):
        start = datetime(2026, 4, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 9, 0, 45, tzinfo=timezone.utc)
        slices = list(iter_15min_slices(start, end))
        assert len(slices) == 4
        assert slices[0].minute == 0
        assert slices[-1].minute == 45

    def test_spans_multiple_hours(self):
        start = datetime(2026, 4, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 9, 2, 0, tzinfo=timezone.utc)
        slices = list(iter_15min_slices(start, end))
        # 0:00 0:15 0:30 0:45 1:00 1:15 1:30 1:45 2:00 = 9 slices
        assert len(slices) == 9

    def test_rejects_off_boundary_minute(self):
        with pytest.raises(ValueError, match="15-min boundaries"):
            list(iter_15min_slices(
                datetime(2026, 4, 9, 0, 7, tzinfo=timezone.utc),
                datetime(2026, 4, 9, 1, 0, tzinfo=timezone.utc),
            ))


# ---------------------------------------------------------------------------
# Line parsing
# ---------------------------------------------------------------------------
def _make_gkg_line(
    *,
    record_id: str = "20260409120000-0",
    date_field: str = "20260409120000",
    domain: str = "tass.ru",
    url: str = "https://tass.ru/politics/123",
    themes: str = "ARMEDCONFLICT;TAX_FNCACT;TAX_FNCACT_PRESIDENT;",
    tone: str = "-3.2,1.1,4.3,5.4,12.5,0.0,150",
    extras_xml: str = "<PAGE_LINKS></PAGE_LINKS><PAGE_TITLE>Test article title</PAGE_TITLE>",
) -> str:
    """Build a synthetic GKG row with the fields we care about and blanks
    for the rest. GKG 2.0 has 27 tab-delimited columns."""
    cols = [""] * 27
    cols[0] = record_id
    cols[1] = date_field
    cols[2] = "1"
    cols[3] = domain
    cols[4] = url
    cols[7] = themes
    cols[15] = tone
    cols[26] = extras_xml
    return "\t".join(cols)


class TestParseGkgLine:
    def test_matches_registered_domain(self):
        line = _make_gkg_line(domain="tass.ru")
        row = parse_gkg_line(line, {"tass.ru"})
        assert row is not None
        assert row.domain == "tass.ru"
        assert row.raw_domain == "tass.ru"
        assert row.url == "https://tass.ru/politics/123"
        assert row.title == "Test article title"
        assert row.themes_v1 == ["ARMEDCONFLICT", "TAX_FNCACT", "TAX_FNCACT_PRESIDENT"]
        assert row.tone == pytest.approx(-3.2)
        assert row.record_id == "20260409120000-0"
        assert row.date == datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)

    def test_walks_up_to_registered_parent(self):
        line = _make_gkg_line(domain="french.xinhuanet.com")
        row = parse_gkg_line(line, {"xinhuanet.com"})
        assert row is not None
        assert row.domain == "xinhuanet.com"  # Matched parent
        assert row.raw_domain == "french.xinhuanet.com"  # Original preserved

    def test_returns_none_for_unregistered_domain(self):
        line = _make_gkg_line(domain="cnn.com")
        row = parse_gkg_line(line, {"tass.ru", "xinhuanet.com"})
        assert row is None

    def test_returns_none_for_short_line(self):
        row = parse_gkg_line("too\tfew\tcolumns", {"anything"})
        assert row is None

    def test_returns_none_for_empty_line(self):
        assert parse_gkg_line("", {"anything"}) is None

    def test_themes_are_deduplicated_and_sorted(self):
        line = _make_gkg_line(
            themes="ARMEDCONFLICT;TAX_FNCACT;ARMEDCONFLICT;TERROR;"
        )
        row = parse_gkg_line(line, {"tass.ru"})
        assert row.themes_v1 == ["ARMEDCONFLICT", "TAX_FNCACT", "TERROR"]

    def test_empty_themes_column(self):
        line = _make_gkg_line(themes="")
        row = parse_gkg_line(line, {"tass.ru"})
        assert row.themes_v1 == []

    def test_missing_tone_returns_none(self):
        line = _make_gkg_line(tone="")
        row = parse_gkg_line(line, {"tass.ru"})
        assert row.tone is None

    def test_garbled_tone_returns_none(self):
        line = _make_gkg_line(tone="not_a_number,1,2,3,4,5,6")
        row = parse_gkg_line(line, {"tass.ru"})
        assert row.tone is None

    def test_title_without_page_title_tag_is_empty(self):
        line = _make_gkg_line(extras_xml="<PAGE_LINKS>just_links</PAGE_LINKS>")
        row = parse_gkg_line(line, {"tass.ru"})
        assert row.title == ""

    def test_title_unescapes_html_entities(self):
        line = _make_gkg_line(
            extras_xml="<PAGE_TITLE>Russia &amp; Ukraine: &quot;war&quot;</PAGE_TITLE>"
        )
        row = parse_gkg_line(line, {"tass.ru"})
        assert row.title == 'Russia & Ukraine: "war"'

    def test_uppercase_domain_is_normalized(self):
        line = _make_gkg_line(domain="TASS.RU")
        row = parse_gkg_line(line, {"tass.ru"})
        assert row is not None
        assert row.domain == "tass.ru"
        assert row.raw_domain == "tass.ru"

    def test_unparseable_date_returns_none(self):
        line = _make_gkg_line(record_id="bogus", date_field="not_a_date")
        row = parse_gkg_line(line, {"tass.ru"})
        assert row is None


# ---------------------------------------------------------------------------
# File fetching (with injected fetcher so no network)
# ---------------------------------------------------------------------------
def _zip_gkg_content(lines: list[str]) -> bytes:
    """Pack a list of GKG lines into a zip file matching GDELT's format."""
    csv_text = "\n".join(lines).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("20260409120000.gkg.csv", csv_text)
    return buf.getvalue()


class TestFetchGkgFile:
    def test_parses_injected_zip_content(self):
        lines = [
            _make_gkg_line(domain="tass.ru", url="https://tass.ru/a/1"),
            _make_gkg_line(domain="cnn.com", url="https://cnn.com/x/1"),  # filtered out
            _make_gkg_line(domain="xinhuanet.com", url="https://xinhuanet.com/a/2"),
        ]
        fake_zip = _zip_gkg_content(lines)
        calls = []

        def fake_fetcher(url, timeout):
            calls.append((url, timeout))
            return fake_zip

        result = fetch_gkg_file(
            datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
            {"tass.ru", "xinhuanet.com"},
            url_fetcher=fake_fetcher,
        )
        assert not result.skipped
        assert result.total_rows_seen == 3
        assert result.matched_rows == 2
        assert len(result.rows) == 2
        assert {r.domain for r in result.rows} == {"tass.ru", "xinhuanet.com"}
        assert len(calls) == 1

    def test_handles_404_gracefully(self):
        import urllib.error

        def fake_fetcher(url, timeout):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        result = fetch_gkg_file(
            datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
            {"tass.ru"},
            url_fetcher=fake_fetcher,
            max_retries=0,
        )
        assert result.skipped
        assert result.error == "404"
        assert result.rows == []

    def test_retries_then_succeeds(self):
        lines = [_make_gkg_line(domain="tass.ru")]
        fake_zip = _zip_gkg_content(lines)
        attempts = [0]

        def flaky_fetcher(url, timeout):
            attempts[0] += 1
            if attempts[0] < 3:
                raise ConnectionError("flaky network")
            return fake_zip

        result = fetch_gkg_file(
            datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
            {"tass.ru"},
            url_fetcher=flaky_fetcher,
            max_retries=3,
            backoff_base=1.0,  # keep the test fast
        )
        assert not result.skipped
        assert result.matched_rows == 1
        assert result.retries == 2  # two failures, then success

    def test_gives_up_after_max_retries(self):
        def always_fail(url, timeout):
            raise ConnectionError("permanent outage")

        result = fetch_gkg_file(
            datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
            {"tass.ru"},
            url_fetcher=always_fail,
            max_retries=2,
            backoff_base=1.0,
        )
        assert result.skipped
        assert "permanent outage" in result.error
        assert result.retries == 2

    def test_handles_bad_zip(self):
        def bad_zip_fetcher(url, timeout):
            return b"not a real zip file"

        result = fetch_gkg_file(
            datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
            {"tass.ru"},
            url_fetcher=bad_zip_fetcher,
            max_retries=0,
        )
        assert result.skipped
        assert "bad zip" in result.error
