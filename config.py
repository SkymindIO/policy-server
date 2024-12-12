"""Basic configuration for the application."""
import os
from collections import OrderedDict

import oyaml as yaml
from pydantic import Field

USE_RAY = True

EXPERIENCE_LOCATION = "./offline_data/"


def base_path(local_file):
    """Join a local file with the BASE_PATH.
    :param local_file: relative path to file on your system.
    :return: joined path
    """
    return os.path.join(BASE_PATH, local_file)


# If you put BASE_PATH on your PATH we use that, otherwise the current working directory.
BASE_PATH = os.environ.get("BASE_PATH", os.path.expanduser("."))

PATHMIND_POLICY = base_path("saved_model.zip")
PATHMIND_SCHEMA = base_path("schema.yaml")

# Naming conventions are fixed, as we can control names on upload.
MODEL_FOLDER = base_path("models")
TF_MODEL_PATH = base_path("models/")
SWAGGER_FILE = "http://localhost:8000/openapi.json"
LOCAL_SWAGGER = base_path("openapi.json")
CLIENTS_ZIP = base_path("clients.zip")


USER_NAME = "admin"
PASSWORD = "admin"


with open(PATHMIND_SCHEMA, "r") as f:
    schema: OrderedDict = yaml.safe_load(f.read())

observations = schema.get("observations")
parameters = schema.get("parameters")
action_type = int if parameters.get("discrete") else float

model_id = parameters.get("model_id", None)
project_id = parameters.get("project_id", None)

payload_data = {}
# If the schema includes `max_items` set the constraints for the array
if observations:
    payload_data = {
        k: (
            v.get("type"),
            Field(..., max_items=v.get("max_items"), min_items=v.get("min_items"))
            if v.get("max_items")
            else ...,
        )
        for k, v in observations.items()
    }
