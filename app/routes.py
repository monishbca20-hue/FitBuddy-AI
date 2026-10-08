import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.database import get_db
from app.models import User, WorkoutPlan
from app.schemas import FeedbackInput, Goal, Intensity, UserInput
from app.services.ai import generate_tip, generate_workout, revise_workout

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
Db = Annotated[Session, Depends(get_db)]


def _user_schema(user: User) -> UserInput:
    return UserInput(
        username=user.username, user_id=user.user_id, age=user.age,
        weight_kg=user.weight_kg, goal=user.goal, intensity=user.intensity,
    )


def _profile_context(profile: UserInput, plan: str, tip: str, mode: str, request: Request, updated: bool = False):
    return {
        "request": request, "profile": profile, "workout_plan": plan,
        "nutrition_tip": tip, "mode": mode, "updated": updated,
        "goal_label": profile.goal.replace("_", " ").title(),
    }


def _friendly_error(request: Request, message: str, code: int = 400):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"error": message}, status_code=code
    )


@router.get("/", response_class=HTMLResponse, name="home")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@router.post("/generate-workout", response_class=HTMLResponse, name="generate_workout_form")
async def generate_workout_form(
    request: Request,
    username: Annotated[str, Form(min_length=2, max_length=80)],
    user_id: Annotated[str, Form(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")],
    age: Annotated[int, Form(ge=16, le=100)],
    weight_kg: Annotated[float, Form(gt=25, le=350)],
    goal: Annotated[Goal, Form()],
    intensity: Annotated[Intensity, Form()],
    db: Db,
):
    profile = UserInput(username=username.strip(), user_id=user_id.strip(), age=age, weight_kg=weight_kg, goal=goal, intensity=intensity)
    try:
        (plan, plan_mode), (tip, tip_mode) = await run_in_threadpool(
            lambda: (generate_workout(profile), generate_tip(profile))
        )
    except RuntimeError as exc:
        return _friendly_error(request, str(exc), 503)

    user = db.scalar(select(User).where(User.user_id == profile.user_id))
    if user is None:
        user = User(user_id=profile.user_id, username=profile.username, age=age, weight_kg=weight_kg, goal=goal, intensity=intensity)
        db.add(user)
    else:
        user.username, user.age, user.weight_kg = profile.username, age, weight_kg
        user.goal, user.intensity = goal, intensity
    db.flush()
    record = WorkoutPlan(user_id=user.id, original_plan=plan, nutrition_tip=tip)
    db.add(record)
    db.commit()
    return templates.TemplateResponse(
        request=request, name="result.html",
        context=_profile_context(profile, plan, tip, "Gemini" if "gemini" in (plan_mode, tip_mode) else "Demo", request),
    )


@router.post("/submit-feedback", response_class=HTMLResponse, name="submit_feedback_form")
async def submit_feedback_form(
    request: Request,
    user_id: Annotated[str, Form(min_length=3, max_length=40)],
    feedback: Annotated[str, Form(min_length=5, max_length=1000)],
    db: Db,
):
    record = db.scalar(
        select(WorkoutPlan).join(User).where(User.user_id == user_id.strip()).order_by(WorkoutPlan.created_at.desc(), WorkoutPlan.id.desc())
    )
    if record is None:
        return _friendly_error(request, "We couldn't find a plan for that user ID. Generate a plan first.", 404)
    profile = _user_schema(record.user)
    try:
        plan, mode = await run_in_threadpool(revise_workout, profile, record.updated_plan or record.original_plan, feedback.strip())
        tip, tip_mode = await run_in_threadpool(generate_tip, profile)
    except RuntimeError as exc:
        return _friendly_error(request, str(exc), 503)
    from datetime import datetime, timezone
    record.updated_plan = plan
    record.feedback = feedback.strip()
    record.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    record.nutrition_tip = tip
    db.commit()
    return templates.TemplateResponse(
        request=request, name="result.html",
        context=_profile_context(profile, plan, tip, "Gemini" if "gemini" in (mode, tip_mode) else "Demo", request, updated=True),
    )


def _authorize_admin(token: str | None, header_token: str | None) -> None:
    expected = get_settings().admin_token
    if expected and (token or header_token) != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid admin token is required.")


@router.get("/view-all-users", response_class=HTMLResponse, name="view_all_users")
def view_all_users(request: Request, db: Db, token: str | None = Query(default=None), x_admin_token: str | None = Header(default=None)):
    _authorize_admin(token, x_admin_token)
    users = db.scalars(select(User).options(selectinload(User.plans)).order_by(User.created_at.desc())).all()
    return templates.TemplateResponse(request=request, name="all_users.html", context={"users": users, "admin_token": token or x_admin_token})


@router.post("/admin/users/{user_id}/delete")
def delete_user_form(user_id: str, db: Db, token: str = Query(...)):
    _authorize_admin(token, None)
    user = db.scalar(select(User).where(User.user_id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    db.delete(user)
    db.commit()
    return RedirectResponse(url=f"/view-all-users?token={token}", status_code=303)


@router.get("/api/health")
def health():
    return {"status": "ok", "ai_mode": "gemini" if get_settings().gemini_api_key else "demo"}


@router.post("/api/plans", status_code=201)
async def create_plan_api(payload: UserInput, db: Db):
    try:
        (plan, plan_mode), (tip, tip_mode) = await run_in_threadpool(lambda: (generate_workout(payload), generate_tip(payload)))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    user = db.scalar(select(User).where(User.user_id == payload.user_id))
    if user is None:
        user = User(user_id=payload.user_id, username=payload.username, age=payload.age, weight_kg=payload.weight_kg, goal=payload.goal, intensity=payload.intensity)
        db.add(user)
    else:
        user.username, user.age, user.weight_kg = payload.username, payload.age, payload.weight_kg
        user.goal, user.intensity = payload.goal, payload.intensity
    db.flush()
    record = WorkoutPlan(user_id=user.id, original_plan=plan, nutrition_tip=tip)
    db.add(record)
    db.commit()
    return {"user_id": user.user_id, "plan_id": record.id, "workout_plan": plan, "nutrition_tip": tip, "mode": "gemini" if "gemini" in (plan_mode, tip_mode) else "demo"}


@router.post("/api/plans/{user_id}/feedback")
async def update_plan_api(user_id: str, payload: FeedbackInput, db: Db):
    record = db.scalar(select(WorkoutPlan).join(User).where(User.user_id == user_id).order_by(WorkoutPlan.id.desc()))
    if record is None:
        raise HTTPException(status_code=404, detail="No plan found for this user ID.")
    try:
        plan, mode = await run_in_threadpool(revise_workout, _user_schema(record.user), record.updated_plan or record.original_plan, payload.feedback)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    from datetime import datetime
    record.updated_plan, record.feedback = plan, payload.feedback
    record.updated_at = datetime.utcnow()
    db.commit()
    return {"user_id": user_id, "plan_id": record.id, "updated_plan": plan, "mode": mode}


@router.get("/api/plans/{user_id}")
def get_user_plans(user_id: str, db: Db):
    user = db.scalar(select(User).options(selectinload(User.plans)).where(User.user_id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return {
        "user_id": user.user_id,
        "username": user.username,
        "plans": [{"id": plan.id, "original_plan": plan.original_plan, "updated_plan": plan.updated_plan, "feedback": plan.feedback, "nutrition_tip": plan.nutrition_tip} for plan in user.plans],
    }


@router.get("/api/admin/users")
def get_all_users_api(db: Db, x_admin_token: str | None = Header(default=None)):
    _authorize_admin(None, x_admin_token)
    users = db.scalars(select(User).options(selectinload(User.plans)).order_by(User.created_at.desc())).all()
    return [{"user_id": user.user_id, "username": user.username, "age": user.age, "weight_kg": user.weight_kg, "goal": user.goal, "intensity": user.intensity,
             "plans": [{"id": plan.id, "original_plan": plan.original_plan, "updated_plan": plan.updated_plan, "feedback": plan.feedback} for plan in user.plans]} for user in users]


@router.delete("/api/admin/users/{user_id}", status_code=204)
def delete_user_api(user_id: str, db: Db, x_admin_token: str | None = Header(default=None)):
    _authorize_admin(None, x_admin_token)
    user = db.scalar(select(User).where(User.user_id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    db.delete(user)
    db.commit()

