import logging
import os
import streamlit as st
from dotenv import load_dotenv
from google import genai

load_dotenv()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="FitBuddy AI | Fitness Planner",
    page_icon="🏋️",
    layout="wide",
)

st.markdown(
    """
    <style>
        :root {
            --bg: #f3f7ee;
            --panel: rgba(255, 255, 255, 0.82);
            --panel-strong: #ffffff;
            --text: #17251d;
            --muted: #627368;
            --accent: #2c7a4a;
            --accent-soft: #dff4e7;
            --highlight: #d8ee88;
            --border: rgba(23, 37, 29, 0.08);
            --shadow: 0 16px 40px rgba(16, 34, 25, 0.12);
        }

        html, body, [data-testid="stAppViewContainer"] {
            background: linear-gradient(135deg, #edf5e9 0%, #f9faf5 45%, #f2f7ed 100%);
            color: var(--text);
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }

        .hero-card {
            background: linear-gradient(135deg, rgba(44,122,74,0.98), rgba(32,87,58,0.94));
            border-radius: 26px;
            padding: 2rem 2.2rem;
            box-shadow: var(--shadow);
            color: white;
            margin-bottom: 1.2rem;
        }

        .hero-title {
            font-size: 2.8rem;
            font-weight: 800;
            line-height: 1.05;
            margin: 0;
        }

        .hero-subtitle {
            font-size: 1.1rem;
            color: rgba(255,255,255,0.86);
            margin-top: 0.8rem;
            max-width: 700px;
        }

        .glass-card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 22px;
            box-shadow: var(--shadow);
            padding: 1.3rem 1.2rem;
            backdrop-filter: blur(10px);
        }

        .small-label {
            font-size: 0.72rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--muted);
            font-weight: 700;
        }

        .metric-box {
            background: linear-gradient(180deg, #fbfdf8 0%, #f2f9ec 100%);
            border: 1px solid #dfeeda;
            border-radius: 18px;
            padding: 1rem 1.1rem;
            margin-top: 0.5rem;
        }

        .metric-value {
            font-size: 1.5rem;
            font-weight: 800;
            color: var(--text);
            margin: 0.25rem 0;
        }

        .plan-section {
            background: white;
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 1.3rem 1.4rem;
            box-shadow: var(--shadow);
            margin-top: 1.1rem;
        }

        [data-testid="stSidebar"] {
            background: rgba(255,255,255,0.68);
            backdrop-filter: blur(10px);
        }

        div[data-testid="stSidebarNav"] {
            display: none;
        }

        .stButton > button {
            background: linear-gradient(135deg, #2d7d4d 0%, #204f38 100%);
            color: white;
            border: none;
            border-radius: 14px;
            padding: 0.8rem 1.2rem;
            font-weight: 700;
            width: 100%;
            transition: transform 0.2s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            filter: brightness(1.03);
        }

        .stSelectbox label, .stNumberInput label, .stRadio label {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text);
            letter-spacing: 0.02em;
        }

        .stMarkdown h3 {
            margin-top: 0;
            color: var(--text);
        }

        .success-box {
            background: #ecf9ee;
            border: 1px solid #cfeecf;
            border-radius: 14px;
            padding: 0.8rem 1rem;
            color: #235d39;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def build_prompt(name, weight, goal, activity, age, experience, focus):
    return f"""
    Create a safe, practical seven-day exercise plan. Do not diagnose conditions,
    promise results, prescribe calories, or recommend extreme exercise.

    User details:
    - Name: {name}
    - Age: {age}
    - Weight: {weight} kg
    - Goal: {goal}
    - Activity level: {activity}
    - Experience: {experience}
    - Main focus: {focus}

    Create a practical 7-day fitness plan with:
    1. A short overview
    2. Daily workout schedule for all 7 days
    3. General, balanced nutrition guidance (no calorie targets or restrictive diets)
    4. A realistic daily movement target
    5. Recovery and sleep advice, including at least one rest day
    6. A simple weekly checklist

    Keep it encouraging and easy to follow. Use headings and bullet points.
    Include warm-ups and cool-downs, and advise stopping for pain or concerning symptoms.
    """


def generate_content(api_key, model, prompt):
    client = genai.Client(api_key=api_key)
    try:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return response, model
        except Exception as exc:
            if getattr(exc, "code", None) != 503 or model == "gemini-3.1-flash-lite":
                raise
            logger.warning("Gemini model %s is overloaded; retrying with gemini-3.1-flash-lite", model)
            response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
            return response, "gemini-3.1-flash-lite"
    finally:
        client.close()


def explain_gemini_error(error, api_key):
    code = getattr(error, "code", None)
    message = str(error).replace(api_key, "[redacted]")
    if code == 400 or code == 401:
        cause = "Gemini rejected the request. Check that the API key is correct and active."
    elif code == 403:
        cause = "This API key or Google Cloud project is not allowed to use Gemini. Check API access and billing/project restrictions."
    elif code == 404:
        cause = "The selected Gemini model was not found or is unavailable to this API project. Choose an enabled model."
    elif code == 429:
        cause = "The Gemini API quota or request rate limit was reached. Check quota in Google AI Studio and retry later."
    elif code == 503:
        cause = "The selected Gemini model is temporarily overloaded. Retry shortly or select another available model."
    elif isinstance(error, (TimeoutError, ConnectionError)):
        cause = "The request could not reach Gemini. Check your internet connection and retry."
    else:
        cause = "Gemini generation failed. The diagnostic below may explain why."
    return cause, message[:2000]


st.markdown(
    """
    <div class="hero-card">
        <div class="small-label" style="color: rgba(255,255,255,0.75); margin-bottom: 0.6rem;">Personal training assistant</div>
        <h1 class="hero-title">FitBuddy AI</h1>
        <p class="hero-subtitle">Build a smart, realistic 7-day fitness plan around your body, your goal, and your current energy level.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Gemini connection")
    configured_key = os.getenv("GEMINI_API_KEY", "").strip()
    api_key = st.text_input(
        "Google AI Studio API key",
        value=configured_key,
        type="password",
        help="Kept in this session only if entered here. For a persistent setup, add it to the project .env file.",
    ).strip()
    model = st.text_input(
        "Gemini model",
        value=os.getenv("GEMINI_WORKOUT_MODEL", "gemini-3-flash-preview"),
        help="Change this to a model ID enabled for your Google AI Studio project.",
    ).strip()
    if api_key:
        st.success("API key is configured. Generate a plan to verify access.")
    else:
        st.warning("Add a Gemini API key to generate AI plans.")
        st.markdown("[Get a key from Google AI Studio](https://aistudio.google.com/app/apikey)")
    st.caption("Your key is not saved by this app when entered here.")
    test_connection = st.button("Test Gemini connection", disabled=not api_key or not model)
    if test_connection:
        try:
            with st.spinner("Testing the Gemini connection..."):
                response, used_model = generate_content(
                    api_key, model, "Reply with exactly: FitBuddy connection test passed."
                )
            if (response.text or "").strip():
                st.success(f"Gemini connection works with {used_model}.")
            else:
                st.error("Gemini connected, but returned an empty response.")
        except Exception as exc:
            logger.exception("Gemini connection test failed")
            cause, details = explain_gemini_error(exc, api_key)
            st.error(cause)
            with st.expander("Technical details"):
                st.code(details or type(exc).__name__)

left_column, right_column = st.columns([1.6, 1.1])

with left_column:
    with st.container():
        st.markdown('<div class="glass-card"><div class="small-label">Your profile</div></div>', unsafe_allow_html=True)
        st.write("")

        with st.form("fitness_form"):
            name = st.text_input("Name", value="Alex")
            age = st.number_input("Age", min_value=16, max_value=100, value=28)
            weight = st.number_input("Weight (kg)", min_value=20, max_value=300, value=70)
            goal = st.selectbox(
                "Fitness Goal",
                ["Weight Loss", "Muscle Gain", "General Fitness", "Flexibility & Mobility"],
            )
            activity = st.selectbox(
                "Current Activity Level",
                ["Beginner", "Intermediate", "Advanced"],
            )
            experience = st.selectbox(
                "Workout Experience",
                ["No regular exercise", "1-3 workouts/week", "3-5 workouts/week"],
            )
            focus = st.text_input(
                "Main focus",
                value="Improve energy and consistency",
                help="Example: build strength, reduce stress, feel more active, improve posture",
            )

            submitted = st.form_submit_button("Generate Fitness Plan")

    if submitted:
        st.session_state.pop("fitbuddy_plan", None)
        st.session_state.pop("fitbuddy_plan_name", None)
        st.session_state.pop("fitbuddy_plan_model", None)
        if not name.strip():
            st.error("Enter your name before generating a plan.")
        elif not api_key:
            st.error(
                "Gemini is not configured. Enter an API key in the sidebar, "
                "or add GEMINI_API_KEY=your_key to the project .env file and restart the app."
            )
        elif not model:
            st.error("Enter a Gemini model ID in the sidebar.")
        else:
            try:
                with st.spinner("Connecting to Gemini and creating your plan..."):
                    response, used_model = generate_content(
                        api_key,
                        model,
                        build_prompt(name.strip(), weight, goal, activity, age, experience, focus),
                    )
                    plan_text = (response.text or "").strip()

                if not plan_text:
                    st.error("Gemini returned an empty response. Please try again.")
                else:
                    st.session_state["fitbuddy_plan"] = plan_text
                    st.session_state["fitbuddy_plan_name"] = name.strip()
                    st.session_state["fitbuddy_plan_model"] = used_model
            except Exception as exc:
                logger.exception("Gemini plan generation failed")
                cause, details = explain_gemini_error(exc, api_key)
                st.error(cause)
                with st.expander("Technical details"):
                    st.code(details or type(exc).__name__)

    if st.session_state.get("fitbuddy_plan"):
        st.success(f"Your personalized plan is ready (generated with {st.session_state['fitbuddy_plan_model']}).")
        st.subheader(f"Coach plan for {st.session_state['fitbuddy_plan_name']}")
        st.markdown(st.session_state["fitbuddy_plan"])

with right_column:
    st.markdown('<div class="glass-card"><div class="small-label">Quick overview</div></div>', unsafe_allow_html=True)
    st.write("")

    col1, col2 = st.columns(2)
    col1.markdown(
        f"""
        <div class="metric-box">
            <div class="small-label">Goal</div>
            <div class="metric-value">{goal}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"""
        <div class="metric-box">
            <div class="small-label">Level</div>
            <div class="metric-value">{activity}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown(
        """
        <div class="glass-card">
            <div class="small-label">What you get</div>
            <ul style="margin-top: 0.8rem; padding-left: 1.1rem; line-height: 1.8; color: #2d3d34;">
                <li>7-day structured workouts</li>
                <li>Simple nutrition guidance</li>
                <li>Recovery and sleep tips</li>
                <li>Daily movement target</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown(
        """
        <div class="glass-card">
            <div class="small-label">Coach note</div>
            <p style="margin: 0.8rem 0 0; line-height: 1.7; color: #394d41;">
                Consistency beats intensity. Start with a realistic routine and build momentum week by week.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

if not st.session_state.get("fitbuddy_plan"):
    st.markdown(
        """
        <div class="plan-section">
            <h3>Sample training plan</h3>
            <p><strong>Monday:</strong> 30-minute brisk walk + 10-minute mobility</p>
            <p><strong>Tuesday:</strong> Full-body strength circuit</p>
            <p><strong>Wednesday:</strong> Recovery day + stretching</p>
            <p><strong>Thursday:</strong> Cardio + core workout</p>
            <p><strong>Friday:</strong> Strength session</p>
            <p><strong>Saturday:</strong> Active recovery + optional walk</p>
            <p><strong>Sunday:</strong> Rest and planning</p>
        </div>
        """,
        unsafe_allow_html=True,
    )