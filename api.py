import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uvicorn
import asyncio
import time
from datetime import datetime

_APP_START_MONOTONIC: float | None = None

from database import AsyncSessionLocal, init_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from models import RegisteredFace, AttendanceLog, GymOwner
import face_service
import main as engine # Integrated with the Sentinel Engine
import onvif_utils
import base64
import numpy as np
import cv2
from pydantic import BaseModel
from supabase import create_client, Client

# Supabase Storage Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "face"

class RegisterRequest(BaseModel):
    owner_id: int
    name: str
    role: str
    image_base64: str


class RenameRequest(BaseModel):
    name: str

class BlacklistRequest(BaseModel):
    is_blacklisted: bool

class NodeRequest(BaseModel):
    name: str
    url: str # This will be the IP address in "Smart" mode
    owner_id: int
    brand: str = "Generic"
    use_p2p: bool = False
    p2p_uid: str = ""
    p2p_user: str = "admin"
    p2p_pass: str = ""
    use_onvif: bool = False
    onvif_port: int = 80
    onvif_user: str = "admin"
    onvif_pass: str = ""

class AuthRequest(BaseModel):
    identifier: str
    password: str

class SignupRequest(BaseModel):
    gym_name: str
    email: str
    mobile: str
    password: str

class WorkoutSaveRequest(BaseModel):
    owner_id: int
    member_id: int
    exercise_name: str
    reps: int
    avg_accuracy: int

class NotificationSettingsRequest(BaseModel):
    owner_id: int
    gmail_enabled: bool = False
    alert_email: str = ""
    notify_on_entry: bool = True
    notify_on_expiry: bool = True

class SubscriptionRequest(BaseModel):
    user_id: int
    expiry_date: str # ISO format
    plan_type: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _APP_START_MONOTONIC
    _APP_START_MONOTONIC = time.monotonic()

    # Ensure static directories exist to prevent deployment crashes
    os.makedirs("static/faces", exist_ok=True)
    os.makedirs("frontend/dist/assets", exist_ok=True)
    
    logger.info("SYSTEM: Initializing Database Connection...")
    await init_db()
    logger.info("SYSTEM: Database Connection Established")


    
    # Initialize Sentinel Engine inside API process for shared memory
    engine.start_background_workers()
    
    # Load Command Center Cameras from Database
    async with AsyncSessionLocal() as session:
        from models import CameraNode
        result = await session.execute(select(CameraNode))
        db_nodes = result.scalars().all()
        for c in db_nodes:
            node = engine.SentinelNode(
                c.url, c.name, owner_id=c.owner_id, rotation=None,
                use_p2p=c.use_p2p, p2p_uid=c.p2p_uid,
                p2p_user=c.p2p_user, p2p_pass=c.p2p_pass
            )
            node.use_onvif = c.use_onvif
            node.onvif_port = c.onvif_port
            node.onvif_user = c.onvif_user
            node.onvif_pass = c.onvif_pass
            node.start()
            engine.global_nodes[c.name] = node
            logger.info(f"SYSTEM: Restored Camera Node '{c.name}'")
            
    print(">> Sentinel Engine Integrated & Online")
    yield
    # Clean shutdown
    for node_name, node in engine.global_nodes.items():
        node.stop()

app = FastAPI(title="Universal Face System API", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}

