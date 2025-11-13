from fastapi import FastAPI, HTTPException, Request
from fastapi import Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import pandas as pd
import joblib
import logging
import os
import ast
from datetime import datetime
import json
from pathlib import Path


# ---- Load trained artifacts (keep your existing files/paths) ----
lgb_model = joblib.load("trained_credit_model.pkl")
scaler = joblib.load("scaler.pkl")
feature_cols = joblib.load("feature_columns.pkl")

# ---- Predictions logger (file) ----
pred_logger = logging.getLogger("predictions_logger")
pred_logger.setLevel(logging.INFO)

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)
log_path = os.path.join("logs", "predictions.log")

# Use FileHandler that appends
file_handler = logging.FileHandler(log_path)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(message)s")
file_handler.setFormatter(formatter)

# Avoid duplicate handlers
if not pred_logger.handlers:
    pred_logger.addHandler(file_handler)

# ---- FastAPI app ----
app = FastAPI(title="CreditPathAI API")

# Mount folders:
# - static/ for css/js (used as /static/...)
# - frontend/ for html pages (served below)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

if os.path.isdir("frontend"):
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


# ---- Pydantic model for borrower input ----
class Borrower(BaseModel):
    loan_id: str
    loan_amnt: float
    term: str
    int_rate: float
    installment: float
    grade: str
    sub_grade: str
    emp_length: str
    home_ownership: str
    annual_inc: float
    verification_status: str
    issue_d: str
    purpose: str
    dti: float
    open_acc: float
    pub_rec: float
    revol_bal: float
    revol_util: float
    total_acc: float
    initial_list_status: str
    application_type: str
    mort_acc: float
    pub_rec_bankruptcies: float


# ---- Preprocessing helper ----
def preprocess_api_data(df: pd.DataFrame) -> pd.DataFrame:
    def clean_emp_length(x):
        if "<" in str(x) and "1" in str(x):
            return 0
        if "10+" in str(x):
            return 10
        try:
            return int(str(x).split()[0])
        except:
            return 0

    # safe copy
    df = df.copy()

    # Apply transformations
    if "emp_length" in df.columns:
        df["emp_length"] = df["emp_length"].apply(clean_emp_length)

    if "term" in df.columns:
        df["term"] = df["term"].astype(str).str.replace(" months", "", regex=False)
        # convert to numeric if possible
        try:
            df["term"] = df["term"].astype(int)
        except:
            pass

    # drop heavy text columns if present
    df.drop(columns=["address", "emp_title", "title"], inplace=True, errors="ignore")

    # Scale numeric columns (only those present in df and in scaler.feature_names_in_ if available)
    num_cols = df.select_dtypes(include=["float64", "int64"]).columns.tolist()
    if len(num_cols) > 0:
        try:
            df[num_cols] = scaler.transform(df[num_cols])
        except Exception as e:
            # if scaler expects different columns, just pass (assume scaler saved for all feature cols)
            pass

    # One-hot encode categoricals then ensure all feature_cols are present
    df = pd.get_dummies(df)
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0
    df = df[feature_cols]
    return df


# ---- Risk mapping ----
def map_risk_action(prob: float):
    if prob < 0.3:
        return "Low risk", "Send reminder"
    elif prob < 0.7:
        return "Medium risk", "Call borrower"
    else:
        return "High risk", "Prioritize collection / restructure loan"


# ---- Serve frontend pages via clean routes ----
# If you prefer to use plain static HTML paths, you can visit /frontend/login.html directly.
# These routes give nicer endpoints: '/', '/home', '/predict_page', '/model', '/logs_page'

@app.get("/", response_class=FileResponse)
def serve_login():
    # prefer frontend/login.html if exists, else fallback to root login.html
    if os.path.exists("frontend/login.html"):
        return FileResponse("frontend/login.html")
    if os.path.exists("login.html"):
        return FileResponse("login.html")
    return HTMLResponse("<h3>Login page not found. Place login.html inside frontend/ or project root.</h3>", status_code=404)


@app.get("/home", response_class=FileResponse)
def serve_home():
    if os.path.exists("frontend/home.html"):
        return FileResponse("frontend/home.html")
    return HTMLResponse("<h3>Home page not found.</h3>", status_code=404)


