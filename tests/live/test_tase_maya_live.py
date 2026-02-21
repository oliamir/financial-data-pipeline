"""Live tests for TASE Maya headless scraper/downloader."""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from playwright.async_api import async_playwright

from src.tase_maya.downloader import TaseMayaDownloader

RUN_LIVE = os.getenv("RUN_LIVE_TASE_TESTS") == "1"

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not RUN_LIVE,
        reason="Set RUN_LIVE_TASE_TESTS=1 to run live TASE scraping tests",
    ),
]


@pytest.mark.asyncio
async def test_live_apollo_listing_returns_events(tmp_path):
    downloader = TaseMayaDownloader(output_root=tmp_path, headless=True, max_pages=3)
    from_date = date.today() - timedelta(days=365)
    to_date = date.today()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(viewport={"width": 1600, "height": 1100})
        page = await context.new_page()

        events = await downloader._list_company_events(
            page=page,
            company_id="1074",
            company_name="Apollo Power",
            from_date=from_date,
            to_date=to_date,
            events_family_ids=(200, 100),
        )

        await context.close()
        await browser.close()

    assert events
    assert all(event.report_id > 0 for event in events)
    assert any(event.detail_url.startswith("https://maya.tase.co.il/") for event in events)


@pytest.mark.asyncio
async def test_live_event_assets_cover_pdf_and_text_paths(tmp_path):
    downloader = TaseMayaDownloader(output_root=tmp_path, headless=True, max_pages=2)
    from_date = date.today() - timedelta(days=365)
    to_date = date.today()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(viewport={"width": 1600, "height": 1100})
        list_page = await context.new_page()
        detail_page = await context.new_page()

        events = await downloader._list_company_events(
            page=list_page,
            company_id="1074",
            company_name="Apollo Power",
            from_date=from_date,
            to_date=to_date,
            events_family_ids=(200, 100),
        )
        assert events

        pdf_event_found = False
        text_event_found = False

        for event in events[:8]:
            assets = await downloader._inspect_event_assets(page=detail_page, event=event)
            pdf_count = 0
            for index, url in enumerate(assets.pdf_urls[:6], start=1):
                target = tmp_path / f"{event.report_id}_{index}.pdf"
                if downloader._download_pdf(url, target):
                    pdf_count += 1

            if pdf_count > 0:
                pdf_event_found = True
            else:
                text = downloader._fetch_event_text(assets.text_url or "")
                if text and len(text) > 80:
                    text_event_found = True

            if pdf_event_found and text_event_found:
                break

        await context.close()
        await browser.close()

    assert pdf_event_found
    assert text_event_found

