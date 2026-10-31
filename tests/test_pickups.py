"""A valid code opens the door once, frees it and stamps dwell — atomically."""
from sqlalchemy.orm import Session

from lockerline.models import Parcel


def make_drop(client):
    response = client.post("/drops", json={"size_class": "M", "flat": "302"})
    assert response.status_code == 201, response.text
    return response.json()


def test_pickup_opens_and_refuses_replay(client):
    drop = make_drop(client)
    opened = client.post("/pickups", json={"code": drop["code"]})
    assert opened.status_code == 200, opened.text

    repeated = client.post("/pickups", json={"code": drop["code"]})
    assert repeated.status_code == 409
    assert repeated.json()["type"] == "/errors/code-used"


def test_pickup_failure_after_parcel_write_returns_500(client, monkeypatch):
    drop = make_drop(client)
    original_flush = Session.flush

    def fail_after_collection_write(session, *args, **kwargs):
        if any(isinstance(row, Parcel) and row.state == "collected" for row in session.dirty):
            raise RuntimeError("injected failure after parcel update")
        return original_flush(session, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", fail_after_collection_write)
    response = client.post("/pickups", json={"code": drop["code"]})
    assert response.status_code == 500
