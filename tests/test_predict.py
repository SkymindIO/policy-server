import ray
from fastapi.testclient import TestClient

from app import app
from generate import CLI

# Set up server
CLI.copy_server_files("examples/mouse_and_cheese")
client = TestClient(app)

payload = {
    "mouse_row": 1,
    "mouse_col": 1,
    "mouse_row_dist": 1,
    "mouse_col_dist": 1,
}


def predict():
    return client.post(
        "http://localhost:8000/predict/",
        json=payload,
        headers={"access-token": "1234567asdfgh"},
    )


def test_predict_simple():
    res = predict()
    assert res is not None
    ray.shutdown()


def test_write_openapi_json():
    res = client.get("http://localhost:8000/openapi.json")

    with open("../openapi.json", "w") as f:
        f.write(res.content.decode("utf-8"))

    ray.shutdown()
