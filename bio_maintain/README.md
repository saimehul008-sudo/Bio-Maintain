# Bio-Maintain

A full-stack Python medical machine tracking system built with FastAPI.

## Features
- Track medical machine usage (duration, effectiveness)
- Maintenance history and scheduling
- Purchase details logging
- Rapid issue reporting portal
- Device Health Score (0-100%)
- Interactive 2D machine schematics
- QR code generation per machine (scan to view machine profile)
- Role-based access control (doctor, technician, admin)
- Active downtime tracking and financial impact estimation

## Installation & Setup

1. Install dependencies:
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

2. Run the server:
```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Open browser on this machine or another device on the same network:
```
http://<your-pc-ip>:8000
```

4. Login with demo users:
   - Username: `doc1` (Doctor)
   - Username: `tech1` (Technician)
   - Username: `admin1` (Admin)

## Project Structure
```
bio_maintain/
├── app/
│   ├── main.py              # FastAPI routes and app logic
│   ├── models.py            # SQLModel ORM definitions
│   ├── database.py          # Database setup
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS and static assets
├── data/                    # SQLite database
└── requirements.txt         # Python dependencies
```

## Key Endpoints
- `GET /` - Machine list
- `GET /machine/{id}` - Machine details & schematic
- `GET /machine/{id}/qr` - QR code image
- `POST /machine/{id}/report` - Report issue
- `POST /machine/{id}/claim` - Claim for maintenance
- `GET /login` - Login form
