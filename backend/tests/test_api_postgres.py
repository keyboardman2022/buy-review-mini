import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app


DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.integration


@pytest.fixture()
def client(tmp_path):
    if not DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to an isolated PostgreSQL database")
    if "test" not in DATABASE_URL.lower():
        pytest.skip("TEST_DATABASE_URL database name must contain 'test' because the fixture truncates tables")
    db = Database(DATABASE_URL)
    db.initialize()
    db.execute("TRUNCATE outbox,votes,approvals,reactions,comments,items,media,friends,friend_requests,sessions,challenges,users CASCADE")
    settings = Settings(
        mode="demo", database_url=DATABASE_URL, auth_secret="integration-test-secret", data_dir=tmp_path,
        public_url="http://testserver", host="127.0.0.1", port=3210, wechat={"app_id": "", "app_secret": ""},
        sms={"mode": "demo", "provider": "mock", "secret_id": "", "secret_key": "", "sms_app_id": "", "sign_name": "", "templates": {"otp": "", "review": "", "result": ""}, "region": "ap-guangzhou"},
    )
    with TestClient(create_app(settings)) as value:
        yield value


def login(client, account):
    result = client.post("/api/auth/demo", json={"account": account})
    assert result.status_code == 200
    return {"Authorization": f"Bearer {result.json()['token']}"}


def create_approval(client, owner_headers, reviewer_id):
    item_id = client.get("/api/items?scope=mine", headers=owner_headers).json()["items"][0]["id"]
    response = client.post("/api/approvals", headers=owner_headers, json={"itemId": item_id, "reviewerIds": [reviewer_id], "rule": "veto"})
    assert response.status_code == 200
    return response.json()["approval"]["id"]


def test_removed_friend_cannot_cast_a_pending_vote(client):
    owner, reviewer = login(client, "a"), login(client, "b")
    approval_id = create_approval(client, owner, "demo-b")
    assert client.delete("/api/friends/demo-b", headers=owner).status_code == 200
    response = client.post(f"/api/approvals/{approval_id}/vote", headers=reviewer, json={"decision": "accept", "comment": "价格合理"})
    assert response.status_code == 403
    assert "不是好友" in response.json()["error"]


def test_vote_at_expired_deadline_persists_expiration(client):
    owner, reviewer = login(client, "a"), login(client, "c")
    approval_id = create_approval(client, owner, "demo-c")
    Database(DATABASE_URL).execute("UPDATE approvals SET expires_at=0 WHERE id=%s", (approval_id,))
    response = client.post(f"/api/approvals/{approval_id}/vote", headers=reviewer, json={"decision": "accept", "comment": "可以买"})
    assert response.status_code == 409
    detail = client.get(f"/api/approvals/{approval_id}", headers=owner).json()["approval"]
    assert detail["status"] == "expired"
    assert detail["reviewers"][0]["decision"] is None


def test_approval_scopes_separate_pending_votes_and_closed_requests(client):
    owner, reviewer = login(client, "a"), login(client, "b")
    approval_id = create_approval(client, owner, "demo-b")
    pending = client.get("/api/approvals?scope=pending", headers=reviewer).json()
    assert [a["id"] for a in pending["approvals"]] == [approval_id]
    assert pending["pendingCount"] == 1
    assert client.get("/api/approvals?scope=handled", headers=reviewer).json()["approvals"] == []
    client.post(f"/api/approvals/{approval_id}/vote", headers=reviewer, json={"decision": "accept", "comment": "经常用，价格合理"})
    pending = client.get("/api/approvals?scope=pending", headers=reviewer).json()
    assert pending["approvals"] == [] and pending["pendingCount"] == 0
    assert client.get("/api/approvals?scope=handled", headers=reviewer).json()["approvals"][0]["id"] == approval_id
    another_id = create_approval(client, owner, "demo-b")
    client.post(f"/api/approvals/{another_id}/cancel", headers=owner)
    handled = client.get("/api/approvals?scope=handled", headers=reviewer).json()["approvals"]
    assert {a["id"] for a in handled} == {approval_id, another_id}
    assert client.get("/api/approvals?scope=pending", headers=reviewer).json()["pendingCount"] == 0
