"""自動画像収集。URL抽出 / 重複排除 / run(確認キュー化) / 環境隔離 / due判定。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.services.collector_service import CollectorService, extract_urls


def _hdr(env_id: int) -> dict[str, str]:
    return {"X-Environment-Id": str(env_id)}


def _create_env(client: TestClient, name: str) -> dict:
    return client.post("/environments", json={"name": name}).json()


# --- 純粋関数: URL抽出 ---


def test_extract_urls_absolutizes_and_dedups() -> None:
    html = (
        '<html><body>'
        '<img src="/a.jpg">'
        '<img src="https://cdn.x/b.png">'
        '<img srcset="/c.webp 1x, /d.webp 2x">'
        '<img src="/a.jpg">'  # 重複
        '<a href="page2.html">next</a>'
        '<a href="https://other.x/p">ext</a>'
        '</body></html>'
    )
    imgs, links = extract_urls(html, "https://ex.com/dir/")
    assert "https://ex.com/a.jpg" in imgs
    assert "https://cdn.x/b.png" in imgs
    assert "https://ex.com/c.webp" in imgs
    assert "https://ex.com/d.webp" in imgs
    assert imgs.count("https://ex.com/a.jpg") == 1  # 重複排除
    assert "https://ex.com/dir/page2.html" in links
    assert "https://other.x/p" in links


# --- due_sources 純粋関数 ---


def test_due_sources_filters_correctly() -> None:
    from app.services.collect_scheduler import due_sources
    from app.models.collect_source import CollectSource

    now = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)

    disabled = CollectSource(enabled=False, interval_minutes=5, next_run_at=None)
    manual = CollectSource(enabled=True, interval_minutes=0, next_run_at=None)
    never_run = CollectSource(enabled=True, interval_minutes=5, next_run_at=None)
    due = CollectSource(
        enabled=True, interval_minutes=5, next_run_at=now - timedelta(minutes=1)
    )
    not_yet = CollectSource(
        enabled=True, interval_minutes=5, next_run_at=now + timedelta(minutes=1)
    )

    result = due_sources([disabled, manual, never_run, due, not_yet], now)
    assert never_run in result
    assert due in result
    assert disabled not in result
    assert manual not in result
    assert not_yet not in result


def test_due_sources_accepts_naive_next_run_at() -> None:
    """SQLite は next_run_at を naive で返す → aware な now と比較しても落ちない。"""
    from app.services.collect_scheduler import due_sources
    from app.models.collect_source import CollectSource

    now = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    naive_due = CollectSource(
        enabled=True, interval_minutes=5,
        next_run_at=datetime(2026, 6, 11, 11, 0),  # tzinfo無し（SQLite読み出し相当）
    )
    naive_not_yet = CollectSource(
        enabled=True, interval_minutes=5,
        next_run_at=datetime(2026, 6, 11, 13, 0),
    )

    result = due_sources([naive_due, naive_not_yet], now)
    assert naive_due in result
    assert naive_not_yet not in result


# --- API CRUD ---


def test_collect_source_crud(client: TestClient) -> None:
    env = client.get("/environments").json()[0]
    hdr = _hdr(env["id"])

    res = client.post(
        "/collect/sources",
        json={"name": "テスト元", "start_url": "https://example.com/g", "crawl_mode": "page"},
        headers=hdr,
    )
    assert res.status_code == 201, res.text
    src = res.json()
    assert src["name"] == "テスト元"
    assert src["interval_minutes"] == 0

    # 不正URL → 422
    bad = client.post(
        "/collect/sources",
        json={"name": "x", "start_url": "ftp://no"},
        headers=hdr,
    )
    assert bad.status_code == 422

    # 不正 crawl_mode → 422
    bad_mode = client.post(
        "/collect/sources",
        json={"name": "x", "start_url": "https://e.com", "crawl_mode": "deep"},
        headers=hdr,
    )
    assert bad_mode.status_code == 422

    # patch
    upd = client.patch(
        f"/collect/sources/{src['id']}",
        json={"interval_minutes": 1, "enabled": False},
        headers=hdr,
    )
    assert upd.status_code == 200
    assert upd.json()["interval_minutes"] == 1
    assert upd.json()["enabled"] is False

    # delete
    assert client.delete(f"/collect/sources/{src['id']}", headers=hdr).status_code == 204
    assert client.get("/collect/sources", headers=hdr).json() == []


def test_collect_source_isolated_between_environments(client: TestClient) -> None:
    env_a = client.get("/environments").json()[0]
    env_b = _create_env(client, "B")
    client.post(
        "/collect/sources",
        json={"name": "A元", "start_url": "https://a.com"},
        headers=_hdr(env_a["id"]),
    )
    assert client.get("/collect/sources", headers=_hdr(env_b["id"])).json() == []
    # B から A のソースID直アクセス不可
    a_src = client.get("/collect/sources", headers=_hdr(env_a["id"])).json()[0]
    assert (
        client.delete(f"/collect/sources/{a_src['id']}", headers=_hdr(env_b["id"])).status_code
        == 404
    )


# --- run: 確認キュー化 + 重複排除（save_from_url をモンキーパッチしてDL回避） ---


def test_run_saves_to_review_queue_and_dedups(client: TestClient, monkeypatch) -> None:
    import numpy as np

    from app.db.base import SessionLocal
    from app.face.detector import DetectedFace
    import app.services.collector_service as cs
    from app.models.collect_source import CollectSource
    from app.models.collected_url import CollectedUrl
    from app.models.photo import Photo
    from app.models.photo_person import PhotoPerson
    from app.services.photo_service import PhotoService

    env = client.get("/environments").json()[0]
    env_id = env["id"]

    # collect_urls はネットワークを使うので固定URL列を返すようパッチ
    urls = ["https://ex.com/a.jpg", "https://ex.com/b.jpg"]
    monkeypatch.setattr(
        CollectorService, "collect_urls", lambda self, source: (list(urls), 1)
    )

    # save_from_url: 実DLせず Photo を作り、顔1つを未照合(person_id=None)で登録
    def fake_save_from_url(self, *, url, memo=None, include_filename_in_memo=False,
                           auto_enroll=None, **kw):
        assert auto_enroll is False  # 収集は常に確認キュー行き
        photo = self.store_image(content=b"x", filename="c.jpg", memo=memo)
        link = PhotoPerson(photo_id=photo.id, person_id=None, bbox="0,0,10,10")
        self.db.add(link)
        self.db.commit()
        return photo

    monkeypatch.setattr(PhotoService, "save_from_url", fake_save_from_url)

    db = SessionLocal()
    try:
        src = CollectSource(
            environment_id=env_id, name="t", start_url="https://ex.com", crawl_mode="page"
        )
        db.add(src)
        db.commit()
        db.refresh(src)

        result = CollectorService(db, env_id).run(src)
        assert result.found_urls == 2
        assert result.saved == 2
        assert result.skipped_duplicate == 0
        assert src.last_status == "ok"

        # collected_urls に記録され、写真は未照合顔を持つ（確認キュー対象）
        assert db.query(CollectedUrl).filter(CollectedUrl.environment_id == env_id).count() == 2
        unassigned = db.query(PhotoPerson).filter(PhotoPerson.person_id.is_(None)).count()
        assert unassigned == 2

        # 2回目: 全URL重複 → 保存ゼロ
        result2 = CollectorService(db, env_id).run(src)
        assert result2.saved == 0
        assert result2.skipped_duplicate == 2
    finally:
        db.close()


def test_run_keeps_dedup_record_when_next_url_fails(client: TestClient, monkeypatch) -> None:
    """成功URLの収集記録は、後続URLの保存失敗(rollback)で消えない（重複再収集防止）。"""
    from sqlalchemy import select

    from app.db.base import SessionLocal
    from app.models.collect_source import CollectSource
    from app.models.collected_url import CollectedUrl
    from app.services.photo_service import PhotoService

    env = client.get("/environments").json()[0]
    env_id = env["id"]

    urls = ["https://ex.com/ok.jpg", "https://ex.com/broken.jpg"]
    monkeypatch.setattr(
        CollectorService, "collect_urls", lambda self, source: (list(urls), 1)
    )

    def fake_save_from_url(self, *, url, **kw):
        if url.endswith("broken.jpg"):
            raise ValueError("download failed")
        return self.store_image(content=b"x", filename="ok.jpg")

    monkeypatch.setattr(PhotoService, "save_from_url", fake_save_from_url)

    db = SessionLocal()
    try:
        src = CollectSource(
            environment_id=env_id, name="t", start_url="https://ex.com", crawl_mode="page"
        )
        db.add(src)
        db.commit()
        db.refresh(src)

        result = CollectorService(db, env_id).run(src)
        assert result.saved == 1
        assert result.failed == 1

        # 成功分の記録は rollback 後も残る → 次回は重複としてスキップ
        recorded = list(
            db.execute(
                select(CollectedUrl.url).where(CollectedUrl.environment_id == env_id)
            ).scalars()
        )
        assert recorded == ["https://ex.com/ok.jpg"]

        result2 = CollectorService(db, env_id).run(src)
        assert result2.skipped_duplicate == 1
        assert result2.failed == 1  # broken は再試行されまた失敗
    finally:
        db.close()


def test_environment_delete_cascades_collect(client: TestClient) -> None:
    env_b = _create_env(client, "B")
    client.post(
        "/collect/sources",
        json={"name": "消える元", "start_url": "https://b.com"},
        headers=_hdr(env_b["id"]),
    )
    assert client.delete(f"/environments/{env_b['id']}").status_code == 204

    from app.db.base import SessionLocal
    from app.models.collect_source import CollectSource

    db = SessionLocal()
    try:
        assert (
            db.query(CollectSource).filter(CollectSource.environment_id == env_b["id"]).count()
            == 0
        )
    finally:
        db.close()
