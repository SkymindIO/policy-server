import itertools
import json
import shutil
from typing import List

import numpy as np
import ray
import yaml
from fastapi import Depends, FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKey
from ray import serve
from ray.rllib.evaluation.sample_batch_builder import SampleBatchBuilder
from ray.rllib.offline.json_writer import JsonWriter

import config
from api import (
    Action,
    Experience,
    Observation,
    RawObservation,
    _distribution,
    _predict,
    _predict_deterministic,
)
from generate import CLI
from offline import EpisodeCache
from security import get_api_key, verify_credentials

cache = EpisodeCache()
batch_builder = SampleBatchBuilder()  # or MultiAgentSampleBatchBuilder
writer = JsonWriter(config.EXPERIENCE_LOCATION)

url_path = config.parameters.get("url_path")

app = FastAPI(root_path=f"/{url_path}") if url_path else FastAPI()

tags_metadata = [
    {
        "name": "Predictions",
        "description": "Get actions for your next observations.",
    },
    {
        "name": "Clients",
        "description": "Get libraries in several programming languages to connect with this server.",
    },
    {
        "name": "Health",
        "description": "Basic health checks.",
    },
]


SERVE_HANDLE = None


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Pathmind Policy Server",
        description="Serve your policies in production",
        version="1.0.0",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://i2.wp.com/pathmind.com/wp-content/uploads/2020/07/pathmind-logo-blue.png?w=1176&ssl=1"
    }
    if url_path:
        openapi_schema["servers"] = [{"url": f"/{url_path}"}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


if config.USE_RAY:

    @app.on_event("startup")
    async def startup_event():

        ray.init(num_cpus=4, _metrics_export_port=8080)  # Initialize new ray instance
        client = serve.start(http_host=None)

        backend_config = serve.BackendConfig()

        from api import PathmindPolicy

        serve.create_backend("pathmind_policy", PathmindPolicy, config=backend_config)
        serve.create_endpoint("predict", backend="pathmind_policy")

        global SERVE_HANDLE
        SERVE_HANDLE = serve.get_handle("predict")


if config.observations:
    # Note: for basic auth, use "logged_in: bool = Depends(verify_credentials)" as parameter
    @app.post("/predict/", response_model=Action, tags=["Predictions"])
    async def predict(
        payload: Observation, logged_in: bool = Depends(verify_credentials)
    ):
        lists = [
            [getattr(payload, obs)]
            if not isinstance(getattr(payload, obs), List)
            else getattr(payload, obs)
            for obs in config.observations.keys()
        ]
        observations = list(itertools.chain(*lists))
        # Note that ray can't pickle the pydantic "Observation" model, so we need to convert it here.
        return await SERVE_HANDLE.remote(observations)

    @app.post("/predict_deterministic/", response_model=Action, tags=["Predictions"])
    async def predict_deterministic(
        payload: Observation, api_key: APIKey = Depends(get_api_key)
    ):
        return _predict_deterministic(payload)

    @app.post("/distribution/", tags=["Predictions"])
    async def distribution(
        payload: Observation, logged_in: bool = Depends(verify_credentials)
    ):
        return _distribution(payload)

    @app.post("/collect_experience/", response_model=Action, tags=["Predictions"])
    async def collect_experience(
        payload: Experience, api_key: APIKey = Depends(get_api_key)
    ):

        global cache
        global batch_builder

        observation = payload.observation
        rew = payload.reward
        done = payload.done

        lists = [
            [getattr(observation, obs)]
            if not isinstance(getattr(observation, obs), List)
            else getattr(observation, obs)
            for obs in config.observations.keys()
        ]

        obs = list(itertools.chain(*lists))
        obs = np.reshape(np.asarray(obs), (4,))

        action = _predict(obs)

        # from client import prep
        # print("The preprocessor is", prep)

        if cache.is_empty():
            cache.store(t=0, prev_obs=obs, prev_action=action.actions, prev_reward=rew)

        act = action.actions[0]

        batch_builder.add_values(
            agent_index=0,
            actions=act,
            action_prob=action.probability,
            action_logp=np.log(action.probability),
            t=cache.t,
            eps_id=cache.episode,
            prev_actions=cache.prev_action,
            prev_rewards=cache.prev_reward,
            obs=cache.prev_obs,  # prep.transform(...)
            # sent from environment
            new_obs=obs,
            dones=done,
            infos=None,
            rewards=rew,
        )
        cache.store(t=cache.t + 1, prev_obs=obs, prev_action=act, prev_reward=rew)

        if done:
            writer.write(batch_builder.build_and_reset())
            cache.reset()

        return action


@app.post("/predict_raw/", response_model=Action, tags=["Predictions"])
async def predict_raw(payload: RawObservation, api_key: APIKey = Depends(get_api_key)):
    return await SERVE_HANDLE.remote(payload.obs)


@app.get("/clients", tags=["Clients"])
async def clients(api_key: APIKey = Depends(get_api_key)):
    shutil.make_archive("clients", "zip", "./clients")
    return FileResponse(path="clients.zip", filename="clients.zip")


@app.get("/schema", tags=["Clients"])
async def server_schema(logged_in: bool = Depends(verify_credentials)):
    with open(config.PATHMIND_SCHEMA, "r") as schema_file:
        schema_str = schema_file.read()
    schema = yaml.safe_load(schema_str)
    return schema


@app.get("/", tags=["Health"])
async def health_check():
    return "ok"


app.openapi = custom_openapi

# Write the swagger file locally
with open(config.LOCAL_SWAGGER, "w") as f:
    f.write(json.dumps(app.openapi()))

# Generate all clients on startup
CLI.clients()
