import inspect
from enum import Enum
from typing import Type, List, Optional

from fastapi import Form
from pydantic import BaseModel, EmailStr, Field, AnyHttpUrl
from fuse_utilities.main import as_form, ToolParameters, ReferenceModel
