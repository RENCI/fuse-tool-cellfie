import datetime
import inspect
import os

from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Query
from fastapi.logger import logger
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Type, Optional, List
from starlette.responses import StreamingResponse

from bson.json_util import dumps, loads
import docker

from docker.errors import ContainerError
import traceback


from fuse.models.Objects import AnalysisResults

from fastapi.logger import logger
from logging.config import dictConfig
import logging
from fuse.models.Config import LogConfig
dictConfig(LogConfig().dict())
logger = logging.getLogger("fuse-tool-template")

app = FastAPI()

origins = [
    f"http://{os.getenv('HOSTNAME')}:{os.getenv('HOSTPORT')}",
    f"http://{os.getenv('HOSTNAME')}",
    "http://localhost:{os.getenv('HOSTPORT')}",
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

import pathlib

import json
    
# API is described in:
# http://localhost:8083/openapi.json

# Therefore:
# This endpoint self-describes with:
# curl -X 'GET'    'http://localhost:8083/openapi.json' -H 'accept: application/json' 2> /dev/null |python -m json.tool |jq '.paths."/submit".post.parameters' -C |less
# for example, an array of parameter names can be retrieved with:
# curl -X 'GET'    'http://localhost:8083/openapi.json' -H 'accept: application/json' 2> /dev/null |python -m json.tool |jq '.paths."/submit".post.parameters[].name' 

from datetime import datetime
@app.post("/submit", description="Submit an analysis")
async def analyze(submitter_id: str = Query(default=None, description="unique identifier for the submitter (e.g., email)"),
                  number_of_components: int = Query(default=3, description="Number of principle components to return."),
                  gene_expression: UploadFile = File(...)):
    '''
    Gene expression data are formatted with gene id's on rows, and samples on columns. Gene expression counts/intensities will not be normalized as part of the analysis. No header row, comma-delimited.
    '''
    try:
        restul_type="FUSE:PCA" #can also be "FUSE:CellFIE"
        start_time=datetime.now()
        logger.info(msg=f"[submit] started: " + str(start_time))
        # do some analysis
        gene_expression_string = await gene_expression.read()
        import io
        gene_expression_stream = io.StringIO(str(gene_expression_string,'utf-8'))
        import pandas as pd
        import numpy as np
        gene_expression_df = pd.read_csv(gene_expression_stream, sep=",", dtype=np.float64)
        logger.info(msg=f"[submit] read input file.")
        from sklearn.decomposition import PCA
        df_pca = PCA(n_components=number_of_components)
        logger.info(msg=f"[submit] set up PCA.")
        df_principalComponents = df_pca.fit_transform(gene_expression_df)
        logger.info(msg=f"[submit] fit the transform.")
        pc_cols=[]
        for col in range(0,number_of_components):
            pc_cols.append('PC'+str(col +1))
        df_results = pd.DataFrame(data = df_principalComponents,
                                      columns = pc_cols)
        logger.info(msg=f"[submit] added PC column names.")
        results = df_results.values.tolist()
        logger.info(msg=f"[submit] transformed to list.")
        # analysis finished.
        end_time=datetime.now()
        logger.info(msg=f"[submit] ended: " + str(end_time))
        # xxx come back to this
        #return_object = AnalysisResults()
        return_object={}
        return_object["submitter_id"]= submitter_id
        return_object["start_time"] = start_time
        return_object["end_time"] = end_time
        return_object["contents"]= [
            {
                "name": "PCA table",
                "results_type": "PCA",
                "spec": "",
                "size": [len(results), number_of_components],
                "contents": results
            }
        ]

        logger.info(msg=f"[submit] returning: " + str(return_object))
        #return return_object.dict()
        # xxx
        return return_object
    except Exception as e:
        raise HTTPException(status_code=404,
                            detail="! Exception {0} occurred while running submit, message=[{1}] \n! traceback=\n{2}\n".format(type(e), e, traceback.format_exc()))

