"""Headless TASE Maya downloader for event PDFs and text disclosures."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from ..models.company import Company
from ..utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_PRIORITY_SLUGS = ["apollo", "brainsway", "sofwave", "azrieli", "ludan"]
MAYA_BASE_URL = "https://maya.tase.co.il"
MAYA_FILES_BASE_URL = "https://mayafiles.tase.co.il"
DEFAULT_EVENTS_FAMILY_IDS = (200, 100)


@dataclass(slots=True)
class ScrapedEvent:
    """Single event discovered from Maya company reports feed."""

    report_id: int
    title: str
    publish_datetime: Optional[datetime]
    raw_date_text: str
    detail_url: str
    company_id: str
    company_name: str


@dataclass(slots=True)
class EventAssets:
    """Assets discovered on a single event detail page."""

    report_id: int
    detail_url: str
    pdf_urls: list[str] = field(default_factory=list)
    text_url: Optional[str] = None
    inspected_urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DownloadedEventArtifact:
    """Paths written to disk for one event."""

    report_id: int
    metadata_path: Path
    pdf_paths: list[Path] = field(default_factory=list)
    text_path: Optional[Path] = None


@dataclass(slots=True)
class CompanyRunSummary:
    """Run summary for one company."""

    company_slug: str
    company_name: str
    company_id: str
    from_date: date
    to_date: date
    events_found: int
    events_with_pdf: int
    pdf_files_downloaded: int
    text_fallback_events: int
    output_dir: Path
    status: str
    error: Optional[str] = None


def build_company_reports_url(
    *,
    company_id: str,
    from_date: date,
    to_date: date,
    page_number: int = 1,
    events_family_ids: tuple[int, ...] = DEFAULT_EVENTS_FAMILY_IDS,
) -> str:
    """Build Maya company reports URL with explicit date window."""
    family_ids = ",".join(str(value) for value in events_family_ids)
    return (
        f"{MAYA_BASE_URL}/he/reports/companies?"
        f"fromDate={from_date.isoformat()}&"
        f"toDate={to_date.isoformat()}&"
        "isPriority=false&"
        "isTradeHalt=false&"
        "by=company&"
        f"companyId={company_id}&"
        f"eventsFamilyIds={family_ids}&"
        f"pageNumber={page_number}"
    )


def parse_maya_datetime(value: str) -> Optional[datetime]:
    """Parse date/time string from Maya list rows."""
    text = (value or "").strip()
    if not text:
        return None

    # Common formats: DD/MM/YYYY or DD/MM/YYYY HH:MM(:SS)
    match = re.search(
        r"(?P<d>\d{1,2})[./-](?P<m>\d{1,2})[./-](?P<y>\d{2,4})(?:\s+(?P<h>\d{1,2}):(?P<mi>\d{2})(?::(?P<s>\d{2}))?)?",
        text,
    )
    if not match:
        return None

    year = int(match.group("y"))
    if year < 100:
        year += 2000
    month = int(match.group("m"))
    day = int(match.group("d"))
    hour = int(match.group("h")) if match.group("h") else 0
    minute = int(match.group("mi")) if match.group("mi") else 0
    second = int(match.group("s")) if match.group("s") else 0

    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def quarter_label(dt: date) -> str:
    """Return calendar quarter label."""
    quarter = ((dt.month - 1) // 3) + 1
    return f"{dt.year}-Q{quarter}"


def _legacy_bucket(report_id: int) -> tuple[int, int]:
    start = ((report_id - 1) // 1000) * 1000 + 1
    end = start + 999
    return start, end


def build_legacy_rhtm_url(report_id: int) -> str:
    """Build legacy mayafiles HTML URL by report ID."""
    start, end = _legacy_bucket(report_id)
    return f"{MAYA_FILES_BASE_URL}/rhtm/{start}-{end}/H{report_id}.htm"


def build_pdf_guess_urls(report_id: int, max_versions: int = 6) -> list[str]:
    """Build guessed mayafiles PDF URLs by report ID (P<id>-NN.pdf)."""
    start, end = _legacy_bucket(report_id)
    urls: list[str] = []
    for version in range(max_versions):
        urls.append(f"{MAYA_FILES_BASE_URL}/rpdf/{start}-{end}/P{report_id}-{version:02d}.pdf")
    return urls


def _slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "company"


def _normalize_url(url: str) -> Optional[str]:
    value = (url or "").strip()
    if not value:
        return None

    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/rpdf/") or value.startswith("/rhtm/"):
        return f"{MAYA_FILES_BASE_URL}{value}"
    if value.startswith("rpdf/") or value.startswith("rhtm/"):
        return f"{MAYA_FILES_BASE_URL}/{value}"
    if value.startswith("/"):
        return f"{MAYA_BASE_URL}{value}"
    return f"{MAYA_BASE_URL}/{value}"


def _extract_report_id_from_href(href: str) -> Optional[int]:
    match = re.search(r"/reports/details/(\d+)", href)
    if not match:
        match = re.search(r"/companies/(\d+)", href)
    if not match:
        match = re.search(r"/(\d+)(?:/|$)", href)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _is_pdf_url(value: str) -> bool:
    lower = value.lower()
    return "/rpdf/" in lower or lower.endswith(".pdf") or ".pdf?" in lower


def _is_rhtm_url(value: str) -> bool:
    lower = value.lower()
    return "/rhtm/" in lower and ".htm" in lower


class TaseMayaDownloader:
    """Headless Maya downloader that opens event pages and downloads artifacts."""

    def __init__(
        self,
        *,
        output_root: str | Path = "data/companies",
        state_path: str | Path | None = None,
        headless: bool = True,
        max_pages: int = 120,
        navigation_timeout_ms: int = 30_000,
        pause_after_nav_sec: float = 1.5,
        request_timeout_sec: int = 60,
    ) -> None:
        self.output_root = Path(output_root).expanduser().resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.state_path = (
            Path(state_path).expanduser().resolve()
            if state_path
            else self.output_root / "state.json"
        )
        self.headless = headless
        self.max_pages = max_pages
        self.navigation_timeout_ms = navigation_timeout_ms
        self.pause_after_nav_sec = pause_after_nav_sec
        self.request_timeout_sec = request_timeout_sec

        self._http = requests.Session()
        self._http.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

    async def run(
        self,
        *,
        companies: list[Company],
        years: int,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        incremental: bool = True,
        events_family_ids: tuple[int, ...] = DEFAULT_EVENTS_FAMILY_IDS,
    ) -> list[CompanyRunSummary]:
        """Run scraping/downloading for provided companies."""
        if years < 1 or years > 10:
            raise ValueError("years must be in range 1..10")

        run_started_at = datetime.now(timezone.utc)
        run_id = run_started_at.strftime("%Y%m%dT%H%M%SZ")
        range_end = to_date or date.today()
        min_backfill = range_end - timedelta(days=365 * years)

        state = self._load_state()
        summaries: list[CompanyRunSummary] = []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = await browser.new_context(
                user_agent=self._http.headers["User-Agent"],
                viewport={"width": 1600, "height": 1100},
                locale="he-IL",
            )
            list_page = await context.new_page()
            detail_page = await context.new_page()

            for company in companies:
                if not company.tase_company_id:
                    logger.warning("Skipping %s: missing tase_company_id", company.slug)
                    continue

                range_start = self._resolve_from_date(
                    slug=company.slug,
                    explicit_from=from_date,
                    fallback_from=min_backfill,
                    to_date=range_end,
                    incremental=incremental,
                    state=state,
                )
                if range_start > range_end:
                    logger.info(
                        "Skipping %s: from_date %s is after to_date %s",
                        company.slug,
                        range_start,
                        range_end,
                    )
                    continue

                logger.info(
                    "Scraping %s (%s): %s -> %s",
                    company.slug,
                    company.tase_company_id,
                    range_start,
                    range_end,
                )

                try:
                    events = await self._list_company_events(
                        page=list_page,
                        company_id=company.tase_company_id,
                        company_name=company.name,
                        from_date=range_start,
                        to_date=range_end,
                        events_family_ids=events_family_ids,
                    )
                    artifacts = await self._download_company_events(
                        page=detail_page,
                        company=company,
                        events=events,
                        run_id=run_id,
                        run_started_at=run_started_at,
                    )
                    summary = self._build_company_summary(
                        company=company,
                        from_date=range_start,
                        to_date=range_end,
                        artifacts=artifacts,
                    )
                    self._mark_company_success(
                        state=state,
                        company=company,
                        summary=summary,
                        run_started_at=run_started_at,
                    )
                except Exception as exc:
                    logger.exception("Company %s failed: %s", company.slug, exc)
                    summary = CompanyRunSummary(
                        company_slug=company.slug,
                        company_name=company.name,
                        company_id=company.tase_company_id,
                        from_date=range_start,
                        to_date=range_end,
                        events_found=0,
                        events_with_pdf=0,
                        pdf_files_downloaded=0,
                        text_fallback_events=0,
                        output_dir=self._company_output_dir(company),
                        status="failed",
                        error=str(exc),
                    )

                summaries.append(summary)

            await context.close()
            await browser.close()

        self._save_state(state)
        return summaries

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"companies": {}}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {"companies": {}}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def _resolve_from_date(
        self,
        *,
        slug: str,
        explicit_from: Optional[date],
        fallback_from: date,
        to_date: date,
        incremental: bool,
        state: dict[str, Any],
    ) -> date:
        if explicit_from:
            return explicit_from
        if not incremental:
            return fallback_from

        companies_state = state.get("companies", {})
        company_state = companies_state.get(slug, {})
        last_to_date_raw = company_state.get("last_to_date")
        if not last_to_date_raw:
            return fallback_from

        try:
            last_to_date = date.fromisoformat(last_to_date_raw)
        except ValueError:
            return fallback_from

        if last_to_date > to_date:
            return fallback_from
        return last_to_date

    async def _list_company_events(
        self,
        *,
        page: Any,
        company_id: str,
        company_name: str,
        from_date: date,
        to_date: date,
        events_family_ids: tuple[int, ...],
    ) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        seen_report_ids: set[int] = set()

        for page_number in range(1, self.max_pages + 1):
            url = build_company_reports_url(
                company_id=company_id,
                from_date=from_date,
                to_date=to_date,
                page_number=page_number,
                events_family_ids=events_family_ids,
            )

            try:
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.navigation_timeout_ms,
                )
            except PlaywrightTimeout:
                logger.warning("Timeout loading %s page %s", company_id, page_number)
                break

            await asyncio.sleep(self.pause_after_nav_sec)
            rows = await page.evaluate(
                """
                () => {
                  const nodes = Array.from(document.querySelectorAll('.feed-item-report'));
                  return nodes.map((node) => {
                    const link = node.querySelector('a.feed-text-link');
                    const dateNode = node.querySelector('.feed-date');
                    return {
                      href: link ? link.getAttribute('href') : null,
                      title: link ? (link.textContent || '').trim() : '',
                      dateText: dateNode ? (dateNode.textContent || '').trim() : '',
                    };
                  });
                }
                """
            )

            if not rows:
                break

            new_rows = 0
            for row in rows:
                href = _normalize_url(str(row.get("href") or ""))
                if not href:
                    continue
                report_id = _extract_report_id_from_href(href)
                if not report_id or report_id in seen_report_ids:
                    continue

                seen_report_ids.add(report_id)
                publish_dt = parse_maya_datetime(str(row.get("dateText") or ""))
                events.append(
                    ScrapedEvent(
                        report_id=report_id,
                        title=str(row.get("title") or "").strip(),
                        publish_datetime=publish_dt,
                        raw_date_text=str(row.get("dateText") or "").strip(),
                        detail_url=href,
                        company_id=company_id,
                        company_name=company_name,
                    )
                )
                new_rows += 1

            if new_rows == 0:
                break

        return events

    async def _download_company_events(
        self,
        *,
        page: Any,
        company: Company,
        events: list[ScrapedEvent],
        run_id: str,
        run_started_at: datetime,
    ) -> list[DownloadedEventArtifact]:
        artifacts: list[DownloadedEventArtifact] = []

        for event in events:
            assets = await self._inspect_event_assets(page=page, event=event)
            artifacts.append(
                self._persist_event(
                    company=company,
                    event=event,
                    assets=assets,
                    run_id=run_id,
                    run_started_at=run_started_at,
                )
            )

        return artifacts

    async def _inspect_event_assets(self, *, page: Any, event: ScrapedEvent) -> EventAssets:
        observed_urls: set[str] = set()

        def _capture_response(response: Any) -> None:
            url = response.url
            if "mayafiles.tase.co.il" in url or "/rpdf/" in url or "/rhtm/" in url:
                observed_urls.add(url)

        page.on("response", _capture_response)
        try:
            await page.goto(
                event.detail_url,
                wait_until="domcontentloaded",
                timeout=self.navigation_timeout_ms,
            )
            await asyncio.sleep(self.pause_after_nav_sec)

            dom_urls = await page.evaluate(
                """
                () => {
                  const values = [];
                  for (const a of Array.from(document.querySelectorAll('a[href]'))) {
                    values.push(a.getAttribute('href'));
                  }
                  for (const f of Array.from(document.querySelectorAll('iframe[src], embed[src], source[src]'))) {
                    values.push(f.getAttribute('src'));
                  }
                  for (const o of Array.from(document.querySelectorAll('object[data]'))) {
                    values.push(o.getAttribute('data'));
                  }
                  return values.filter(Boolean);
                }
                """
            )
            html = await page.content()
        finally:
            try:
                page.remove_listener("response", _capture_response)
            except Exception:
                pass

        regex_urls: set[str] = set()
        for pattern in (
            r"(?:https?://[^\s\"'>]+/rpdf/[^\s\"'>]+?\.pdf(?:\?[^\s\"'>]+)?)",
            r"(?:https?://[^\s\"'>]+/rhtm/[^\s\"'>]+?\.htm(?:\?[^\s\"'>]+)?)",
            r"(?:/rpdf/[^\s\"'>]+?\.pdf(?:\?[^\s\"'>]+)?)",
            r"(?:/rhtm/[^\s\"'>]+?\.htm(?:\?[^\s\"'>]+)?)",
            r"(?:rpdf/[^\s\"'>]+?\.pdf(?:\?[^\s\"'>]+)?)",
            r"(?:rhtm/[^\s\"'>]+?\.htm(?:\?[^\s\"'>]+)?)",
        ):
            regex_urls.update(re.findall(pattern, html, flags=re.IGNORECASE))

        candidate_urls: list[str] = []
        for raw_url in list(dom_urls or []) + list(observed_urls) + list(regex_urls):
            normalized = _normalize_url(str(raw_url))
            if normalized:
                candidate_urls.append(normalized)

        pdf_urls: list[str] = []
        text_url: Optional[str] = None
        seen: set[str] = set()

        for candidate in candidate_urls:
            if candidate in seen:
                continue
            seen.add(candidate)
            if _is_pdf_url(candidate):
                pdf_urls.append(candidate)
            if text_url is None and _is_rhtm_url(candidate):
                text_url = candidate

        # Always add deterministic guesses to catch hidden additional attachments.
        for guess in build_pdf_guess_urls(event.report_id):
            if guess not in seen:
                pdf_urls.append(guess)
                seen.add(guess)

        if text_url is None:
            text_url = build_legacy_rhtm_url(event.report_id)

        return EventAssets(
            report_id=event.report_id,
            detail_url=event.detail_url,
            pdf_urls=pdf_urls,
            text_url=text_url,
            inspected_urls=sorted(seen),
        )

    def _persist_event(
        self,
        *,
        company: Company,
        event: ScrapedEvent,
        assets: EventAssets,
        run_id: str,
        run_started_at: datetime,
    ) -> DownloadedEventArtifact:
        company_dir = self._company_output_dir(company)
        publish_date = event.publish_datetime.date() if event.publish_datetime else run_started_at.date()
        quarter_dir = company_dir / quarter_label(publish_date)
        quarter_dir.mkdir(parents=True, exist_ok=True)

        date_part = publish_date.isoformat()
        event_prefix = f"{date_part}__{event.report_id}"
        metadata_path = quarter_dir / f"{event_prefix}__meta__{run_id}.json"

        downloaded_pdf_paths: list[Path] = []
        for index, url in enumerate(assets.pdf_urls, start=1):
            target_path = quarter_dir / f"{event_prefix}__pdf{index:02d}__{run_id}.pdf"
            if self._download_pdf(url, target_path):
                downloaded_pdf_paths.append(target_path)

        text_path: Optional[Path] = None
        text_content: Optional[str] = None
        if not downloaded_pdf_paths:
            text_content = self._fetch_event_text(assets.text_url or build_legacy_rhtm_url(event.report_id))
            if text_content:
                text_path = quarter_dir / f"{event_prefix}__body__{run_id}.txt"
                text_path.write_text(text_content, encoding="utf-8")

        metadata = {
            "event_id": event.report_id,
            "company_id": company.tase_company_id,
            "company_slug": company.slug,
            "company_name": company.name,
            "title": event.title,
            "published_at": event.publish_datetime.isoformat() if event.publish_datetime else None,
            "raw_date_text": event.raw_date_text,
            "event_family_ids": list(DEFAULT_EVENTS_FAMILY_IDS),
            "report_url": event.detail_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "pdf_urls_discovered": assets.pdf_urls,
            "pdf_files_downloaded": [str(path) for path in downloaded_pdf_paths],
            "text_url": assets.text_url,
            "text_file_downloaded": str(text_path) if text_path else None,
            "inspected_urls": assets.inspected_urls,
        }
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return DownloadedEventArtifact(
            report_id=event.report_id,
            metadata_path=metadata_path,
            pdf_paths=downloaded_pdf_paths,
            text_path=text_path,
        )

    def _company_output_dir(self, company: Company) -> Path:
        name = _slugify(company.slug or company.name)
        return self.output_root / name

    def _download_pdf(self, url: str, target_path: Path) -> bool:
        try:
            response = self._http.get(url, timeout=self.request_timeout_sec, allow_redirects=True)
        except requests.RequestException:
            return False

        if response.status_code != 200:
            return False

        content = response.content
        if not content.startswith(b"%PDF"):
            return False

        target_path.write_bytes(content)
        return True

    def _fetch_event_text(self, url: str) -> Optional[str]:
        try:
            response = self._http.get(url, timeout=self.request_timeout_sec, allow_redirects=True)
        except requests.RequestException:
            return None

        if response.status_code != 200 or not response.content:
            return None

        html = self._decode_html(response.content, response.encoding)
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text or None

    def _decode_html(self, raw: bytes, detected_encoding: Optional[str]) -> str:
        candidates = [
            detected_encoding,
            "windows-1255",
            "cp1255",
            "utf-8",
            "latin1",
        ]
        for encoding in candidates:
            if not encoding:
                continue
            try:
                return raw.decode(encoding, errors="ignore")
            except Exception:
                continue
        return raw.decode("utf-8", errors="ignore")

    def _build_company_summary(
        self,
        *,
        company: Company,
        from_date: date,
        to_date: date,
        artifacts: list[DownloadedEventArtifact],
    ) -> CompanyRunSummary:
        pdf_events = sum(1 for artifact in artifacts if artifact.pdf_paths)
        pdf_files = sum(len(artifact.pdf_paths) for artifact in artifacts)
        text_events = sum(1 for artifact in artifacts if artifact.text_path is not None)

        return CompanyRunSummary(
            company_slug=company.slug,
            company_name=company.name,
            company_id=company.tase_company_id or "",
            from_date=from_date,
            to_date=to_date,
            events_found=len(artifacts),
            events_with_pdf=pdf_events,
            pdf_files_downloaded=pdf_files,
            text_fallback_events=text_events,
            output_dir=self._company_output_dir(company),
            status="success",
        )

    def _mark_company_success(
        self,
        *,
        state: dict[str, Any],
        company: Company,
        summary: CompanyRunSummary,
        run_started_at: datetime,
    ) -> None:
        companies_state = state.setdefault("companies", {})
        companies_state[company.slug] = {
            "company_id": company.tase_company_id,
            "last_successful_run": run_started_at.isoformat(),
            "last_from_date": summary.from_date.isoformat(),
            "last_to_date": summary.to_date.isoformat(),
            "last_events_found": summary.events_found,
            "last_pdf_files_downloaded": summary.pdf_files_downloaded,
            "last_text_fallback_events": summary.text_fallback_events,
        }
