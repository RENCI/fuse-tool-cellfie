import inspect
from enum import Enum
from typing import Type, List

from fastapi import Form
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


class ReferenceModel(str, Enum):
    MT_iCHOv1_final = "MT_iCHOv1_final.mat"
    MT_iHsa = "MT_iHsa.mat"
    MT_iMM1415 = "MT_iMM1415.mat"
    MT_inesMouseModel = "MT_inesMouseModel.mat"
    MT_iRno = "MT_iRno.mat"
    MT_quek14 = "MT_quek14.mat"
    MT_recon_1 = "MT_recon_1.mat"
    MT_recon_2 = "MT_recon_2.mat"
    MT_recon_2_2_entrez = "MT_recon_2_2_entrez.mat"


@as_form
class Parameters(BaseModel):
    Ref: ReferenceModel = ReferenceModel.MT_recon_2_2_entrez
    ThreshType: str = "local"
    PercentileOrValue: str = "value"
    Percentile: int = 25
    Value: int = 5
    LocalThresholdType: str = "minmaxmean"
    PercentileLow: int = 25
    PercentileHigh: int = 75
    ValueLow: int = 5
    ValueHigh: int = 5


class Contents(BaseModel):
    name: str = "string"
    id: str = "string"
    results_type: str = "string"
    spec: str = "string"
    size: List[int]
    contents: List[str] = [
        "string"
    ]


@as_form
class AnalysisResults(BaseModel):
    class_version: str = "1"
    submitter_id: str = None
    name: str = "Principal Component Analysis (PCA)"
    start_time: str = None
    end_time: str = None
    mime_type: str = "application/json"
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
    description: str = "Performs PCA on the input gene expression and returns a table with the requested number of principle components."
