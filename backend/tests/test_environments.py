"""環境（テナント）分離。CRUD + データ隔離 + 削除カスケード。"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _create_env(client: TestClient, name: str) -> dict:
    res = client.post("/environments", json={"name": name})
    assert res.status_code == 201, res.text
    return res.json()


def _hdr(env_id: int) -> dict[str, str]:
    return {"X-Environment-Id": str(env_id)}


def test_default_environment_autocreated(client: TestClient) -> None:
    res = client.get("/environments")
    assert res.status_code == 200
    envs = res.json()
    assert len(envs) == 1
    assert envs[0]["name"] == "default"


def test_environment_crud(client: TestClient) -> None:
    env = _create_env(client, "実験B")
    assert env["name"] == "実験B"

    # 同名は409
    assert client.post("/environments", json={"name": "実験B"}).status_code == 409

    # rename
    res = client.patch(f"/environments/{env['id']}", json={"name": "本番B"})
    assert res.status_code == 200
    assert res.json()["name"] == "本番B"

    # delete
    assert client.delete(f"/environments/{env['id']}").status_code == 204
    ids = [e["id"] for e in client.get("/environments").json()]
    assert env["id"] not in ids


def test_cannot_delete_last_environment(client: TestClient) -> None:
    envs = client.get("/environments").json()
    assert len(envs) == 1
    assert client.delete(f"/environments/{envs[0]['id']}").status_code == 409


def test_unknown_environment_header_404(client: TestClient) -> None:
    assert client.get("/persons", headers=_hdr(9999)).status_code == 404


def test_person_isolation_between_environments(client: TestClient) -> None:
    env_a = client.get("/environments").json()[0]
    env_b = _create_env(client, "B")

    res = client.post(
        "/persons", json={"name": "太郎"}, headers=_hdr(env_a["id"])
    )
    assert res.status_code == 201
    taro = res.json()

    # A には見える
    names_a = [p["name"] for p in client.get("/persons", headers=_hdr(env_a["id"])).json()]
    assert "太郎" in names_a
    # B には見えない
    assert client.get("/persons", headers=_hdr(env_b["id"])).json() == []
    assert client.get("/persons/count", headers=_hdr(env_b["id"])).json()["count"] == 0
    # B から ID 直アクセスも不可視
    assert client.get(f"/persons/{taro['id']}", headers=_hdr(env_b["id"])).status_code == 404
    # ヘッダ無し = default(A) → 見える
    assert client.get(f"/persons/{taro['id']}").status_code == 200


def test_tag_same_name_in_two_environments(client: TestClient) -> None:
    env_a = client.get("/environments").json()[0]
    env_b = _create_env(client, "B")

    res_a = client.post(
        "/persons",
        json={"name": "太郎", "tags": ["大学"]},
        headers=_hdr(env_a["id"]),
    )
    res_b = client.post(
        "/persons",
        json={"name": "次郎", "tags": ["大学"]},
        headers=_hdr(env_b["id"]),
    )
    assert res_a.status_code == 201 and res_b.status_code == 201
    tag_a = res_a.json()["tags"][0]
    tag_b = res_b.json()["tags"][0]
    assert tag_a["name"] == tag_b["name"] == "大学"
    assert tag_a["id"] != tag_b["id"]  # 環境別に独立した行


def test_event_isolation(client: TestClient) -> None:
    env_a = client.get("/environments").json()[0]
    env_b = _create_env(client, "B")

    res = client.post("/events", json={"name": "GW飲み会"}, headers=_hdr(env_a["id"]))
    assert res.status_code == 201
    assert client.get("/events", headers=_hdr(env_b["id"])).json() == []
    assert (
        client.get("/events/count", headers=_hdr(env_b["id"])).json()["count"] == 0
    )


def test_cross_environment_merge_rejected(client: TestClient) -> None:
    env_a = client.get("/environments").json()[0]
    env_b = _create_env(client, "B")
    a = client.post("/persons", json={"name": "A太"}, headers=_hdr(env_a["id"])).json()
    b = client.post("/persons", json={"name": "B次"}, headers=_hdr(env_b["id"])).json()

    res = client.post(
        f"/persons/{a['id']}/merge",
        json={"source_id": b["id"]},
        headers=_hdr(env_a["id"]),
    )
    assert res.status_code == 400


def test_environment_delete_cascades_data(client: TestClient) -> None:
    env_b = _create_env(client, "B")
    hdr = _hdr(env_b["id"])
    person = client.post("/persons", json={"name": "消える人"}, headers=hdr).json()
    client.post("/events", json={"name": "消える会"}, headers=hdr)

    assert client.delete(f"/environments/{env_b['id']}").status_code == 204

    # default 環境からは元々見えず、全体からも消えている
    from app.db.base import SessionLocal
    from app.models.event import Event
    from app.models.person import Person

    db = SessionLocal()
    try:
        assert db.get(Person, person["id"]) is None
        assert db.query(Event).filter(Event.name == "消える会").first() is None
    finally:
        db.close()


def test_vector_isolation_between_environments(client: TestClient) -> None:
    """環境Aで登録した顔ベクトルは環境Bの照合に出ない。"""
    import numpy as np

    from app.db.base import SessionLocal
    from app.face.registry import get_index
    from app.services.face_service import FaceService

    env_a = client.get("/environments").json()[0]
    env_b = _create_env(client, "B")
    person = client.post(
        "/persons", json={"name": "太郎"}, headers=_hdr(env_a["id"])
    ).json()

    rng = np.random.default_rng(1)
    vec = rng.standard_normal(512).astype("float32")
    vec /= np.linalg.norm(vec)

    db = SessionLocal()
    try:
        svc_a = FaceService(
            db, get_index(env_id=env_a["id"]), env_id=env_a["id"], threshold=0.5
        )
        svc_a.register_embedding(person["id"], vec)
        db.commit()

        # A では命中
        assert svc_a.match(vec, k=1)[0].person_id == person["id"]
        # B では候補ゼロ
        svc_b = FaceService(
            db, get_index(env_id=env_b["id"]), env_id=env_b["id"], threshold=0.5
        )
        assert svc_b.match(vec, k=1) == []
    finally:
        db.close()
