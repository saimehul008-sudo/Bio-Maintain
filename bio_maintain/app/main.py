from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlmodel import select
from datetime import datetime, timedelta
from pathlib import Path

from .database import init_db, get_session, engine
from .models import User, Machine, PurchaseDetail, MaintenanceLog, UsageLog, IssueReport

# Resolve absolute paths for templates and static
app_dir = Path(__file__).parent
templates_dir = app_dir / "templates"
static_dir = app_dir / "static"

app = FastAPI(title="Bio-Maintain")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


def device_health_score(session, machine_id: int) -> int:
    """
    Calculate device health score (0-100%) based on:
    - Recent issue reports (penalize recent issues)
    - Average effectiveness from usage logs
    - Maintenance frequency in last 90 days
    """
    score = 100
    
    # Penalize for recent issues
    issues = session.exec(select(IssueReport).where(IssueReport.machine_id == machine_id)).all()
    for i in issues:
        age_days = (datetime.utcnow() - i.created_at).days
        if age_days < 20:
            severity_penalty = {"low": 3, "medium": 8, "high": 15}.get(i.severity, 5)
            score -= severity_penalty
    
    # Factor in average effectiveness
    usages = session.exec(select(UsageLog).where(UsageLog.machine_id == machine_id)).all()
    if usages:
        completed = [u for u in usages if u.end_time is not None]
        if completed:
            avg_eff = sum((u.effectiveness or 80) for u in completed) / len(completed)
            score = int(score * (avg_eff / 100.0))
    
    # Penalize frequent maintenance (more than 3 times in 90 days is concerning)
    maints = session.exec(select(MaintenanceLog).where(MaintenanceLog.machine_id == machine_id)).all()
    recent_maints = [m for m in maints if (datetime.utcnow() - m.start_time).days < 90]
    if len(recent_maints) > 3:
        score -= min(25, (len(recent_maints) - 3) * 5)
    
    return max(0, min(100, score))


def calculate_downtime_impact(session, machine_id: int):
    """
    Calculate active downtime and estimated impact (financial, procedures delayed).
    Returns dict with downtime hours and estimated procedures delayed.
    """
    maints = session.exec(select(MaintenanceLog).where(MaintenanceLog.machine_id == machine_id)).all()
    total_hours = 0
    for m in maints:
        if m.end_time:
            delta = m.end_time - m.start_time
            total_hours += delta.total_seconds() / 3600
        elif m.start_time:
            delta = datetime.utcnow() - m.start_time
            total_hours += delta.total_seconds() / 3600
    
    # Rough estimate: ~4 procedures per hour delayed per machine type
    procedures_delayed = int(total_hours * 4)
    # Rough estimate: $2000 per procedure lost revenue
    financial_impact = procedures_delayed * 2000
    
    return {
        "total_downtime_hours": round(total_hours, 2),
        "procedures_delayed": procedures_delayed,
        "estimated_revenue_loss": f"${financial_impact:,}"
    }


