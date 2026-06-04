"""イベント + 写真アップロード/検索 + identify。"""
from __future__ import annotations

import io

import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import SessionLocal
from app.face.detector import DetectedFace
from app.models.cooccurrence import PersonCooccurrence
from app.models.photo_person import PhotoPerson


def _face_vec(index: int) -> np.ndarray:
    vec = np.zeros(512, dtype="float32")
    vec[index] = 1.0
    return vec


class FakeDetector:
    def __init__(self, embeddings: list[np.ndarray]) -> None:
        self.embeddings = embeddings

    def detect(self, image_bytes: bytes) -> list[DetectedFace]:
        return [
            DetectedFace(bbox=(i, i, 10, 10), embedding=embedding)
            for i, embedding in enumerate(self.embeddings)
        ]


def test_event_crud(client: TestClient) -> None:
    r = client.post("/events", json={"name": "GW飲み会", "memo": "渋谷"})
    assert r.status_code == 201
    eid = r.json()["id"]
    assert client.get("/events").json()[0]["name"] == "GW飲み会"
    assert client.patch(f"/events/{eid}", json={"memo": "新宿"}).json()["memo"] == "新宿"


def test_photo_upload_and_list(client: TestClient) -> None:
    eid = client.post("/events", json={"name": "沖縄旅行"}).json()["id"]
    files = {"file": ("a.jpg", io.BytesIO(b"fakejpegbytes"), "image/jpeg")}
    r = client.post("/photos/upload", files=files, data={"memo": "海", "event_id": str(eid)})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["memo"] == "海\n画像名: a.jpg" and body["event_id"] == eid

    photos = client.get("/photos", params={"event_id": eid}).json()
    assert len(photos) == 1


def test_photo_update(client: TestClient) -> None:
    eid = client.post("/events", json={"name": "updated event"}).json()["id"]
    files = {"file": ("a.jpg", io.BytesIO(b"fakejpegbytes"), "image/jpeg")}
    photo = client.post("/photos/upload", files=files, data={"memo": "before"}).json()

    r = client.patch(
        f"/photos/{photo['id']}",
        json={"memo": "after", "event_id": eid, "taken_at": "2026-01-02T03:04:05Z"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["memo"] == "after"
    assert body["event_id"] == eid
    assert body["taken_at"].startswith("2026-01-02T03:04:05")

    cleared = client.patch(f"/photos/{photo['id']}", json={"memo": None, "event_id": None}).json()
    assert cleared["memo"] is None
    assert cleared["event_id"] is None


def test_photo_reprocess_replaces_existing_face_links(client: TestClient, monkeypatch) -> None:
    from app.face import detector as detector_mod

    monkeypatch.setattr(detector_mod, "_default", FakeDetector([_face_vec(1), _face_vec(2)]))

    files = {"file": ("a.jpg", io.BytesIO(b"fakejpegbytes"), "image/jpeg")}
    photo = client.post("/photos/upload", files=files, data={"memo": "faces"}).json()
    assert len(photo["person_links"]) == 2

    monkeypatch.setattr(detector_mod, "_default", FakeDetector([_face_vec(3)]))
    r = client.post(f"/photos/{photo['id']}/reprocess")

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["person_links"]) == 1

    db = SessionLocal()
    try:
        links = db.execute(
            select(PhotoPerson).where(PhotoPerson.photo_id == photo["id"])
        ).scalars().all()
        cooccurrences = db.execute(select(PersonCooccurrence)).scalars().all()
    finally:
        db.close()

    assert len(links) == 1
    assert cooccurrences == []


def test_photo_search_by_tag_and_event_name(client: TestClient) -> None:
    person_id = client.post(
        "/persons", json={"name": "Tagged Person", "tags": ["friends", "work"]}
    ).json()["id"]
    event_id = client.post("/events", json={"name": "Summer Camp"}).json()["id"]

    files = {"file": ("a.jpg", io.BytesIO(b"fakejpegbytes"), "image/jpeg")}
    photo = client.post(
        "/photos/upload", files=files, data={"memo": "with tag", "event_id": str(event_id)}
    ).json()

    db = SessionLocal()
    try:
        db.add(PhotoPerson(photo_id=photo["id"], person_id=person_id))
        db.commit()
    finally:
        db.close()

    by_tag = client.get("/photos", params={"tag": "friend"}).json()
    assert [p["id"] for p in by_tag] == [photo["id"]]

    by_event_name = client.get("/photos", params={"event_name": "Camp"}).json()
    assert [p["id"] for p in by_event_name] == [photo["id"]]

    events = client.get("/events", params={"q": "Summer"}).json()
    assert [e["id"] for e in events] == [event_id]


def test_person_event_api(client: TestClient) -> None:
    person_id = client.post("/persons", json={"name": "Event Person"}).json()["id"]
    event_id = client.post("/events", json={"name": "Meetup"}).json()["id"]

    r = client.post(f"/persons/{person_id}/events/{event_id}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == event_id

    assert [e["id"] for e in client.get(f"/persons/{person_id}/events").json()] == [event_id]
    assert [p["id"] for p in client.get(f"/events/{event_id}/persons").json()] == [person_id]

    duplicate = client.post(f"/events/{event_id}/persons/{person_id}")
    assert duplicate.status_code == 200, duplicate.text
    assert len(client.get(f"/events/{event_id}/persons").json()) == 1

    assert client.delete(f"/events/{event_id}/persons/{person_id}").status_code == 204
    assert client.get(f"/persons/{person_id}/events").json() == []


def test_identify_person_template(client: TestClient) -> None:
    pid = client.post(
        "/persons", json={"name": "山田太郎", "relation": "大学の友人"}
    ).json()["id"]
    r = client.post("/identify-person", json={"person_id": pid})
    assert r.status_code == 200, r.text
    ans = r.json()["answer"]
    assert "山田太郎さんです" in ans
    assert "大学の友人" in ans
