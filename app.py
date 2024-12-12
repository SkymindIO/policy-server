import itertools
import json
import shutil
from typing import List

import ray
import yaml
from fastapi import Depends, FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKey
from ray import serve

import config
from api import Action, Observation, RawObservation
from docs import get_redoc_html, get_swagger_ui_html
from generate import CLI
from security import get_api_key

url_path = config.parameters.get("url_path")

app = (
    FastAPI(root_path=f"/{url_path}", docs_url=None, redoc_url=None)
    if url_path
    else FastAPI(docs_url=None, redoc_url=None)
)


@app.get("/docs", include_in_schema=False)
def overridden_swagger():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Pathmind Policy Server",
        swagger_favicon_url="https://www.google.com/s2/favicons?domain_url=pathmind.com",
        project_id=config.project_id,
        model_id=config.model_id,
    )


@app.get("/redoc", include_in_schema=False)
def overridden_redoc():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Pathmind Policy Server",
        redoc_favicon_url="https://www.google.com/s2/favicons?domain_url=pathmind.com",
        project_id=config.project_id,
        model_id=config.model_id,
    )


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
    async def predict(payload: Observation, api_key: APIKey = Depends(get_api_key)):
        lists = [
            [getattr(payload, obs)]
            if not isinstance(getattr(payload, obs), List)
            else getattr(payload, obs)
            for obs in config.observations.keys()
        ]
        observations = list(itertools.chain(*lists))
        # Note that ray can't pickle the pydantic "Observation" model, so we need to convert it here.
        return await SERVE_HANDLE.remote(observations)


@app.post("/predict_raw/", response_model=Action, tags=["Predictions"])
async def predict_raw(payload: RawObservation, api_key: APIKey = Depends(get_api_key)):
    return await SERVE_HANDLE.remote(payload.obs)


@app.get("/clients", tags=["Clients"])
async def clients(api_key: APIKey = Depends(get_api_key)):
    shutil.make_archive("clients", "zip", "./clients")
    return FileResponse(path="clients.zip", filename="clients.zip")


@app.get("/schema", tags=["Clients"])
async def server_schema(api_key: APIKey = Depends(get_api_key)):
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