@app.on_event("startup")
def on_startup():
    init_db()

    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info('user')"))
        columns = [row[1] for row in result]
        if "password" not in columns:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN password TEXT'))
            conn.commit()

        result = conn.execute(text("PRAGMA table_info('purchasedetail')"))
        purchase_columns = [row[1] for row in result]
        if "manufacturer" not in purchase_columns:
            conn.execute(text('ALTER TABLE "purchasedetail" ADD COLUMN manufacturer TEXT'))
        if "hospital_serial_number" not in purchase_columns:
            conn.execute(text('ALTER TABLE "purchasedetail" ADD COLUMN hospital_serial_number TEXT'))
        if "safety_standard" not in purchase_columns:
            conn.execute(text('ALTER TABLE "purchasedetail" ADD COLUMN safety_standard TEXT'))
        conn.commit()

    session = get_session()
    default_users = [
        {"username": "doc1", "password": "docpass", "full_name": "Dr. Alice Johnson", "role": "doctor"},
        {"username": "tech1", "password": "techpass", "full_name": "Bob Martinez", "role": "technician"},
        {"username": "admin1", "password": "adminpass", "full_name": "Admin User", "role": "admin"},
    ]

    default_machines = [
        {"name": "MRI Scanner A", "location": "Imaging Ward 3", "model": "MRI-2000", "serial": "M2000-001"},
        {"name": "Ventilator V1", "location": "ICU Room 5", "model": "VentX Pro", "serial": "V-981"},
        {"name": "X-Ray Machine", "location": "Radiology", "model": "XR-500", "serial": "XR-500-02"},
        {"name": "Syringe Pump", "location": "Ward 4", "model": "PumpSafe 200", "serial": "SP-102"},
        {"name": "Oxygen Concentrator", "location": "Respiratory Care", "model": "OxyPure 50", "serial": "OC-050"},
        {"name": "CT Scanner", "location": "Radiology Suite", "model": "CT-Pro 2.0", "serial": "CT-207"},
        {"name": "Defibrillator", "location": "Emergency Dept", "model": "DefibX 300", "serial": "DF-300"},
        {"name": "Patient Monitor", "location": "ICU Room 2", "model": "VitalGuard 11", "serial": "PM-110"},
        {"name": "ECG Machine", "location": "Cardiology", "model": "HeartTrace 7", "serial": "ECG-700"},
    ]

    for user_data in default_users:
        existing_user = session.exec(select(User).where(User.username == user_data["username"])).first()
        if existing_user:
            if not existing_user.password:
                existing_user.password = user_data["password"]
                session.add(existing_user)
        else:
            session.add(User(**user_data))

    existing_machine_names = {m.name for m in session.exec(select(Machine)).all()}
    for machine_data in default_machines:
        if machine_data["name"] not in existing_machine_names:
            session.add(Machine(**machine_data))

    if session.exec(select(MaintenanceLog)).first() is None:
        u1 = UsageLog(machine_id=1, user="Dr. Smith", effectiveness=95)
        u1.end_time = datetime.utcnow()
        session.add(u1)
        m_log = MaintenanceLog(machine_id=1, performed_by="tech1", notes="Routine calibration")
        m_log.end_time = datetime.utcnow()
        session.add(m_log)

    existing_purchase_machine_ids = {pd.machine_id for pd in session.exec(select(PurchaseDetail)).all()}
    purchase_details = [
        {"name": "MRI Scanner A", "vendor": "MedEquip Supplies", "manufacturer": "MedEquip Corp", "hospital_serial_number": "HSP-MRI-001", "purchase_date": datetime(2023, 3, 12), "price": 350000.00, "safety_standard": "IEC 60601"},
        {"name": "Ventilator V1", "vendor": "AirFlow Systems", "manufacturer": "AirFlow Tech", "hospital_serial_number": "HSP-VEN-005", "purchase_date": datetime(2024, 1, 22), "price": 120000.00, "safety_standard": "ISO 13485"},
        {"name": "X-Ray Machine", "vendor": "ClearScan Medical", "manufacturer": "ClearScan Inc", "hospital_serial_number": "HSP-XR-011", "purchase_date": datetime(2022, 11, 8), "price": 220000.00, "safety_standard": "IEC 60601"},
        {"name": "Syringe Pump", "vendor": "DoseCare", "manufacturer": "DoseCare Labs", "hospital_serial_number": "HSP-SP-021", "purchase_date": datetime(2024, 4, 5), "price": 8000.00, "safety_standard": "ISO 13485"},
        {"name": "Oxygen Concentrator", "vendor": "PureLife Medical", "manufacturer": "PureLife Corp", "hospital_serial_number": "HSP-OC-007", "purchase_date": datetime(2023, 7, 30), "price": 15000.00, "safety_standard": "EN 60601"},
        {"name": "CT Scanner", "vendor": "Precision Imaging", "manufacturer": "Precision Health", "hospital_serial_number": "HSP-CT-003", "purchase_date": datetime(2024, 2, 14), "price": 780000.00, "safety_standard": "IEC 60601"},
        {"name": "Defibrillator", "vendor": "LifePulse", "manufacturer": "LifePulse Systems", "hospital_serial_number": "HSP-DF-002", "purchase_date": datetime(2023, 9, 12), "price": 25000.00, "safety_standard": "IEC 60601-2-4"},
        {"name": "Patient Monitor", "vendor": "VitalView", "manufacturer": "VitalView Tech", "hospital_serial_number": "HSP-PM-014", "purchase_date": datetime(2023, 8, 19), "price": 18000.00, "safety_standard": "ISO 80601"},
        {"name": "ECG Machine", "vendor": "CardioSense", "manufacturer": "CardioSense Labs", "hospital_serial_number": "HSP-ECG-009", "purchase_date": datetime(2024, 5, 2), "price": 13500.00, "safety_standard": "IEC 60601-2-25"},
    ]
    for detail in purchase_details:
        machine = session.exec(select(Machine).where(Machine.name == detail["name"])).first()
        if machine and machine.id not in existing_purchase_machine_ids:
            session.add(PurchaseDetail(
                machine_id=machine.id,
                vendor=detail["vendor"],
                manufacturer=detail["manufacturer"],
                hospital_serial_number=detail["hospital_serial_number"],
                purchase_date=detail["purchase_date"],
                price=detail["price"],
                safety_standard=detail["safety_standard"],
            ))

    session.commit()
    session.close()


