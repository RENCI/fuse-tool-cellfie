import datetime
import json
import logging
import os
import pathlib
import shutil
import traceback
import uuid
from datetime import datetime
from logging.config import dictConfig

import aiofiles
import docker
import requests
from docker.errors import ContainerError
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fuse_cdm.main import ToolParameters

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s | %(levelname)s | %(module)s:%(funcName)s | %(message)s'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        },
    },
    'loggers': {
        "fuse-tool-cellfie": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL")},
    }
}

dictConfig(LOGGING)
logger = logging.getLogger("fuse-tool-cellfie")

g_api_version = "0.0.1"

app = FastAPI(openapi_url=f"/api/{g_api_version}/openapi.json",
              title="CellFie Tool",
              version=g_api_version,
              terms_of_service="https://github.com/RENCI/fuse-agent/doc/terms.pdf",
              contact={
                  "url": "http://txscience.renci.org/contact/",
              },
              license_info={
                  "name": "MIT License",
                  "url": "https://github.com/RENCI/fuse-tool-cellfie/blob/main/LICENSE"
              }
              )

client = docker.from_env()

origins = [
    f"http://{os.getenv('HOSTNAME')}:{os.getenv('HOSTPORT')}",
    f"http://{os.getenv('HOSTNAME')}",
    f"http://localhost:{os.getenv('HOSTPORT')}",
    "http://localhost",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API is described in:
# http://localhost:8086/openapi.json

# Therefore:
# This endpoint self-describes with:
# curl -X 'GET'    'http://localhost:8083/openapi.json' -H 'accept: application/json' 2> /dev/null |python -m json.tool |jq '.paths."/submit".post.parameters' -C |less
# for example, an array of parameter names can be retrieved with:
# curl -X 'GET'    'http://localhost:8083/openapi.json' -H 'accept: application/json' 2> /dev/null |python -m json.tool |jq '.paths."/submit".post.parameters[].name' 


def get_results(results_file: str):
    results_data = []
    results_feature_count = 0
    logger.info(f"reading: {results_file}")
    with open(results_file, 'r') as csvfile:
        data = csvfile.readlines()
        for line in data:
            if results_feature_count == 0:
                results_feature_count = len(line.split(','))
            results_data.append(tuple(line.strip().split(',')))
    dimension = [len(results_data), results_feature_count]
    logger.info(f"dimension: {dimension}")
    return dimension, results_data


@app.post("/submit", description="Submit an analysis")
async def analyze(parameters: ToolParameters = Depends(ToolParameters.as_form),
                  expression_file: UploadFile = File(default=None, description="Gene Expression Data (csv)")):
    logger.debug(msg=f"parameters: {parameters}")
    try:
        start_time = datetime.now()

        global_value = parameters.percentile if parameters.percentile_or_value == "percentile" else parameters.value
        local_values = f"{parameters.percentile_low} {parameters.percentile_high}" if parameters.percentile_or_value == "percentile" else f"{parameters.value_low} {parameters.value_high} "

        task_id = str(uuid.uuid4())[:8]
        task_path = os.path.abspath(f"/app/data/{task_id}")
        os.makedirs(task_path, exist_ok=False)

        param_path = os.path.join(task_path, "parameters.json")
        with open(param_path, 'w', encoding='utf-8') as f:
            f.write(parameters.json())
        f.close()

        file_path = os.path.join(task_path, "geneBySampleMatrix.csv")

        match (expression_file, parameters.expression_url):
            case (None, url):
                response = requests.get(url)
                open(file_path, 'wb').write(response.content)
            case (file, None):
                async with aiofiles.open(file_path, 'wb') as out_file:
                    content = await file.read()
                    await out_file.write(content)

        with open(file_path) as f:
            firstline = f.readline().rstrip()
            # assumption is that the first column is a target
            number_of_samples = len(firstline.split(",")) - 1

        logger.info(f"number_of_samples: {number_of_samples}")

        image = "hmasson/cellfie-standalone-app:v2"

        if os.environ.get("CELLFIE_INPUT_PATH") is not None:
            volumes = {
                'cellfie-data': {'bind': '/data', 'mode': 'rw'},
                f"{os.getenv('CELLFIE_INPUT_PATH')}": {'bind': '/input', 'mode': 'rw'},
            }
        else:
            volumes = {
                'cellfie-data': {'bind': '/data', 'mode': 'rw'},
                'cellfie-input-data': {'bind': '/input', 'mode': 'rw'},
            }
        logger.info(f"volumes: {volumes}")
        command = f"/data/{task_id}/geneBySampleMatrix.csv {number_of_samples} {parameters.reference_model} {parameters.threshold_type} {parameters.percentile_or_value} {global_value} {parameters.local_threshold_type} {local_values} /data/{task_id}"
        logger.info(f"command: {command}")
        try:
            cellfie_container_logs = client.containers.run(image, volumes=volumes, name=task_id, working_dir="/input", privileged=True, remove=True, command=command, detach=False,
                                                           mem_limit="10g")
            cellfie_container_logs_decoded = cellfie_container_logs.decode("utf8")
            logger.info(cellfie_container_logs_decoded)
        except ContainerError as err:
            logger.exception(err)
            raise HTTPException(status_code=404, detail="problem running the hmasson/cellfie-standalone-app:v2 image")

        end_time = datetime.now()
        duration = end_time - start_time
        logger.debug(msg=f"run duration: {divmod(duration.seconds, 60)}")

        detail_scoring_results_file = os.path.join(task_path, "detailScoring.csv")
        score_binary_results_file = os.path.join(task_path, "score_binary.csv")
        score_results_file = os.path.join(task_path, "score.csv")
        task_info_file = os.path.join(task_path, "taskInfo.csv")

        expected_output_files = [detail_scoring_results_file, score_binary_results_file, score_results_file, task_info_file]
        for file in expected_output_files:
            if not os.path.exists(file):
                raise Exception(f"Expected output file does not exist: {file}")

        (detail_scoring_dim, detail_scoring_data) = get_results(detail_scoring_results_file)
        (score_binary_dim, score_binary_data) = get_results(score_binary_results_file)
        (score_dim, score_data) = get_results(score_results_file)
        (task_info_dim, task_info_data) = get_results(task_info_file)

        return_object = {
            "submitter_id": parameters.submitter_id,
            "start_time": start_time,
            "end_time": end_time,
            "results": [
                {
                    "name": "detail_scoring",
                    "results_type": "filetype_results_CellFieDetailScoringTable",
                    "spec": "",
                    "dimension": detail_scoring_dim,
                    "data": detail_scoring_data
                },
                {
                    "name": "score_binary",
                    "results_type": "filetype_results_CellFieScoreBinaryTable",
                    "spec": "",
                    "dimension": score_binary_dim,
                    "data": score_binary_data
                },
                {
                    "name": "score",
                    "results_type": "filetype_results_CellFieScoreTable",
                    "spec": "",
                    "dimension": score_dim,
                    "data": score_data
                },
                {
                    "name": "task_info",
                    "results_type": "filetype_results_CellFieTaskInfoTable",
                    "spec": "",
                    "dimension": task_info_dim,
                    "data": task_info_data
                }
            ]}

        shutil.rmtree(task_path)

        return return_object

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=404,
                            detail="! Exception {0} occurred while running submit, message=[{1}] \n! traceback=\n{2}\n".format(type(e), e, traceback.format_exc()))


@app.get("/service-info", summary="Retrieve information about this service")
async def service_info():
    """
    Returns information similar to DRS service format

    Extends the v1.0.0 GA4GH Service Info specification as the standardized format for GA4GH web services to self-describe.

    According to the service-info type registry maintained by the Technical Alignment Sub Committee (TASC), a DRS service MUST have:
    - a type.group value of org.ga4gh
    - a type.artifact value of drs

    e.g.
    ```
    {
      "id": "com.example.drs",
      "description": "Serves data according to DRS specification",
      ...
      "type": {
        "group": "org.ga4gh",
        "artifact": "drs"
      }
    ...
    }
    ```
    """
    service_info_path = pathlib.Path(__file__).parent.parent / "resources" / "service_info.json"
    with open(service_info_path) as f:
        return json.load(f)
