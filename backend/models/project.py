from pydantic import BaseModel, Field
from typing import List


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ProjectResponse(BaseModel):
    uuid: str
    name: str
    state: str
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
