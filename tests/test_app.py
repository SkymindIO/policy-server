import ray
from fastapi.testclient import TestClient

from app import app
from generate import CLI

# Set up server
CLI.copy_server_files("examples/mouse_and_cheese")
client = TestClient(app)


def setup_function():
    ray.shutdown()


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "ok"


def test_docs():
    response = client.get("/docs")
    assert response.status_code == 200


def test_redoc():
    response = client.get("/redoc")
    assert response.status_code == 200


payload = {
    "mouse_row": 1,
    "mouse_col": 1,
    "mouse_row_distance": 1,
    "mouse_col_distance": 1,
    "cheese_row": 1,
    "cheese_col": 1,
}


def test_predict_no_auth():
    response = client.post("http://localhost:8000/predict/", json=payload)
    assert response.status_code == 403


def test_predict_bad_observations():
    response = client.post(
        "http://localhost:8000/predict/",
        json={"bad_payload": 1},
        headers={"access-token": "1234567asdfgh"},
    )
    assert response.status_code == 422


def test_predict():
    with TestClient(app) as client:
        response = client.post(
            "http://localhost:8000/predict/",
            json=payload,
            headers={"access-token": "1234567asdfgh"},
        )
        assert response.status_code == 200
        assert response.json()
        assert len(response.json()["actions"]) == 1
        assert response.json()["probability"] >= 0
        ray.shutdown()


def test_clients():
    with TestClient(app) as client:
        response = client.get(
            "http://localhost:8000/clients",
            headers={"access-token": "1234567asdfgh"},
        )
        assert response.status_code == 200
        ray.shutdown()
