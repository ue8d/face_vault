"""人物CRUD + タグ。"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient


def test_create_and_get_person(client: TestClient) -> None:
    r = client.post(
        "/persons",
        json={
            "name": "山田太郎",
            "nicknames": ["タロ", "やまちゃん"],
            "relation": "大学の友人",
            "memo": "サークル仲間",
            "tags": ["大学", "趣味仲間"],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "山田太郎"
    assert body["nicknames"] == ["タロ", "やまちゃん"]
    assert {t["name"] for t in body["tags"]} == {"大学", "趣味仲間"}
    pid = body["id"]

    r = client.get(f"/persons/{pid}")
    assert r.status_code == 200
    assert r.json()["nicknames"] == ["タロ", "やまちゃん"]


def test_nicknames_update_and_dedup(client: TestClient) -> None:
    pid = client.post(
        "/persons", json={"name": "B", "nicknames": ["ビー", "ビー", " "]}
    ).json()["id"]
    # 重複排除・空白除去
    assert client.get(f"/persons/{pid}").json()["nicknames"] == ["ビー"]
    # 更新で置換
    r = client.patch(f"/persons/{pid}", json={"nicknames": ["B太", "ビーちゃん"]})
    assert r.json()["nicknames"] == ["B太", "ビーちゃん"]


def test_list_and_search_persons(client: TestClient) -> None:
    client.post("/persons", json={"name": "田中花子"})
    client.post("/persons", json={"name": "鈴木一郎"})

    assert len(client.get("/persons").json()) == 2
    hits = client.get("/persons", params={"q": "田中"}).json()
    assert len(hits) == 1 and hits[0]["name"] == "田中花子"


def test_list_persons_pagination(client: TestClient) -> None:
    for i in range(105):
        client.post("/persons", json={"name": f"Paged Person {i:03d}"})

    first = client.get("/persons", params={"limit": 100, "offset": 0}).json()
    second = client.get("/persons", params={"limit": 100, "offset": 100}).json()
    searched = client.get(
        "/persons", params={"q": "Paged Person", "limit": 10, "offset": 100}
    ).json()

    assert len(first) == 100
    assert len(second) == 5
    assert len(searched) == 5


def test_search_persons_deduplicates_multiple_nickname_matches(
    client: TestClient,
) -> None:
    client.post(
        "/persons",
        json={
            "name": "Nickname Owner",
            "nicknames": ["shared alias one", "shared alias two"],
        },
    )

    hits = client.get("/persons", params={"q": "shared alias"}).json()

    assert len(hits) == 1
    assert hits[0]["name"] == "Nickname Owner"


def test_import_persons_from_friend_csv(client: TestClient) -> None:
    csv_body = """id,name,name_type
1,三上かなみ,main
1,Kanako,alias
1,K.Mikami,alias
2,相下れな,main
2,Rei,alias
3,佐伯まい,main
4,三橋ゆい,main
"""
    files = {"file": ("friends.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")}
    r = client.post("/persons/import", files=files)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "created": 4,
        "updated": 0,
        "skipped": 0,
        "face_queued": 0,
        "errors": [],
    }

    people = client.get("/persons").json()
    by_name = {person["name"]: person for person in people}
    assert by_name["三上かなみ"]["nicknames"] == ["Kanako", "K.Mikami"]
    assert by_name["相下れな"]["nicknames"] == ["Rei"]
    assert by_name["佐伯まい"]["nicknames"] == []

    hits = client.get("/persons", params={"q": "Mikami"}).json()
    assert [person["name"] for person in hits] == ["三上かなみ"]

    r = client.post("/persons/import", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 0
    assert r.json()["updated"] == 0


def test_import_allows_duplicate_main_names_when_external_ids_differ(
    client: TestClient,
) -> None:
    csv_body = """id,name,name_type
10,同姓同名,main
10,Alice,alias
11,同姓同名,main
11,Bob,alias
"""
    files = {"file": ("friends.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")}
    r = client.post("/persons/import", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2

    hits = client.get("/persons", params={"q": "同姓同名"}).json()
    assert len(hits) == 2
    assert sorted(person["nicknames"][0] for person in hits) == ["Alice", "Bob"]

    files = {"file": ("friends.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")}
    r = client.post("/persons/import", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 0
    assert len(client.get("/persons", params={"q": "同姓同名"}).json()) == 2


def test_update_and_delete_person(client: TestClient) -> None:
    pid = client.post("/persons", json={"name": "A"}).json()["id"]

    r = client.patch(f"/persons/{pid}", json={"relation": "家族", "tags": ["家族"]})
    assert r.status_code == 200
    assert r.json()["relation"] == "家族"

    assert client.delete(f"/persons/{pid}").status_code == 204
    assert client.get(f"/persons/{pid}").status_code == 404


def test_confirm_face_unknown_person_returns_404(client: TestClient) -> None:
    """存在しない人物IDでの顔確定はFK違反500ではなく404。"""
    from app.db.base import SessionLocal
    from app.models.photo import Photo
    from app.models.photo_person import PhotoPerson

    db = SessionLocal()
    try:
        photo = Photo(path="x.jpg")
        db.add(photo)
        db.flush()
        link = PhotoPerson(photo_id=photo.id, person_id=None, bbox="0,0,10,10")
        db.add(link)
        db.commit()
        link_id = link.id
    finally:
        db.close()

    r = client.patch(f"/faces/links/{link_id}", json={"person_id": 999999})
    assert r.status_code == 404


def test_register_person_face_unknown_person_returns_404(client: TestClient) -> None:
    files = {"file": ("f.jpg", io.BytesIO(b"x"), "image/jpeg")}
    r = client.post("/persons/999999/faces", files=files)
    assert r.status_code == 404
