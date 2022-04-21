import inspect
from enum import Enum
from typing import Type, List, Optional

from fastapi import Form
from pydantic import BaseModel, EmailStr, Field, AnyHttpUrl


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
class ToolParameters(BaseModel):
    service_id: str
    submitter_id: EmailStr = Field(..., title="email", description="unique submitter id (email)")
    number_of_components: Optional[int] = 3
    reference_model: Optional[ReferenceModel] = ReferenceModel.MT_recon_2_2_entrez
    threshold_type: Optional[str] = "local"
    percentile_or_value: Optional[str] = "value"
    percentile: Optional[int] = 25
    value: Optional[int] = 5
    local_threshold_type: Optional[str] = "minmaxmean"
    percentile_low: Optional[int] = 25
    percentile_high: Optional[int] = 75
    value_low: Optional[int] = 5
    value_high: Optional[int] = 5
    dataset: str = Field(...)
    description: Optional[str] = Field(None, title="Description", description="detailed description of the requested analysis being performed (optional)")
    expression_url: Optional[AnyHttpUrl] = Field(None, title="Gene expression URL", description="Optionally grab expression from an URL instead of uploading a file")
    properties_url: Optional[AnyHttpUrl] = Field(None, title="Properties URL", description="Optionally grab properties from an URL instead of uploading a file")
    archive_url: Optional[AnyHttpUrl] = Field(None, title="Archive URL", description="Optionally grab all the files from an URL to an archive instead of uploading file(s)")
    results_provider_service_id: Optional[str] = Field(None, title="Data Provider for Results",
                                                       description="If not set, the system default will be provided. e.g., 'fuse-provider-upload'")


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
