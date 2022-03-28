import datetime
import inspect
import os

from pydantic import BaseModel
from typing import Type, Optional, List
from fastapi import File, UploadFile, Form, Depends, HTTPException, Query

import docker

from docker.errors import ContainerError
import traceback
from pydantic import BaseModel


def as_form(cls: Type[BaseModel]):
    new_params = [
        inspect.Parameter(
            field.alias,
            inspect.Parameter.POSITIONAL_ONLY,
            default=(Form(field.default) if not field.required else Form(...)),
        )
        for field in cls.__fields__.values()
    ]

    async def _as_form(**data):
        return cls(**data)

    sig = inspect.signature(_as_form)
    sig = sig.replace(parameters=new_params)
    _as_form.__signature__ = sig
    setattr(cls, "as_form", _as_form)
    return cls

class Contents(BaseModel):
    name: str="string"
    id: str="string"
    results_type: str="string"
    spec: str="string"
    size: List[int]
    contents: List[str] = [
        "string"
    ]

@as_form
class AnalysisResults(BaseModel):
    class_version: str="1"
    submitter_id: str=None
    name: str="Principal Component Analysis (PCA)"
    start_time: str=None
    end_time: str=None
    mime_type: str="application/json"
    contents: List[Contents] = [
        {
            "name": "PCA table",
            "results_type": "PCA",
            "spec": "",
            "size": [2, 3],
            "contents": [
                "gene1,1,2",
                "gene2,3,4"
            ]
        }
    ]
    description: str="Performs PCA on the input gene expression and returns a table with the requested number of principle components."
