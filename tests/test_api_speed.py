import timeit

import ray
from fastapi.testclient import TestClient

from app import app
from generate import CLI

CLI.copy_server_files("examples/lpoc")
client = TestClient(app)


payload = {
    "coordinates": [1, 1],
    "has_core": True,
    "has_down_neighbour": True,
    "has_left_neighbour": True,
    "has_right_neighbour": True,
    "has_up_neighbour": True,
    "id": 0,
    "is_down_free": True,
    "is_left_free": False,
    "is_right_free": True,
    "is_up_free": True,
    "name": "pt07_c",
    "target": [6, 2],
}


def predict():
    return client.post(
        "http://localhost:8000/predict/",
        json=payload,
        headers={"access-token": "1234567asdfgh"},
    )


def test_predict():
    number = 1000
    res = timeit.timeit(predict, number=number)
    print(
        f"A total of {number} requests took {res} milliseconds to process on average."
    )
    ray.shutdown()
