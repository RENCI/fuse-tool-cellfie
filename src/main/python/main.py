import datetime
import logging
import os
import shutil
import traceback
import uuid
from datetime import datetime
from logging.config import dictConfig

import aiofiles
import docker
from docker.errors import ContainerError
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from fuse.models.Objects import Parameters

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

app = FastAPI()

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


def get_results(task_path: str, file_name: str):
    results_file = os.path.join(task_path, file_name)
    logger.info(f"reading: {results_file}")
    if not os.path.exists(results_file):
        raise HTTPException(status_code=404, detail="Not found")
    results_data = []
    results_feature_count = 0
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
async def analyze(submitter_id: str = Query(default=..., description="unique identifier for the submitter (e.g., email)"),
                  gene_expression_data: UploadFile = File(default=None, description="Gene Expression Data (csv)"),
                  parameters: Parameters = Depends(Parameters.as_form)):
    logger.debug(msg=f"submitter_id: {submitter_id}")
    try:
        start_time = datetime.now()

        global_value = parameters.Percentile if parameters.PercentileOrValue == "percentile" else parameters.Value
        local_values = f"{parameters.PercentileLow} {parameters.PercentileHigh}" if parameters.PercentileOrValue == "percentile" else f"{parameters.ValueLow} {parameters.ValueHigh}"

        task_id = str(uuid.uuid4())[:8]
        task_path = os.path.abspath(f"/app/data/{task_id}")
        os.makedirs(task_path, exist_ok=False)

        param_path = os.path.join(task_path, "parameters.json")
        with open(param_path, 'w', encoding='utf-8') as f:
            f.write(parameters.json())
        f.close()

        file_path = os.path.join(task_path, "geneBySampleMatrix.csv")
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await gene_expression_data.read()
            await out_file.write(content)

        image = "hmasson/cellfie-standalone-app:v2"

        volumes = {}
        found_input_volume = list(filter(lambda x: x.name == "cellfie-input-data", client.volumes.list()))
        if len(found_input_volume) == 0 and os.environ.get("CELLFIE_INPUT_PATH") is not None:
            volumes = {
                'cellfie-data': {'bind': '/data', 'mode': 'rw'},
                f"{os.getenv('CELLFIE_INPUT_PATH')}": {'bind': '/input', 'mode': 'rw'},
            }
        else:
            volumes = {
                'cellfie-data': {'bind': '/data', 'mode': 'rw'},
                'cellfie-input-data': {'bind': '/input', 'mode': 'rw'},
            }
        logger.info(f"{volumes}")
        command = f"/data/{task_id}/geneBySampleMatrix.csv {parameters.SampleNumber} {parameters.Ref} {parameters.ThreshType} {parameters.PercentileOrValue} {global_value} {parameters.LocalThresholdType} {local_values} /data/{task_id}"
        try:
            cellfie_container_logs = client.containers.run(image, volumes=volumes, name=task_id, working_dir="/input", privileged=True, remove=True, command=command, detach=False)
            cellfie_container_logs_decoded = cellfie_container_logs.decode("utf8")
            logger.info(cellfie_container_logs_decoded)
        except ContainerError as err:
            logger.exception(err)

        end_time = datetime.now()
        duration = end_time - start_time
        logger.debug(msg=f"run duration: {divmod(duration.seconds, 60)}")

        (detail_scoring_dim, detail_scoring_data) = get_results(task_path=task_path, file_name="detailScoring.csv")
        (score_binary_dim, score_binary_data) = get_results(task_path=task_path, file_name="score_binary.csv")
        (score_dim, score_data) = get_results(task_path=task_path, file_name="score.csv")
        (task_info_dim, task_info_data) = get_results(task_path=task_path, file_name="taskInfo.csv")

        return_object = {"submitter_id": submitter_id, "start_time": start_time, "end_time": end_time, "results": [
            {
                "name": "Detail Scoring",
                "results_type": "CellFIE",
                "spec": "",
                "dimension": detail_scoring_dim,
                "data": detail_scoring_data
            },
            {
                "name": "Score Binary",
                "results_type": "CellFIE",
                "spec": "",
                "dimension": score_binary_dim,
                "data": score_binary_data
            },
            {
                "name": "Score",
                "results_type": "CellFIE",
                "spec": "",
                "dimension": score_dim,
                "data": score_data
            },
            {
                "name": "Detail Scoring Table",
                "results_type": "CellFIE",
                "spec": "",
                "dimension": task_info_dim,
                "data": task_info_data
            }
        ]}

        shutil.rmtree(task_path)

        return return_object

    except Exception as e:
        raise HTTPException(status_code=404,
                            detail="! Exception {0} occurred while running submit, message=[{1}] \n! traceback=\n{2}\n".format(type(e), e, traceback.format_exc()))
