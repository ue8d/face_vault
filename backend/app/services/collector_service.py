"""自動画像収集。登録した収集元(ドメイン/URL)を巡回し画像を集めて取込む。

外部依存なし: HTML解析は標準 html.parser、robots は urllib.robotparser。
収集画像は PhotoService.save_from_url(auto_enroll=False) で保存 → 顔は未照合の
まま確認キューへ出る（新規人物の自動作成はしない）。同一環境で同一URLは
collected_urls で重複排除する。
"""
from __future__ import annotations

import logging
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.collect_source import DOMAIN, PAGE, SHALLOW, CollectSource
from app.models.collected_url import CollectedUrl
from app.services.photo_service import PhotoService

logger = logging.getLogger(__name__)

_USER_AGENT = "face_vault/1.0"
_PAGE_TIMEOUT = 20
_MAX_PAGE_BYTES = 5 * 1024 * 1024  # HTMLは5MBまで
_PAGE_DELAY_SEC = 1.0  # 同一ドメイン連続取得の間隔（レート制限）
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")


@dataclass
class CollectResult:
    found_urls: int = 0
    new_urls: int = 0
    saved: int = 0
    skipped_duplicate: int = 0
    failed: int = 0
    pages_scanned: int = 0
    error: str | None = None


class _LinkImageParser(HTMLParser):
    """HTMLから <img src>/<img srcset> と <a href> を収集する。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.img_urls: list[str] = []
        self.link_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "img":
            src = a.get("src")
            if src:
                self.img_urls.append(src)
            srcset = a.get("srcset")
            if srcset:
                # "url1 1x, url2 2x" → 各URL
                for part in srcset.split(","):
                    cand = part.strip().split(" ")[0].strip()
                    if cand:
                        self.img_urls.append(cand)
        elif tag in ("a", "link"):
            href = a.get("href")
            if href:
                self.link_urls.append(href)


def _looks_like_image(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return path.endswith(_IMAGE_EXTS)


def _same_domain(a: str, b: str) -> bool:
    return urlsplit(a).netloc.lower() == urlsplit(b).netloc.lower()


def extract_urls(html: str, base_url: str) -> tuple[list[str], list[str]]:
    """HTML から (画像URL絶対化, ページリンクURL絶対化) を返す。重複は順序維持で排除。"""
    parser = _LinkImageParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - 壊れたHTMLでも拾える分だけ
        logger.debug("html parse partial failure for %s", base_url, exc_info=True)
    imgs = _dedup(urljoin(base_url, u) for u in parser.img_urls)
    links = _dedup(urljoin(base_url, u) for u in parser.link_urls)
    return imgs, links


def _dedup(urls) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen and u.startswith(("http://", "https://")):
            seen.add(u)
            out.append(u)
    return out


class CollectorService:
    def __init__(self, db: Session, env_id: int | None = None) -> None:
        self.db = db
        self.env_id = env_id

    # --- HTML取得 ---
    def _fetch_html(self, url: str) -> str | None:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=_PAGE_TIMEOUT) as resp:
                ctype = resp.headers.get_content_type() if resp.headers.get("Content-Type") else ""
                if ctype and not ctype.startswith(("text/html", "application/xhtml")):
                    return None
                raw = resp.read(_MAX_PAGE_BYTES)
                charset = resp.headers.get_content_charset() or "utf-8"
        except Exception:  # noqa: BLE001 - ページ取得失敗は当該ページのみスキップ
            logger.info("page fetch failed: %s", url, exc_info=True)
            return None
        try:
            return raw.decode(charset, errors="replace")
        except (LookupError, TypeError):
            return raw.decode("utf-8", errors="replace")

    def _robot_checker(self, source: CollectSource):
        """respect_robots 時の許可判定関数を返す。未取得・無効なら常に許可。"""
        if not source.respect_robots:
            return lambda url: True
        parts = urlsplit(source.start_url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
        except Exception:  # noqa: BLE001 - robots取得不可なら制限せず許可
            return lambda url: True
        return lambda url: rp.can_fetch(_USER_AGENT, url)

    # --- 画像URL収集（crawl_mode 別） ---
    def collect_urls(self, source: CollectSource) -> tuple[list[str], int]:
        """画像URL候補列と走査ページ数を返す。"""
        can_fetch = self._robot_checker(source)
        mode = source.crawl_mode

        if mode == PAGE:
            return self._collect_page(source, can_fetch)
        if mode == SHALLOW:
            return self._collect_crawl(source, can_fetch, max_depth=1)
        if mode == DOMAIN:
            return self._collect_crawl(source, can_fetch, max_depth=10)
        return [], 0

    def _collect_page(self, source: CollectSource, can_fetch) -> tuple[list[str], int]:
        if not can_fetch(source.start_url):
            return [], 0
        html = self._fetch_html(source.start_url)
        if html is None:
            return [], 1
        imgs, _ = extract_urls(html, source.start_url)
        imgs = [u for u in imgs if _looks_like_image(u)]
        return imgs[: source.max_images], 1

    def _collect_crawl(
        self, source: CollectSource, can_fetch, *, max_depth: int
    ) -> tuple[list[str], int]:
        """BFS でページを辿りつつ画像URLを集約。max_pages/max_images/深さで打ち切り。"""
        start = source.start_url
        seen_pages: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        images: list[str] = []
        seen_images: set[str] = set()
        pages_scanned = 0

        while queue and pages_scanned < source.max_pages and len(images) < source.max_images:
            page_url, depth = queue.popleft()
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            if not can_fetch(page_url):
                continue
            html = self._fetch_html(page_url)
            pages_scanned += 1
            time.sleep(_PAGE_DELAY_SEC)
            if html is None:
                continue
            imgs, links = extract_urls(html, page_url)
            for u in imgs:
                if _looks_like_image(u) and u not in seen_images:
                    if source.same_domain_only and not _same_domain(u, start):
                        continue
                    seen_images.add(u)
                    images.append(u)
                    if len(images) >= source.max_images:
                        break
            if depth < max_depth:
                for link in links:
                    if link in seen_pages:
                        continue
                    if source.same_domain_only and not _same_domain(link, start):
                        continue
                    queue.append((link, depth + 1))
        return images[: source.max_images], pages_scanned

    # --- 実行 ---
    def run(self, source: CollectSource) -> CollectResult:
        """収集元を1回巡回し、新規画像を確認キュー行きで保存する。"""
        result = CollectResult()
        source.last_status = "running"
        self.db.commit()
        try:
            urls, pages = self.collect_urls(source)
            result.found_urls = len(urls)
            result.pages_scanned = pages

            photos = PhotoService(self.db, self.env_id)
            for url in urls:
                if result.saved >= source.max_images:
                    break
                if self._already_collected(url):
                    result.skipped_duplicate += 1
                    continue
                result.new_urls += 1
                try:
                    photo = photos.save_from_url(
                        url=url,
                        memo=f"自動収集: {source.name}",
                        include_filename_in_memo=True,
                        auto_enroll=False,  # 常に確認キュー行き
                    )
                    self._record(source, url, photo.id)
                    result.saved += 1
                except Exception as e:  # noqa: BLE001 - 1件失敗で全体は止めない
                    result.failed += 1
                    logger.info("collect save failed %s: %s", url, e)
                    self.db.rollback()

            source.last_status = "ok"
            source.last_error = None
        except Exception as e:  # noqa: BLE001 - 収集全体の失敗
            self.db.rollback()
            source.last_status = "error"
            source.last_error = str(e)[:500]
            result.error = str(e)
            logger.warning("collect run failed for source %s", source.id, exc_info=True)

        now = datetime.now(timezone.utc)
        source.last_run_at = now
        source.next_run_at = (
            now + timedelta(minutes=source.interval_minutes)
            if source.interval_minutes and source.interval_minutes > 0
            else None
        )
        self.db.commit()
        return result

    def _already_collected(self, url: str) -> bool:
        stmt = select(CollectedUrl.id).where(CollectedUrl.url == url)
        if self.env_id is not None:
            stmt = stmt.where(CollectedUrl.environment_id == self.env_id)
        return self.db.scalar(stmt) is not None

    def _record(self, source: CollectSource, url: str, photo_id: int | None) -> None:
        row = CollectedUrl(source_id=source.id, url=url, photo_id=photo_id)
        if self.env_id is not None:
            row.environment_id = self.env_id
        self.db.add(row)
        self.db.flush()
