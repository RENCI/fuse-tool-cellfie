import datetime
import logging
import os
import traceback
import uuid
from datetime import datetime
from logging.config import dictConfig
from typing import Optional
import csv
import docker
import aiofiles
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


@app.post("/submit", description="Submit an analysis")
async def analyze(submitter_id: str = Query(default=None, description="unique identifier for the submitter (e.g., email)"),
                  gene_expression_data: UploadFile = File(default=None, description="Gene Expression Data (csv)"),
                  phenotype_data: Optional[bytes] = File(default=None, description="Phenotype Data (csv)"),
                  parameters: Parameters = Depends(Parameters.as_form)):
    try:
        start_time = datetime.now()

        global_value = parameters.Percentile if parameters.PercentileOrValue == "percentile" else parameters.Value
        local_values = f"{parameters.PercentileLow} {parameters.PercentileHigh}" if parameters.PercentileOrValue == "percentile" else f"{parameters.ValueLow} {parameters.ValueHigh}"

        task_id = str(uuid.uuid4())[:8]
        task_path = os.path.abspath(f"/app/data/{task_id}")
        os.makedirs(task_path, exist_ok=True)

        param_path = os.path.join(task_path, "parameters.json")
        with open(param_path, 'w', encoding='utf-8') as f:
            f.write(parameters.json())
        f.close()

        file_path = os.path.join(task_path, "geneBySampleMatrix.csv")
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await gene_expression_data.read()
            await out_file.write(content)

        if phenotype_data is not None:
            phenotype_data_file_path = os.path.join(task_path, "phenoDataMatrix.csv")
            async with aiofiles.open(phenotype_data_file_path, 'wb') as out_file:
                await out_file.write(phenotype_data)

        image = "hmasson/cellfie-standalone-app:v2"
        volumes = {
            'cellfie-data': {'bind': '/data', 'mode': 'rw'},
            'cellfie-input-data': {'bind': '/input', 'mode': 'rw'},
        }
        command = f"/data/{task_id}/geneBySampleMatrix.csv {parameters.SampleNumber} {parameters.Ref} {parameters.ThreshType} {parameters.PercentileOrValue} {global_value} {parameters.LocalThresholdType} {local_values} /data"
        try:
            cellfie_container_logs = client.containers.run(image, volumes=volumes, name=task_id, working_dir="/input", privileged=True, remove=True, command=command)
            cellfie_container_logs_decoded = cellfie_container_logs.decode("utf8")
            logger.info(cellfie_container_logs_decoded)
        except ContainerError as err:
            logger.exception(err)

        end_time = datetime.now()
        duration = end_time-start_time
        logger.debug(msg=f"run duration: {divmod(duration.seconds, 60)}")

        detail_scoring_file = os.path.join(task_path, "detailScoring.csv")
        if not os.path.exists(detail_scoring_file):
            raise HTTPException(status_code=404, detail="Not found")
        detail_scoring_data = []
        feature_count = 0
        with open(detail_scoring_file, 'r') as csvfile:
            data = csvfile.readlines()
            for line in data:
                if feature_count == 0:
                    feature_count = len(line.split(','))
                detail_scoring_data.append(tuple(line.strip().split(',')))

# detailScoring.csv
# score.csv

        # return_object = AnalysisResults()
        return_object = {}
        return_object["submitter_id"] = submitter_id
        return_object["start_time"] = start_time
        return_object["end_time"] = end_time
        return_object["contents"] = [
            {
                "name": "Detail Scoring Table",
                "results_type": "CellFIE",
                "spec": "",
                "size": [len(detail_scoring_data), feature_count],
                "detailScoring": detail_scoring_data
            }
        ]

        return return_object

    except Exception as e:
        raise HTTPException(status_code=404,
                            detail="! Exception {0} occurred while running submit, message=[{1}] \n! traceback=\n{2}\n".format(type(e), e, traceback.format_exc()))
