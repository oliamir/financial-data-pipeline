"""Unit tests for headless TASE Maya downloader helpers."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from src.models.company import Company
from src.tase_maya.downloader import (
    EventAssets,
    ScrapedEvent,
    TaseMayaDownloader,
    build_company_reports_url,
    build_legacy_rhtm_url,
    build_pdf_guess_urls,
    parse_maya_datetime,
    quarter_label,
)


def test_build_company_reports_url_contains_expected_filters() -> None:
    url = build_company_reports_url(
        company_id="1074",
        from_date=date(2025, 2, 21),
        to_date=date(2026, 2, 21),
        page_number=3,
        events_family_ids=(200, 100),
    )
    assert "companyId=1074" in url
    assert "fromDate=2025-02-21" in url
    assert "toDate=2026-02-21" in url
    assert "eventsFamilyIds=200,100" in url
    assert "pageNumber=3" in url


def test_parse_maya_datetime_supports_date_and_time() -> None:
    parsed = parse_maya_datetime("11/02/2026 22:38")
    assert parsed == datetime(2026, 2, 11, 22, 38)


def test_parse_maya_datetime_returns_none_for_invalid() -> None:
    assert parse_maya_datetime("not a date") is None


def test_quarter_label() -> None:
    assert quarter_label(date(2026, 1, 1)) == "2026-Q1"
    assert quarter_label(date(2026, 12, 31)) == "2026-Q4"


def test_build_legacy_urls_for_report_id() -> None:
    report_id = 1717373
    assert build_legacy_rhtm_url(report_id).endswith("/rhtm/1717001-1718000/H1717373.htm")

    pdf_urls = build_pdf_guess_urls(report_id, max_versions=3)
    assert len(pdf_urls) == 3
    assert pdf_urls[0].endswith("/rpdf/1717001-1718000/P1717373-00.pdf")
    assert pdf_urls[2].endswith("/rpdf/1717001-1718000/P1717373-02.pdf")


def test_resolve_from_date_prefers_incremental_state(tmp_path: Path) -> None:
    downloader = TaseMayaDownloader(output_root=tmp_path)
    state = {"companies": {"apollo": {"last_to_date": "2026-01-15"}}}

    result = downloader._resolve_from_date(
        slug="apollo",
        explicit_from=None,
        fallback_from=date(2025, 2, 21),
        to_date=date(2026, 2, 21),
        incremental=True,
        state=state,
    )
    assert result == date(2026, 1, 15)


def test_persist_event_uses_text_fallback_when_no_pdf(tmp_path: Path) -> None:
    downloader = TaseMayaDownloader(output_root=tmp_path)
    downloader._fetch_event_text = lambda _: "Event body text"  # type: ignore[method-assign]

    company = Company(slug="apollo", name="Apollo Power", tase_company_id="1074")
    event = ScrapedEvent(
        report_id=1722298,
        title="Sample Event",
        publish_datetime=datetime(2026, 2, 11, 22, 38),
        raw_date_text="11/02/2026 22:38",
        detail_url="https://maya.tase.co.il/he/reports/details/1722298/2/0",
        company_id="1074",
        company_name="Apollo Power",
    )
    assets = EventAssets(
        report_id=1722298,
        detail_url=event.detail_url,
        pdf_urls=[],
        text_url="https://mayafiles.tase.co.il/rhtm/1722001-1723000/H1722298.htm",
    )

    artifact = downloader._persist_event(
        company=company,
        event=event,
        assets=assets,
        run_id="20260221T120000Z",
        run_started_at=datetime(2026, 2, 21, tzinfo=timezone.utc),
    )

    assert artifact.text_path is not None
    assert artifact.text_path.exists()
    assert artifact.text_path.read_text(encoding="utf-8") == "Event body text"
    assert artifact.pdf_paths == []
    assert artifact.metadata_path.exists()

    metadata = json.loads(artifact.metadata_path.read_text(encoding="utf-8"))
    assert metadata["event_id"] == 1722298
    assert metadata["text_file_downloaded"] == str(artifact.text_path)


def test_persist_event_downloads_all_pdf_attachments(tmp_path: Path) -> None:
    downloader = TaseMayaDownloader(output_root=tmp_path)

    def fake_download(_url: str, target_path: Path) -> bool:
        target_path.write_bytes(b"%PDF-1.4\nfake\n")
        return True

    downloader._download_pdf = fake_download  # type: ignore[method-assign]
    downloader._fetch_event_text = lambda _: (_ for _ in ()).throw(RuntimeError("should not fetch text"))  # type: ignore[method-assign]

    company = Company(slug="apollo", name="Apollo Power", tase_company_id="1074")
    event = ScrapedEvent(
        report_id=1717373,
        title="Event With PDF",
        publish_datetime=datetime(2026, 1, 15, 8, 54),
        raw_date_text="15/01/2026 08:54",
        detail_url="https://maya.tase.co.il/he/reports/details/1717373/2/0",
        company_id="1074",
        company_name="Apollo Power",
    )
    assets = EventAssets(
        report_id=1717373,
        detail_url=event.detail_url,
        pdf_urls=[
            "https://mayafiles.tase.co.il/rpdf/1717001-1718000/P1717373-00.pdf",
            "https://mayafiles.tase.co.il/rpdf/1717001-1718000/P1717373-01.pdf",
        ],
        text_url=None,
    )

    artifact = downloader._persist_event(
        company=company,
        event=event,
        assets=assets,
        run_id="20260221T120000Z",
        run_started_at=datetime(2026, 2, 21, tzinfo=timezone.utc),
    )

    assert len(artifact.pdf_paths) == 2
    assert all(path.exists() for path in artifact.pdf_paths)
    assert artifact.text_path is None

    metadata = json.loads(artifact.metadata_path.read_text(encoding="utf-8"))
    assert len(metadata["pdf_files_downloaded"]) == 2
    assert metadata["text_file_downloaded"] is None

