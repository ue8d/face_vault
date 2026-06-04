"""EXIF抽出 / 写真削除 / CSV img_url 予約。"""
from __future__ import annotations

import io
from email.message import EmailMessage

from fastapi.testclient import TestClient
from PIL import Image


def _jpeg_with_exif(dt: str | None) -> bytes:
    img = Image.new("RGB", (40, 40), (100, 100, 100))
    buf = io.BytesIO()
    if dt:
        exif = img.getexif()
        exif[0x8769] = {36867: dt}  # DateTimeOriginal
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


def test_exif_taken_at_parsing() -> None:
    from app.services.photo_service import _exif_taken_at

    dt = _exif_taken_at(_jpeg_with_exif("2019:07:15 10:30:00"))
    assert dt is not None and dt.year == 2019 and dt.month == 7 and dt.day == 15
    assert _exif_taken_at(_jpeg_with_exif(None)) is None


def test_upload_uses_exif_when_no_taken_at(client: TestClient) -> None:
    files = {"file": ("e.jpg", io.BytesIO(_jpeg_with_exif("2018:03:04 05:06:07")), "image/jpeg")}
    r = client.post("/photos/upload", files=files)
    assert r.status_code == 201, r.text
    assert r.json()["taken_at"].startswith("2018-03-04")


def test_import_photo_from_url(client: TestClient, monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content
            self.headers = EmailMessage()
            self.headers["Content-Type"] = "image/jpeg"

        def read(self, size: int = -1) -> bytes:
            return self.content if size < 0 else self.content[:size]

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args) -> None:
            return None

    def fake_urlopen(req, timeout: int):
        assert req.full_url == "https://example.com/p.jpg"
        assert timeout == 20
        return FakeResponse(_jpeg_with_exif(None))

    monkeypatch.setattr("app.services.photo_service.urllib.request.urlopen", fake_urlopen)

    r = client.post(
        "/photos/import-url",
        json={"url": "https://example.com/p.jpg", "memo": "URL取込"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["memo"] == "URL取込\n画像名: p.jpg"
    assert client.get(f"/photos/{body['id']}/raw").status_code == 200


def test_import_photos_from_urls(client: TestClient, monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content
            self.headers = EmailMessage()
            self.headers["Content-Type"] = "image/jpeg"

        def read(self, size: int = -1) -> bytes:
            return self.content if size < 0 else self.content[:size]

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args) -> None:
            return None

    seen: list[str] = []

    def fake_urlopen(req, timeout: int):
        seen.append(req.full_url)
        assert timeout == 20
        return FakeResponse(_jpeg_with_exif(None))

    monkeypatch.setattr("app.services.photo_service.urllib.request.urlopen", fake_urlopen)

    r = client.post(
        "/photos/import-urls",
        json={
            "urls": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
            "memo": "URL一括",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert seen == ["https://example.com/a.jpg", "https://example.com/b.jpg"]
    assert len(body["created"]) == 2
    assert body["errors"] == []
    assert {p["memo"] for p in body["created"]} == {
        "URL一括\n画像名: a.jpg",
        "URL一括\n画像名: b.jpg",
    }


def test_upload_photos_bulk(client: TestClient) -> None:
    files = [
        ("files", ("a.jpg", io.BytesIO(_jpeg_with_exif(None)), "image/jpeg")),
        ("files", ("b.jpg", io.BytesIO(_jpeg_with_exif(None)), "image/jpeg")),
    ]
    r = client.post("/photos/upload-bulk", files=files, data={"memo": "一括"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["created"]) == 2
    assert body["errors"] == []
    assert {p["memo"] for p in body["created"]} == {
        "一括\n画像名: a.jpg",
        "一括\n画像名: b.jpg",
    }


def test_delete_photo(client: TestClient) -> None:
    files = {"file": ("d.jpg", io.BytesIO(_jpeg_with_exif(None)), "image/jpeg")}
    pid = client.post("/photos/upload", files=files).json()["id"]
    assert client.delete(f"/photos/{pid}").status_code == 204
    assert client.get(f"/photos/{pid}").status_code == 404
    assert client.delete(f"/photos/{pid}").status_code == 404


def test_import_enqueues_face_for_img_url(client: TestClient) -> None:
    csv_body = (
        '"id","name","name_type","img_url"\n'
        '"x1","テスト","main","https://example.com/a.jpg"\n'
    )
    files = {"file": ("f.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")}
    r = client.post("/persons/import", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["face_queued"] == 1
    # キューに1件入っている（背景処理の成否に依らず合計1）
    st = client.get("/persons/import/face-status").json()
    assert st["pending"] + st["done"] + st["failed"] == 1
