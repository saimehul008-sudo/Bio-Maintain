from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from io import BytesIO
import segno
from datetime import datetime
from pathlib import Path

from .database import init_db, get_session, engine
from .models import User, Machine, MaintenanceLog, UsageLog, IssueReport

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
    # Create sample data if empty
    session = get_session()
    if session.exec(select(User)).first() is None:
        session.add(User(username="doc1", full_name="Dr. Alice Johnson", role="doctor"))
        session.add(User(username="tech1", full_name="Bob Martinez", role="technician"))
        session.add(User(username="admin1", full_name="Admin User", role="admin"))
        
        m1 = Machine(name="MRI Scanner A", location="Imaging Ward 3", model="MRI-2000", serial="M2000-001")
        m2 = Machine(name="Ventilator V1", location="ICU Room 5", model="VentX Pro", serial="V-981")
        m3 = Machine(name="X-Ray Machine", location="Radiology", model="XR-500", serial="XR-500-02")
        
        session.add(m1)
        session.add(m2)
        session.add(m3)
        
        # Add sample usage and maintenance logs
        u1 = UsageLog(machine_id=1, user="Dr. Smith", effectiveness=95)
        u1.end_time = datetime.utcnow()
        session.add(u1)
        
        m_log = MaintenanceLog(machine_id=1, performed_by="tech1", notes="Routine calibration")
        m_log.end_time = datetime.utcnow()
        session.add(m_log)
        
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
    session = get_session()
    machines = session.exec(select(Machine)).all()
    scores = {m.id: device_health_score(session, m.id) for m in machines}
    session.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "machines": machines,
        "scores": scores,
        "user": get_current_user(request)
    })


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(response: Response, username: str = Form(...)):
    session = get_session()
    user = session.exec(select(User).where(User.username == username)).first()
    session.close()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    response = Response(status_code=302, headers={"Location": "/"})
    response.set_cookie(key="user_id", value=str(user.id), max_age=86400)
    return response


@app.get("/logout")
def logout(response: Response):
    response = Response(status_code=302, headers={"Location": "/"})
    response.delete_cookie("user_id")
    return response


@app.get("/machine/{machine_id}", response_class=HTMLResponse)
def machine_view(request: Request, machine_id: int):
    session = get_session()
    machine = session.get(Machine, machine_id)
    if not machine:
        session.close()
        raise HTTPException(status_code=404)
    
    issues = session.exec(select(IssueReport).where(IssueReport.machine_id == machine_id)).all()
    maints = session.exec(select(MaintenanceLog).where(MaintenanceLog.machine_id == machine_id)).all()
    usages = session.exec(select(UsageLog).where(UsageLog.machine_id == machine_id)).all()
    score = device_health_score(session, machine_id)
    impact = calculate_downtime_impact(session, machine_id)
    
    session.close()
    return templates.TemplateResponse("machine.html", {
        "request": request,
        "machine": machine,
        "issues": issues,
        "maints": maints,
        "usages": usages,
        "score": score,
        "impact": impact,
        "user": get_current_user(request)
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


@app.get("/machine/{machine_id}/qr")
def qr_code(machine_id: int):
    """Generate and return QR code for machine as SVG."""
    url = f"http://localhost:8000/machine/{machine_id}"
    qr = segno.make(url, micro=False)
    svg_bytes = qr.save(None, kind='svg', scale=5)
    return Response(content=svg_bytes, media_type="image/svg+xml")
