"""Three refusals, each with its own type, raised from the service and mapped by one handler."""


def test_unknown_code_is_no_such_code(client):
    response = client.post("/pickups", json={"code": "000000"})
    assert response.status_code == 404
    assert response.json()["type"] == "/errors/no-such-code"


def test_expired_code_has_code_expired_type(client, clock):
    dropped = client.post("/drops", json={"size_class": "S", "flat": "101"})
    assert dropped.status_code == 201
    clock.advance(hours=49)
    response = client.post("/pickups", json={"code": dropped.json()["code"]})
    assert response.status_code == 404
    assert response.json()["type"] == "/errors/code-expired"


def test_no_door_free_has_its_own_type(client):
    response = None
    for number in range(100):
        response = client.post("/drops", json={"size_class": "S", "flat": f"{number:03d}"})
        if response.status_code == 409:
            break
    assert response is not None and response.status_code == 409
    assert response.json()["type"] == "/errors/no-door-free"