# Enable CORS for frontend integration
origins = os.getenv("CORS_ORIGINS", "*").split(",")
origins = [o.strip() for o in origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"INCOMING: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"OUTGOING: {request.method} {request.url} -> {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"CRASH: {request.method} {request.url} -> {e}")
        raise

# Dependency to get DB session safely
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# --- LIVE STREAMING CORE ---
async def gen_frames(request: Request, node_name: str):
    """MJPEG frame generator for a specific Sentinel node with resource cleanup."""
    while True:
        if await request.is_disconnected():
            break
            
        if node_name in engine.global_nodes:
            node = engine.global_nodes[node_name]
            frame = node.last_frame
            if frame is not None:
                # Optimized encoding for streaming
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        await asyncio.sleep(0.05) # ~20 FPS for stability

@app.get("/api/stream/{node_name}")
async def stream_node(request: Request, node_name: str):
    if node_name not in engine.global_nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    return StreamingResponse(gen_frames(request, node_name), media_type='multipart/x-mixed-replace; boundary=frame')

@app.get("/api/telemetry")
async def get_system_telemetry():
    return engine.get_telemetry()

@app.post("/api/recognize/crop")
async def recognize_crop(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    face_base64 = data.get("image_base64")
    node_name = data.get("node_name", "Edge_Node")
    owner_id = data.get("owner_id", 1)
    
    if not face_base64:
        return {"status": "error", "message": "No image data"}
        
    # Process the crop through the Recognition Engine
    import base64
    import numpy as np
    
    img_data = base64.b64decode(face_base64.split(",")[1] if "," in face_base64 else face_base64)
    nparr = np.frombuffer(img_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # We use a special mode in the engine to just recognize this single cropped frame
    match_id, name, score = await engine.process_single_crop(frame, node_name, owner_id, db)
    
    return {
        "status": "success",
        "match_id": match_id,
        "name": name,
        "score": float(score)
    }

@app.post("/api/nodes/add")
async def add_node(request: NodeRequest, db: AsyncSession = Depends(get_db)):
    if request.name in engine.global_nodes:
        logger.info(f"Stopping existing node: {request.name}")
        engine.global_nodes[request.name].stop()
        await asyncio.sleep(2) # Extended wait for hardware release
        
    try:
        final_url = request.url
        node_name = request.name if request.name else "Gym_Camera"
        
        # Smart Discovery Logic based on Brand
        if request.use_onvif:
            # Try specified port first, then common ones
            ports_to_try = [request.onvif_port] if request.onvif_port != 80 else [80, 8080, 888, 8000]
            discovered_url = None
            
            for port in ports_to_try:
                logger.info(f"Attempting ONVIF discovery for {request.url}:{port}")
                discovered_url = await onvif_utils.get_onvif_rtsp_url(
                    request.url, port, request.onvif_user, request.onvif_pass
                )
                if discovered_url:
                    logger.info(f"ONVIF Discovered URL on port {port}: {discovered_url}")
                    final_url = discovered_url
                    break
            
            # If ONVIF fails, try brand-specific RTSP templates
            if not discovered_url:
                brand = request.brand.lower()
                user = request.onvif_user
                pw = request.onvif_pass
                ip = request.url
                
                templates = {
                    "hikvision": [f"rtsp://{user}:{pw}@{ip}:554/Streaming/Channels/101"],
                    "dahua": [f"rtsp://{user}:{pw}@{ip}:554/cam/realmonitor?channel=1&subtype=0"],
                    "cp plus": [f"rtsp://{user}:{pw}@{ip}:554/cam/realmonitor?channel=1&subtype=0"],
                    "honeywell": [f"rtsp://{user}:{pw}@{ip}:554/Streaming/Channels/1"],
                    "axis": [f"rtsp://{user}:{pw}@{ip}/axis-media/media.amp"]
                }
                
                if brand in templates:
                    for template in templates[brand]:
                        logger.info(f"Trying brand template for {brand}: {template}")
                        final_url = template
                        break
        
        url = int(final_url) if str(final_url).isdigit() else final_url
        if isinstance(url, str) and url.startswith("http"):
            if url.count('/') < 3 or (url.count('/') == 3 and url.endswith('/')):
                url = url.rstrip('/') + '/video'

        logger.info(f"Registering Node: {node_name} with source: {url}")
        node = engine.SentinelNode(
            url, node_name, owner_id=request.owner_id, rotation=None,
            use_p2p=request.use_p2p, p2p_uid=request.p2p_uid,
            p2p_user=request.p2p_user, p2p_pass=request.p2p_pass
        )
        node.use_onvif = request.use_onvif
        node.onvif_port = request.onvif_port
        node.onvif_user = request.onvif_user
        node.onvif_pass = request.onvif_pass
        node.start()
        
        engine.global_nodes[node_name] = node
        
        # Save to database
        from models import CameraNode
        result = await db.execute(select(CameraNode).where(CameraNode.owner_id == request.owner_id, CameraNode.name == node_name))
        db_node = result.scalars().first()
        if not db_node:
            db_node = CameraNode(owner_id=request.owner_id, name=node_name)
            db.add(db_node)
        
        db_node.url = str(request.url)
        db_node.use_p2p = request.use_p2p
        db_node.p2p_uid = request.p2p_uid
        db_node.p2p_user = request.p2p_user
        db_node.p2p_pass = request.p2p_pass
        db_node.use_onvif = request.use_onvif
        db_node.onvif_port = request.onvif_port
        db_node.onvif_user = request.onvif_user
        db_node.onvif_pass = request.onvif_pass
        await db.commit()

        return {"message": f"Node {node_name} added successfully.", "onvif_success": request.use_onvif and final_url != request.url}
    except Exception as e:
        logger.error(f"Error adding node: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/nodes/list")
async def list_nodes(owner_id: int, db: AsyncSession = Depends(get_db)):
    from models import CameraNode
    result = await db.execute(select(CameraNode).where(CameraNode.owner_id == owner_id))
    nodes = result.scalars().all()
    return nodes

@app.delete("/api/nodes/{name}")
async def delete_node(name: str, owner_id: int, db: AsyncSession = Depends(get_db)):
    from models import CameraNode
    result = await db.execute(select(CameraNode).where(CameraNode.owner_id == owner_id, CameraNode.name == name))
    node = result.scalars().first()
    if node:
        await db.delete(node)
        await db.commit()
    
    if name in engine.global_nodes:
        engine.global_nodes[name].stop()
        del engine.global_nodes[name]
    
    return {"message": "Node deleted"}

@app.get("/api/nodes/settings")
async def get_node_settings(owner_id: int):
    # Compatibility endpoint for frontend
    for name, node in engine.global_nodes.items():
        if getattr(node, 'owner_id', None) == owner_id or node.owner_id == owner_id:
            return {
                "name": node.node_name,
                "url": str(node.rtsp_url),
                "use_p2p": getattr(node, 'use_p2p', False),
                "p2p_uid": getattr(node, 'p2p_uid', ''),
                "p2p_user": getattr(node, 'p2p_user', 'admin'),
                "p2p_pass": getattr(node, 'p2p_pass', ''),
                "use_onvif": getattr(node, 'use_onvif', False),
                "onvif_port": getattr(node, 'onvif_port', 80),
                "onvif_user": getattr(node, 'onvif_user', 'admin'),
                "onvif_pass": getattr(node, 'onvif_pass', '')
            }
    return {"message": "No active node found"}

# WhatsApp Integration decommissioned

@app.post("/api/auth/signup")
async def signup(request: SignupRequest, req: Request, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(GymOwner).where(GymOwner.email == request.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_owner = GymOwner(
        gym_name=request.gym_name,
        email=request.email,
        mobile=request.mobile,
        password=request.password,
        last_ip=req.headers.get("x-forwarded-for") or req.client.host
    )
    db.add(new_owner)
    await db.commit()
    await db.refresh(new_owner)
    
    # Trigger Admin Notification
    asyncio.create_task(send_admin_signup_notification(new_owner))
    
    return {"message": "Account created successfully", "status": "success"}

async def send_admin_signup_notification(owner):
    admin_email = os.getenv("ADMIN_EMAIL")
    if not admin_email:
        return

    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if not smtp_user or not smtp_pass:
        logger.warning("Admin Notification: SMTP credentials missing.")
        return

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = admin_email
        msg['Subject'] = f"🚀 New Gym Owner Signup: {owner.gym_name}"

        body = f"""
        A new gym owner has signed up on the Universal Face System!
        
        Gym Name: {owner.gym_name}
        Email: {owner.email}
        Mobile: {owner.mobile}
        Signup Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        System ID: {owner.id}
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587")))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logger.info(f"Admin notification sent to {admin_email}")
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")

@app.post("/api/auth/login")
async def login(request: AuthRequest, db: AsyncSession = Depends(get_db)):
    # Match either email or mobile number
    from sqlalchemy import or_
    result = await db.execute(
        select(GymOwner).where(
            or_(
                GymOwner.email == request.identifier,
                GymOwner.mobile == request.identifier
            )
        )
    )
    owner = result.scalars().first()
    
    if not owner or owner.password != request.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "message": "Login successful", 
        "status": "success", 
        "owner_id": owner.id,
        "gym_name": owner.gym_name
    }

@app.get("/api/workouts")
async def get_workouts(owner_id: int, db: AsyncSession = Depends(get_db)):
    from models import WorkoutSession, RegisteredFace
    # Use outerjoin so guest sessions (unregistered IDs) still show up
    query = (
        select(WorkoutSession, RegisteredFace.name)
        .outerjoin(RegisteredFace, WorkoutSession.member_id == RegisteredFace.id)
        .where(WorkoutSession.owner_id == owner_id)
        .order_by(WorkoutSession.timestamp.desc())
        .limit(20)
    )
    result = await db.execute(query)
    sessions = []
    for row in result.all():
        session, name = row
        sessions.append({
            "id": session.id,
            "member_name": name if name else "Guest Member",
            "exercise": session.exercise_name,
            "reps": session.reps,
            "accuracy": session.avg_accuracy,
            "timestamp": session.timestamp
        })
    return sessions

@app.post("/api/workouts/save")
async def save_workout(request: WorkoutSaveRequest, db: AsyncSession = Depends(get_db)):
    new_session = WorkoutSession(
        owner_id=request.owner_id,
        member_id=request.member_id,
        exercise_name=request.exercise_name,
        reps=request.reps,
        avg_accuracy=request.avg_accuracy
    )
    db.add(new_session)
    await db.commit()
    return {"status": "success"}

@app.get("/api/admin/owners")
async def get_all_owners(admin_pass: str = None, db: AsyncSession = Depends(get_db)):
    secret = os.getenv("ADMIN_PASSWORD", "Goal@2026")
    if admin_pass != secret:
        raise HTTPException(status_code=401, detail="Unauthorized access")

    result = await db.execute(select(GymOwner).order_by(GymOwner.id.desc()))
    owners = result.scalars().all()
    out = []
    for o in owners:
        out.append({
            "id": o.id,
            "gym_name": o.gym_name,
            "email": o.email,
            "mobile": o.mobile,
            "created_at": o.created_at if hasattr(o, 'created_at') else None,
            "last_ip": o.last_ip if hasattr(o, 'last_ip') else "N/A"
        })
    return out

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/faces", StaticFiles(directory="static/faces"), name="faces")
app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

@app.get("/")
async def root():
    return FileResponse("frontend/dist/index.html")

@app.get("/admin")
async def admin_page():
    return FileResponse("static/admin.html")

@app.get("/api/export/attendance")
async def export_attendance(owner_id: int, db: AsyncSession = Depends(get_db)):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    result = await db.execute(
        select(AttendanceLog, RegisteredFace.name, RegisteredFace.role)
        .join(RegisteredFace, AttendanceLog.face_id == RegisteredFace.id)
        .where(AttendanceLog.owner_id == owner_id)
        .order_by(AttendanceLog.timestamp.desc())
    )
    logs = result.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Role", "Timestamp", "Node", "Status"])
    
    for log, name, role in logs:
        writer.writerow([
            log.id, 
            name, 
            role, 
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"), 
            log.node_name, 
            log.subscription_status
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{owner_id}.csv"}
    )

@app.get("/api/users")
async def get_users(owner_id: int, db: AsyncSession = Depends(get_db)):
    from datetime import datetime
    now = datetime.now()
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.owner_id == owner_id))
    users = result.scalars().all()
    out = []
    for u in users:
        is_expired = u.subscription_expiry is not None and u.subscription_expiry < now
        out.append({
            "id": u.id,
            "owner_id": u.owner_id,
            "name": u.name,
            "role": u.role,
            "image_path": u.image_path,
            "is_blacklisted": u.is_blacklisted,
            "subscription_expiry": u.subscription_expiry,
            "plan_type": u.plan_type,
            "notes": u.notes,
            "created_at": u.created_at,
            "is_active": u.is_active,
            "subscription_status": "expired" if is_expired else "active",
        })
    return out

@app.get("/api/logs")
async def get_logs(owner_id: int, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    query = (
        select(AttendanceLog, RegisteredFace.name, RegisteredFace.role, RegisteredFace.image_path, RegisteredFace.subscription_expiry)
        .join(RegisteredFace, AttendanceLog.face_id == RegisteredFace.id)
        .where(AttendanceLog.owner_id == owner_id)
        .order_by(AttendanceLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    logs = []
    for row in result.all():
        log, name, role, img_path, expiry = row
        from datetime import datetime
        is_expired = expiry < datetime.now() if expiry else False
        logs.append({
            "id": log.id,
            "face_id": log.face_id,
            "name": name,
            "role": role,
            "image_path": img_path,
            "subscription_status": "expired" if is_expired else "active",
            "timestamp": log.timestamp,
            "location": log.location
        })
    return logs

@app.get("/api/stats")
async def get_stats(owner_id: int, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_24h = now - timedelta(hours=24)

    uptime_sec = 0
    if _APP_START_MONOTONIC is not None:
        uptime_sec = int(time.monotonic() - _APP_START_MONOTONIC)

    # 1. Member Stats (no expiry date = open-ended / active membership)
    total_q = await db.execute(select(func.count(RegisteredFace.id)).where(RegisteredFace.owner_id == owner_id))
    total_members = total_q.scalar() or 0

    active_q = await db.execute(select(func.count(RegisteredFace.id)).where(
        RegisteredFace.owner_id == owner_id,
        RegisteredFace.is_active == True,
        or_(
            RegisteredFace.subscription_expiry.is_(None),
            RegisteredFace.subscription_expiry > now,
        ),
    ))
    active_members = active_q.scalar() or 0

    expired_q = await db.execute(select(func.count(RegisteredFace.id)).where(
        RegisteredFace.owner_id == owner_id,
        RegisteredFace.subscription_expiry.isnot(None),
        RegisteredFace.subscription_expiry < now,
    ))
    expired_members = expired_q.scalar() or 0

    visits_24h_q = await db.execute(select(func.count(AttendanceLog.id)).where(
        AttendanceLog.owner_id == owner_id,
        AttendanceLog.timestamp >= window_24h,
    ))
    visits_last_24h = visits_24h_q.scalar() or 0

    # 2. Today's Attendance
    today_q = await db.execute(select(func.count(AttendanceLog.id)).where(
        AttendanceLog.owner_id == owner_id,
        AttendanceLog.timestamp >= today_start
    ))
    today_count = today_q.scalar()

    # 3. Weekly Trend (Last 7 Days) - Optimized to 1 query
    week_start = today_start - timedelta(days=6)
    day_trunc = func.date_trunc('day', AttendanceLog.timestamp)
    weekly_q = await db.execute(
        select(
            day_trunc.label('day'),
            func.count(AttendanceLog.id).label('count')
        )
        .where(
            AttendanceLog.owner_id == owner_id,
            AttendanceLog.timestamp >= week_start
        )
        .group_by(day_trunc)
        .order_by('day')
    )
    
    weekly_data = {row.day.strftime("%a"): row.count for row in weekly_q.all()}
    weekly_trend = []
    for i in range(7):
        d = (week_start + timedelta(days=i)).strftime("%a")
        weekly_trend.append({"day": d, "count": weekly_data.get(d, 0)})

    # 4. Peak Hours Distribution (Today) - Optimized to 1 query
    hour_extract = func.extract('hour', AttendanceLog.timestamp)
    peak_q = await db.execute(
        select(
            hour_extract.label('hour'),
            func.count(AttendanceLog.id).label('count')
        )
        .where(
            AttendanceLog.owner_id == owner_id,
            AttendanceLog.timestamp >= today_start
        )
        .group_by(hour_extract)
    )
    
    peak_data = {int(row.hour): row.count for row in peak_q.all()}
    peak_hours = []
    for h in range(6, 23):
        peak_hours.append({"hour": f"{h:02d}:00", "count": peak_data.get(h, 0)})

    return {
        "summary": {
            "total_members": total_members,
            "active_members": active_members,
            "expired_members": expired_members,
            "today_attendance": today_count,
            "visits_last_24h": visits_last_24h,
            "server_uptime_seconds": uptime_sec,
        },
        "weekly_trend": weekly_trend,
        "peak_hours": peak_hours
    }

@app.get("/api/users/{user_id}/activity")
async def get_user_activity(user_id: int, db: AsyncSession = Depends(get_db)):
    # Get attendance counts for last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    date_expr = func.date(AttendanceLog.timestamp)
    result = await db.execute(
        select(date_expr, func.count(AttendanceLog.id))
        .where(AttendanceLog.face_id == user_id, AttendanceLog.timestamp >= thirty_days_ago)
        .group_by(date_expr)
        .order_by(date_expr)
    )
    
    activity = result.all()
    # Fill gaps for a continuous chart
    activity_map = {str(row[0]): row[1] for row in activity}
    full_data = []
    for i in range(30):
        d = (thirty_days_ago + timedelta(days=i)).date()
        full_data.append({"date": str(d), "count": activity_map.get(str(d), 0)})
    
    return full_data

class UserUpdateRequest(BaseModel):
    name: str = None
    role: str = None
    subscription_expiry: str = None # ISO format
    plan_type: str = None

@app.post("/api/users/{user_id}/update")
async def update_user(user_id: int, request: UserUpdateRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.name: user.name = request.name
    if request.role: user.role = request.role
    if request.plan_type: user.plan_type = request.plan_type
    if request.subscription_expiry:
        try:
            from datetime import datetime
            user.subscription_expiry = datetime.fromisoformat(request.subscription_expiry)
        except:
            raise HTTPException(status_code=400, detail="Invalid date format")
            
    await db.commit()
    return {"message": "Profile updated successfully", "status": "success"}

@app.put("/api/users/subscription")
async def update_subscription(request: SubscriptionRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == request.user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="Member not found")
    
    from datetime import datetime
    try:
        user.subscription_expiry = datetime.fromisoformat(request.expiry_date.replace("Z", "+00:00"))
        user.plan_type = request.plan_type
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid date format")
        
    return {"message": "Subscription updated successfully"}

@app.put("/api/settings/notifications")
async def update_notification_settings(request: NotificationSettingsRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GymOwner).where(GymOwner.id == request.owner_id))
    owner = result.scalars().first()
    if not owner: raise HTTPException(status_code=404, detail="Owner not found")
    
    owner.gmail_enabled = request.gmail_enabled
    owner.alert_email = request.alert_email
    owner.notify_on_entry = request.notify_on_entry
    owner.notify_on_expiry = request.notify_on_expiry
    
    await db.commit()
    return {"message": "Notification settings updated"}

@app.get("/api/settings/notifications")
async def get_notification_settings(owner_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GymOwner).where(GymOwner.id == owner_id))
    owner = result.scalars().first()
    if not owner: raise HTTPException(status_code=404, detail="Owner not found")
    
    return {
        "gmail_enabled": owner.gmail_enabled,
        "alert_email": owner.alert_email,
        "notify_on_entry": owner.notify_on_entry,
        "notify_on_expiry": owner.notify_on_expiry
    }

@app.get("/api/stats/hourly")
async def get_hourly_stats(db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta
    yesterday = datetime.now() - timedelta(days=1)
    result = await db.execute(
        select(AttendanceLog.timestamp).where(AttendanceLog.timestamp >= yesterday)
    )
    from collections import Counter
    ts_list = result.scalars().all()
    hours = [ts.hour for ts in ts_list]
    counts = Counter(hours)
    
    current_hour = datetime.now().hour
    data = []
    for i in range(12):
        h = (current_hour - i) % 24
        data.append({"hour": f"{h}:00", "count": counts.get(h, 0)})
    
    # Add unique visitor count
    res_unique = await db.execute(
        select(RegisteredFace.id).where(RegisteredFace.is_active == True)
    )
    unique_count = len(res_unique.scalars().all())
    
    return {"hourly": data[::-1], "unique_captured": unique_count}

@app.put("/api/users/{user_id}/rename")
async def rename_user(user_id: int, request: RenameRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user.name = request.name
    await db.commit()
    return {"message": "User renamed successfully"}

@app.put("/api/users/{user_id}/blacklist")
async def toggle_blacklist(user_id: int, request: BlacklistRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user.is_blacklisted = request.is_blacklisted
    await db.commit()
    return {"message": "Blacklist status updated"}

@app.post("/api/register")
async def register_user(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Decode base64 image
        header, encoded = request.image_base64.split(",", 1) if "," in request.image_base64 else (None, request.image_base64)
        nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image data")

        # Detect and get embedding using SOTA ArcFace
        objs = face_service.extract_face(frame, enforce_liveness=False)
        
        if not objs:
            raise HTTPException(status_code=400, detail="No face detected in image")
        
        if len(objs) > 1:
            raise HTTPException(status_code=400, detail="Multiple faces detected. Please provide a clear image of one face.")

        raw_emb = np.array(objs[0]["embedding"], dtype=np.float32)
        encoding = face_service.l2_normalize(raw_emb).tolist()
        
        # Check if user already exists
        result = await db.execute(select(RegisteredFace).where(RegisteredFace.name == request.name))
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="User already exists")

        # Save to DB as pure vector
        new_face = RegisteredFace(
            owner_id=request.owner_id,
            name=request.name,
            role=request.role,
            face_encoding=encoding
        )
        db.add(new_face)
        await db.commit()
        await db.refresh(new_face)

        # Cloud Storage Upload (Supabase Bucket)
        filename = f"{int(time.time())}_{new_face.id}.jpg"
        file_path = f"registration/{filename}"
        
        # Convert frame to bytes for upload
        _, img_encoded = cv2.imencode('.jpg', frame)
        img_bytes = img_encoded.tobytes()

        try:
            # Upload to Supabase 'face' bucket
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=img_bytes,
                file_options={"content-type": "image/jpeg"}
            )
            
            # Get Public URL
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            
            # Update user record with the Cloud URL
            new_face.image_path = public_url
            await db.commit()
            logger.info(f"Photo uploaded to cloud: {public_url}")
            
        except Exception as storage_err:
            logger.error(f"Cloud Storage Error: {storage_err}")
            # Fallback to local if cloud fails (optional)
            local_path = f"static/faces/{filename}"
            cv2.imwrite(local_path, frame)
            new_face.image_path = local_path
            await db.commit()
        
        return {"message": f"Successfully registered {request.name}", "status": "success", "image_url": new_face.image_path}

    except Exception as e:
        print(f"Registration Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    return {"message": f"User {user_id} deleted successfully"}


@app.get("/api/whatsapp/qr")
async def get_whatsapp_qr():
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:9000/qr", timeout=10.0)
            return resp.json()
    except Exception as e:
        return {"qr": None, "status": f"Gateway Error: {str(e)}"}

@app.post("/api/whatsapp/logout")
async def logout_whatsapp():
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post("http://localhost:9000/logout", timeout=10.0)
            return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

