from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


class MemberCreate(BaseModel):
    email: EmailStr


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    email: str
    created_at: datetime
