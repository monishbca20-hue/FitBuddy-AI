from typing import Literal

from pydantic import BaseModel, Field


Goal = Literal["weight_loss", "muscle_gain", "general_wellness", "flexibility"]
Intensity = Literal["low", "medium", "high"]


class UserInput(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    user_id: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    age: int = Field(ge=16, le=100)
    weight_kg: float = Field(gt=25, le=350)
    goal: Goal
    intensity: Intensity


class FeedbackInput(BaseModel):
    feedback: str = Field(min_length=5, max_length=1000)


class PlanResponse(BaseModel):
    user_id: str
    username: str
    goal: str
    intensity: str
    workout_plan: str
    nutrition_tip: str
    mode: str