@app.get("/predict_page", response_class=FileResponse)
def serve_predict():
    if os.path.exists("frontend/predict.html"):
        return FileResponse("frontend/predict.html")
    return HTMLResponse("<h3>Predict page not found.</h3>", status_code=404)


@app.get("/model", response_class=FileResponse)
def serve_model():
    if os.path.exists("frontend/model.html"):
        return FileResponse("frontend/model.html")
    return HTMLResponse("<h3>Model page not found.</h3>", status_code=404)


@app.get("/logs_page", response_class=FileResponse)
def serve_logs_page():
    if os.path.exists("frontend/logs.html"):
        return FileResponse("frontend/logs.html")
    return HTMLResponse("<h3>Logs page not found.</h3>", status_code=404)


# -------------------------
# USER AUTH MANAGEMENT
# -------------------------
USER_FILE = Path("users.json")

def load_users():
    if USER_FILE.exists():
        with open(USER_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)



# ---- Prediction endpoint (unchanged behavior) ----
@app.post("/predict")
async def predict(request: Request, borrowers: List[Borrower]):
    try:
        # Get user email from headers (sent by frontend)
        user_email = request.headers.get("x-user-email", "guest")

        data = pd.DataFrame([b.dict() for b in borrowers])

        # Validate missing data
        if data.isnull().sum().sum() > 0:
            raise HTTPException(status_code=400, detail="Please enter valid data for all fields")

        df = preprocess_api_data(data)
        probs = lgb_model.predict_proba(df)[:, 1]

        results = []
        for b, prob in zip(borrowers, probs):
            risk, action = map_risk_action(prob)
            result = {
                "borrower": b.dict(),
                "default_probability": round(float(prob), 3),
                "risk_level": risk,
                "recommended_action": action,
                "user_email": user_email  # ✅ add user to each record
            }
            results.append(result)

            # Log borrower info, prediction, and user email
            pred_logger.info(result)

        return JSONResponse(content=results)

    except HTTPException as e:
        return JSONResponse(content={"error": e.detail}, status_code=e.status_code)
    except Exception as e:
        logging.exception("Unexpected error in /predict")
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)


# ---- Logs endpoint: read predictions.log and return parsed records ----
@app.get("/logs")
async def get_logs(request: Request, limit: int = 100):
    user_email = request.headers.get("x-user-email", "guest")

    if not os.path.exists(log_path):
        return JSONResponse(content=[], status_code=200)

    records = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
            for line in lines:
                try:
                    parts = line.strip().split(" - ", 1)
                    if len(parts) != 2:
                        continue
                    _, dict_str = parts
                    parsed = ast.literal_eval(dict_str.strip())

                    # ✅ filter logs for the specific user
                    if parsed.get("user_email") == user_email:
                        parsed_record = {
                            "timestamp": parts[0],
                            "borrower": parsed.get("borrower"),
                            "default_probability": parsed.get("default_probability"),
                            "risk_level": parsed.get("risk_level"),
                            "recommended_action": parsed.get("recommended_action"),
                            "user_email": parsed.get("user_email"),
                        }
                        records.append(parsed_record)
                except Exception:
                    continue

        records.reverse()
        return JSONResponse(content=records)
    except Exception as e:
        logging.exception("Failed to read logs")
        return JSONResponse(content={"error": "Failed to load logs"}, status_code=500)

#--signup--
@app.post("/signup")
async def signup(name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    users = load_users()

    # Check if user already exists
    if any(u["email"].lower() == email.lower() for u in users):
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = {"name": name, "email": email, "password": password}
    users.append(new_user)
    save_users(users)

    return {"message": "Signup successful! You can now log in."}


#--login--
@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    users = load_users()
    for u in users:
        if u["email"].lower() == email.lower() and u["password"] == password:
            return {"message": "Login successful", "name": u["name"], "email": u["email"]}
    raise HTTPException(status_code=401, detail="Invalid email or password")



# ---- Run instruction note: uvicorn backend:app --reload --port 8000 ----