def get_current_user(request: Request):
    uid = request.cookies.get("user_id")
    if not uid:
        return None
    session = get_session()
    try:
        user = session.get(User, int(uid))
    except:
        user = None
    session.close()
    return user


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = get_current_user(request)
    if not user:
        error = request.query_params.get("error")
        return templates.TemplateResponse("login.html", {"request": request, "error": error})

    session = get_session()
    machines = session.exec(select(Machine)).all()
    scores = {m.id: device_health_score(session, m.id) for m in machines}
    status_counts = {"Active": 0, "Under Maintenance": 0, "Offline": 0}
    for m in machines:
        status_counts[m.status] = status_counts.get(m.status, 0) + 1
    session.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "machines": machines,
        "scores": scores,
        "status_counts": status_counts,
        "user": user
    })


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)

    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
def login(response: Response, username: str = Form(...), password: str = Form(...)):
    session = get_session()
    user = session.exec(select(User).where(User.username == username)).first()
    session.close()
    if not user:
        return RedirectResponse(url="/login?error=Invalid+user", status_code=302)
    if not user.password or user.password != password:
        return RedirectResponse(url="/login?error=Invalid+password", status_code=302)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="user_id", value=str(user.id), max_age=86400)
    return response


@app.get("/logout")
def logout(response: Response):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("user_id")
    return response


@app.get("/machine/{machine_id}", response_class=HTMLResponse)
def machine_view(request: Request, machine_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    session = get_session()
    machine = session.get(Machine, machine_id)
    if not machine:
        session.close()
        raise HTTPException(status_code=404)
    
    issues = session.exec(select(IssueReport).where(IssueReport.machine_id == machine_id)).all()
    maints = session.exec(select(MaintenanceLog).where(MaintenanceLog.machine_id == machine_id)).all()
    usages = session.exec(select(UsageLog).where(UsageLog.machine_id == machine_id)).all()
    purchase_detail = session.exec(select(PurchaseDetail).where(PurchaseDetail.machine_id == machine_id)).first()
    score = device_health_score(session, machine_id)
    impact = calculate_downtime_impact(session, machine_id)

    next_due = None
    if machine.last_maintenance:
        next_due = machine.last_maintenance + timedelta(days=180)
    elif purchase_detail and purchase_detail.purchase_date:
        next_due = purchase_detail.purchase_date + timedelta(days=365)
    
    session.close()
    return templates.TemplateResponse("machine.html", {
        "request": request,
        "machine": machine,
        "issues": issues,
        "maints": maints,
        "usages": usages,
        "purchase_detail": purchase_detail,
        "score": score,
        "impact": impact,
        "next_due": next_due,
        "user": user
    })


@app.post("/machine/{machine_id}/report")
def report_issue(machine_id: int, reported_by: str = Form(...), severity: str = Form("medium"), notes: str = Form("")):
    session = get_session()
    if not session.get(Machine, machine_id):
        session.close()
        raise HTTPException(status_code=404)
    
    ir = IssueReport(machine_id=machine_id, reported_by=reported_by, severity=severity, notes=notes)
    session.add(ir)
    session.commit()
    session.close()
    return {"ok": True, "message": "Issue reported successfully"}


@app.post("/machine/{machine_id}/claim")
def claim_machine(machine_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    if user.role not in ("doctor", "technician", "admin"):
        raise HTTPException(status_code=403, detail="Not authorized to claim machines")
    
    session = get_session()
    m = session.get(Machine, machine_id)
    if not m:
        session.close()
        raise HTTPException(status_code=404)
    
    m.status = "Under Maintenance"
    m.last_maintenance = datetime.utcnow()
    ml = MaintenanceLog(machine_id=machine_id, performed_by=user.username, start_time=datetime.utcnow())
    
    session.add(ml)
    session.add(m)
    session.commit()
    session.close()
    
    return {"ok": True, "message": f"Machine claimed for maintenance by {user.full_name}"}


@app.post("/machine/{machine_id}/release")
def release_machine(machine_id: int, request: Request, notes: str = Form("")):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    
    session = get_session()
    m = session.get(Machine, machine_id)
    if not m:
        session.close()
        raise HTTPException(status_code=404)
    
    m.status = "Active"
    
    # Find the open maintenance log and close it
    maints = session.exec(select(MaintenanceLog).where(
        MaintenanceLog.machine_id == machine_id,
        MaintenanceLog.end_time == None
    )).all()
    for maint in maints:
        maint.end_time = datetime.utcnow()
        if notes:
            maint.notes = notes
        session.add(maint)
    
    session.add(m)
    session.commit()
    session.close()
    
    return {"ok": True, "message": "Machine released back to active status"}


