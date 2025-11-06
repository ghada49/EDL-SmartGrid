
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

good_item = {
    "building_code": "Bld_292a",
    "electricity_kwh": 83.91,
    "area_m2": 275.02,
    "year_construction": 1960,
    "num_floors": 7,
    "num_apartments": 12,
    "function": "Residentiel",
    "longitude": 35.51187,
    "latitude": 33.87996
}

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

def test_score_one():
    r = client.post("/ml/v1/score", json=good_item)
    assert r.status_code == 200
    data = r.json()
    assert "score" in data and "is_fraud" in data

def test_batch_score():
    payload = {"items":[good_item, good_item]}
    r = client.post("/ml/v1/batch/score", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data and "summary" in data
    assert len(data["results"]) == 2
