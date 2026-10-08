import logging

from app.config import get_settings
from app.schemas import UserInput

logger = logging.getLogger(__name__)

GOAL_LABELS = {
    "weight_loss": "fat loss and cardiovascular fitness",
    "muscle_gain": "strength and muscle gain",
    "general_wellness": "general wellness and consistent movement",
    "flexibility": "mobility and flexibility",
}


def _client():
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai

        return genai.Client(api_key=settings.gemini_api_key)
    except Exception as exc:  # SDK configuration can vary by local installation.
        logger.exception("Could not initialize Gemini client")
        raise RuntimeError("Gemini could not be initialized. Check your SDK installation and API key.") from exc


def _generate(prompt: str, model: str, fallback: str) -> tuple[str, str]:
    settings = get_settings()
    client = _client()
    if client is None:
        if settings.allow_demo_ai:
            return fallback, "demo"
        raise RuntimeError("Add GEMINI_API_KEY to your .env file to enable AI generation.")
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        result = (response.text or "").strip()
        if not result:
            raise RuntimeError("Gemini returned an empty response. Please try again.")
        return result, "gemini"
    except RuntimeError:
        raise
    except Exception as exc:
        logger.exception("Gemini generation failed")
        if settings.allow_demo_ai:
            return fallback + "\n\n(Demo plan shown because Gemini was temporarily unavailable.)", "demo"
        raise RuntimeError("Gemini could not generate a response. Check your key, quota, and model settings.") from exc


def _fallback_plan(profile: UserInput) -> str:
    target = GOAL_LABELS[profile.goal]
    days = [
        ("Day 1 - Full body strength", "Chair or goblet squats 3×8-10; incline push-ups 3×8; backpack rows 3×10; easy walk 10 minutes."),
        ("Day 2 - Cardio and mobility", "Brisk walk or cycling 20-30 minutes at a conversational pace; gentle hip and shoulder mobility 8 minutes."),
        ("Day 3 - Lower body and core", "Hip hinges 3×10; reverse lunges 2×8 each side; glute bridges 3×12; dead bug 2×8 each side."),
        ("Day 4 - Recovery", "Rest or take an easy 15-20 minute walk. Finish with comfortable full-body stretching."),
        ("Day 5 - Upper body and core", "Wall or incline push-ups 3×8-12; backpack rows 3×10; shoulder taps 2×8 each side; side plank 2×15 seconds each side."),
        ("Day 6 - Goal-focused movement", "Choose a low-impact activity you enjoy for 20-30 minutes, then do 5 minutes of relaxed mobility."),
        ("Day 7 - Rest and reflect", "Take a full rest day. Note what felt comfortable and what you would like to adjust next week."),
    ]
    if profile.intensity == "low":
        days = [(title, detail.replace("3×", "2×").replace("20-30", "15-20")) for title, detail in days]
    elif profile.intensity == "high":
        days[1] = (days[1][0], "Warm up 5 minutes, then alternate 2 minutes brisk / 2 minutes easy for 20 minutes. Keep the effort controlled.")
        days[5] = (days[5][0], "Choose a goal-focused activity for 30-40 minutes at a challenging but controlled effort; stop if form or comfort declines.")
    if profile.goal == "flexibility":
        days[5] = ("Day 6 - Mobility flow", "Move gently through cat-cow, supported lunge, hamstring stretch, thoracic rotations, and ankle rocks. Hold each comfortable position 20-30 seconds; no bouncing.")
    return (
        f"7-DAY STARTER PLAN — {target}\n"
        f"Profile: age {profile.age}, {profile.weight_kg:g} kg, {profile.intensity} intensity.\n\n"
        + "\n\n".join(f"{title}\nWarm-up: 5 minutes of easy movement.\nMain session: {detail}\nCool-down: 3-5 minutes of easy movement and comfortable stretching." for title, detail in days)
        + "\n\nChoose loads that let you keep good form, rest 60-90 seconds between strength sets, and stop for pain, dizziness, or unusual shortness of breath."
    )


def generate_workout(profile: UserInput) -> tuple[str, str]:
    goal = GOAL_LABELS[profile.goal]
    prompt = f"""Create a safe, practical seven-day beginner-friendly exercise plan for this adult.
Name: {profile.username}; age: {profile.age}; weight: {profile.weight_kg:g} kg; goal: {goal}; preferred intensity: {profile.intensity}.
Give every day a clear focus, warm-up, exercises with sets/reps or duration, rest guidance, and cool-down/recovery. Include at least one recovery day. Adapt volume to the intensity. Avoid diagnosing, weight-loss promises, calorie prescriptions, or extreme exercise. Add a short safety note to stop for pain or concerning symptoms. Format as plain text with headings for Day 1 through Day 7."""
    return _generate(prompt, get_settings().gemini_workout_model, _fallback_plan(profile))


def generate_tip(profile: UserInput) -> tuple[str, str]:
    goal = GOAL_LABELS[profile.goal]
    fallback = {
        "weight_loss": "Build meals around vegetables, a satisfying protein source, and high-fiber foods; keep hydration steady and choose changes you can sustain.",
        "muscle_gain": "Include a protein-rich food in regular meals and have a balanced meal or snack after training; sleep and recovery support strength progress.",
        "general_wellness": "Drink water regularly, eat a varied mix of minimally processed foods, and protect a consistent sleep routine to support recovery.",
        "flexibility": "Stay hydrated and pair mobility work with regular meals and adequate sleep; move into stretches gently and never force a painful range.",
    }[profile.goal]
    prompt = f"Write one concise, practical nutrition or recovery tip for an adult whose exercise goal is {goal}. Avoid medical claims, restrictive diets, supplement prescriptions, calorie targets, and individualized medical advice. Maximum 55 words."
    return _generate(prompt, get_settings().gemini_tip_model, fallback)


def revise_workout(profile: UserInput, current_plan: str, feedback: str) -> tuple[str, str]:
    prompt = f"""Revise this seven-day exercise plan based on the user's feedback. Keep it practical and safe, preserve rest/recovery and warm-up/cool-down, and state when a request should be adjusted for safety.
Goal: {GOAL_LABELS[profile.goal]}; intensity: {profile.intensity}.
CURRENT PLAN:\n{current_plan[:12000]}\n\nUSER FEEDBACK:\n{feedback[:1000]}\n\nReturn the complete revised plan with Day 1 through Day 7 headings. Do not diagnose or promise results."""
    fallback = current_plan + f"\n\nDEMO REVISION NOTE\nRequested change: {feedback}\nApply this preference by adjusting the relevant sessions while keeping at least one recovery day and stopping if activity causes pain."
    return _generate(prompt, get_settings().gemini_workout_model, fallback)

