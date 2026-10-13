from typing import Optional

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    name: str
    email: str


class TokenOut(BaseModel):
    token: str
    user: UserOut


class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str
    password: str = Field(min_length=6, max_length=80)


class MaterialOut(BaseModel):
    code: str
    name: str
    full_name: str
    category: str
    object_name: str
    container: str
    container_detail: str
    steps: list[str]
    primary_action: str
    recyclable: bool
    weight_kg: float
    co2_kg: float
    accent: str
    tone: str
    warning: str
    blurb: str


class ScanIn(BaseModel):
    material_code: str = Field(min_length=2, max_length=8)
    object_name: str = Field(min_length=2, max_length=80)
    confidence: float = Field(ge=0, le=1)
    separated_well: bool = True


class ScanOut(BaseModel):
    id: int
    material_code: str
    material_name: str
    full_name: str
    category: str
    object_name: str
    confidence: float
    container: str
    container_detail: str
    tone: str
    steps: list[str]
    primary_action: str
    points: int
    weight_kg: float
    co2_kg: float
    created_at: str
    separated_well: bool
    accent: str
    warning: str
    recyclable: bool


class DayCount(BaseModel):
    label: str
    count: int
    is_today: bool


class CategoryCount(BaseModel):
    name: str
    count: int
    percent: int
    color: str


class ImpactOut(BaseModel):
    total: int
    well_percent: int
    today: int
    last7: int
    previous7: int
    night: int
    week_change_percent: int
    points: int
    weight_kg: float
    co2_kg: float
    weekly: list[DayCount]
    categories: list[CategoryCount]
    recent: list[ScanOut]


class ScoreOut(BaseModel):
    code: str
    score: float


class BBoxOut(BaseModel):
    x: float
    y: float
    w: float
    h: float


class GuideOut(BaseModel):
    meaning: str
    destination: str
    actions: list[str]
    tip: str


class AnalyzeOut(BaseModel):
    material_code: str
    object_name: str
    confidence: float
    bbox: BBoxOut
    inference_ms: float
    engine: str
    scores: list[ScoreOut]
    container: str
    full_name: str
    guide: Optional[GuideOut] = None


class MessageOut(BaseModel):
    detail: Optional[str] = None
