import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import func, or_
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uvicorn
import asyncio
import time
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import queue

_APP_START_MONOTONIC: float | None = None

from database import AsyncSessionLocal, init_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === JWT & AUTHENTICATION SETUP ===
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-DO-NOT-USE-THIS!")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

if os.getenv("JWT_SECRET") is None:
    logger.warning("⚠️  JWT_SECRET not set! Using insecure default. Set JWT_SECRET environment variable.")

security = HTTPBearer()

def create_access_token(owner_id: int, gym_name: str) -> str:
    """Create JWT token for authenticated user"""
    payload = {
        "owner_id": owner_id,
        "gym_name": gym_name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """Verify JWT token and return owner_id"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        owner_id: int = payload.get("owner_id")
        if owner_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return owner_id
    except JWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# === RATE LIMITING ===
limiter = Limiter(key_func=get_remote_address)

from models import RegisteredFace, AttendanceLog, GymOwner
import face_service
import main as engine # Integrated with the Sentinel Engine
import onvif_utils
import base64
import numpy as np
import cv2
from pydantic import BaseModel, EmailStr, Field, validator
from supabase import create_client, Client

# Supabase Storage Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "face"

class WorkoutSaveRequest(BaseModel):
    owner_id: int = Field(..., gt=0)
    member_id: int = Field(..., gt=0)
    exercise_name: str = Field(..., min_length=1, max_length=100)
    reps: int = Field(..., ge=0)
    avg_accuracy: int = Field(..., ge=0, le=100)

class RegisterRequest(BaseModel):
    owner_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=2, max_length=100)
    role: str = Field(default="member", max_length=50)
    image_base64: str

class RenameRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)

class BlacklistRequest(BaseModel):
    is_blacklisted: bool

class NodeRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    url: str = Field(..., min_length=5)
    owner_id: int = Field(..., gt=0)
    brand: str = Field(default="Generic", max_length=50)
    use_p2p: bool = False
    p2p_uid: str = Field(default="", max_length=100)
    p2p_user: str = Field(default="admin", max_length=50)
    p2p_pass: str = Field(default="", max_length=100)
    use_onvif: bool = False
    onvif_port: int = Field(default=80, ge=1, le=65535)
    onvif_user: str = Field(default="admin", max_length=50)
    onvif_pass: str = Field(default="", max_length=100)

class AuthRequest(BaseModel):
    identifier: str = Field(..., min_length=5)
    password: str = Field(..., min_length=8)

class SignupRequest(BaseModel):
    gym_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    mobile: str = Field(..., regex=r"^\+?[1-9]\d{1,14}$")
    password: str = Field(..., min_length=12)
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Enforce strong password requirements"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v

class NotificationSettingsRequest(BaseModel):
    owner_id: int = Field(..., gt=0)
    gmail_enabled: bool = False
    alert_email: EmailStr = ""
    notify_on_entry: bool = True
    notify_on_expiry: bool = True

class SubscriptionRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    expiry_date: str
    plan_type: str = Field(..., max_length=50)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _APP_START_MONOTONIC
    _APP_START_MONOTONIC = time.monotonic()

    # Validate admin password is configured
    if not os.getenv("ADMIN_PASSWORD"):
        logger.warning("⚠️  WARNING: ADMIN_PASSWORD environment variable not set!")
        logger.warning("   Set it before deployment: export ADMIN_PASSWORD='<random-strong-password>'")

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
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}

# Enable CORS for frontend integration - RESTRICTED ORIGINS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
allowed_origins = [o.strip() for o in allowed_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"INCOMING: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(f"OUTGOING: {request.method} {request.url.path} -> {response.status_code} ({duration:.3f}s)")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"CRASH: {request.method} {request.url.path} -> {e} ({duration:.3f}s)", exc_info=True)
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
            with node._frame_lock:  # Acquire lock before reading
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
async def add_node(request: NodeRequest, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Add or update a camera node with ONVIF auto-discovery"""
    if request.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Validate ONVIF URL before saving
    if request.use_onvif:
        is_valid = await validate_camera_url(request.url, timeout=5)
        if not is_valid:
            raise HTTPException(status_code=400, detail="Camera URL is not accessible or invalid")
    
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

        # Persist to DB
        db_node = await db.execute(select(CameraNode).where(CameraNode.name == node_name))
        existing = db_node.scalars().first()
        
        if existing:
            existing.url = final_url
            existing.use_p2p = request.use_p2p
            existing.p2p_uid = request.p2p_uid
            existing.p2p_user = request.p2p_user
            existing.p2p_pass = request.p2p_pass
            existing.use_onvif = request.use_onvif
            existing.onvif_port = request.onvif_port
            existing.onvif_user = request.onvif_user
            existing.onvif_pass = request.onvif_pass
        else:
            from models import CameraNode
            new_node = CameraNode(
                owner_id=request.owner_id,
                name=node_name,
                url=final_url,
                use_p2p=request.use_p2p,
                p2p_uid=request.p2p_uid,
                p2p_user=request.p2p_user,
                p2p_pass=request.p2p_pass,
                use_onvif=request.use_onvif,
                onvif_port=request.onvif_port,
                onvif_user=request.onvif_user,
                onvif_pass=request.onvif_pass
            )
            db.add(new_node)
        
        await db.commit()
        return {"message": f"Node '{node_name}' registered successfully", "status": "success", "node_name": node_name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add node: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add node: {str(e)}")

async def validate_camera_url(url: str, timeout: int = 5) -> bool:
    """Test if camera URL is accessible"""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['rtsp', 'http', 'https']:
            return False
        
        # For RTSP, try to open stream briefly
        if parsed.scheme == 'rtsp':
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                return ret
        return True
    except Exception as e:
        logger.error(f"Invalid camera URL {url}: {e}")
        return False
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
@limiter.limit("3/minute")  # Rate limit signup to 3 attempts per minute
async def signup(request: Request, signup_request: SignupRequest, req: Request, db: AsyncSession = Depends(get_db)):
    try:
        # Check if user already exists
        result = await db.execute(select(GymOwner).where(GymOwner.email == signup_request.email))
        if result.scalars().first():
            # Generic error message to prevent user enumeration
            raise HTTPException(status_code=400, detail="Registration failed")
        
        # Hash the password with bcrypt
        hashed_password = bcrypt.hashpw(
            signup_request.password.encode('utf-8'), 
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')
        
        new_owner = GymOwner(
            gym_name=signup_request.gym_name,
            email=signup_request.email,
            mobile=signup_request.mobile,
            password=hashed_password,  # Store hashed password
            last_ip=req.headers.get("x-forwarded-for") or req.client.host
        )
        db.add(new_owner)
        await db.commit()
        await db.refresh(new_owner)
        
        # Trigger Admin Notification
        asyncio.create_task(send_admin_signup_notification(new_owner))
        
        return {"message": "Account created successfully", "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Signup failed")

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
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error sending admin notification: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in admin notification: {e}", exc_info=True)

@app.post("/api/auth/login")
@limiter.limit("5/minute")  # Maximum 5 login attempts per minute
async def login(request: Request, auth_request: AuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Match either email or mobile number
        result = await db.execute(
            select(GymOwner).where(
                or_(
                    GymOwner.email == auth_request.identifier,
                    GymOwner.mobile == auth_request.identifier
                )
            )
        )
        owner = result.scalars().first()
        
        # Use constant-time comparison to prevent timing attacks
        if not owner:
            # Dummy check to prevent timing attacks
            bcrypt.checkpw(auth_request.password.encode('utf-8'), b'$2b$12$invalid')
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password hash
        if not bcrypt.checkpw(auth_request.password.encode('utf-8'), owner.password.encode('utf-8')):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create JWT token
        token = create_access_token(owner.id, owner.gym_name)
        
        return {
            "message": "Login successful",
            "status": "success",
            "access_token": token,
            "token_type": "bearer",
            "owner_id": owner.id,
            "gym_name": owner.gym_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/api/workouts")
async def get_workouts(db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Get workouts for authenticated owner"""
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
async def save_workout(request: WorkoutSaveRequest, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Save workout session for authenticated owner"""
    if request.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
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
@limiter.limit("10/minute")  # Rate limit admin access
async def get_all_owners(admin_pass: str = None, db: AsyncSession = Depends(get_db)):
    # Get password from environment only
    secret = os.getenv("ADMIN_PASSWORD")
    
    if not secret:
        logger.error("ADMIN_PASSWORD not configured in environment")
        raise HTTPException(status_code=500, detail="Admin authentication not configured")
    
    if not admin_pass or admin_pass != secret:
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
async def export_attendance(db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Export attendance records for authenticated owner"""
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
async def get_users(
    db: AsyncSession = Depends(get_db),
    owner_id: int = Depends(get_current_user)  # Get from JWT token
):
    """Get all users for authenticated owner"""
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
async def get_logs(
    limit: int = 50, 
    offset: int = 0, 
    db: AsyncSession = Depends(get_db),
    owner_id: int = Depends(get_current_user)
):
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
async def get_stats(db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
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
async def get_user_activity(user_id: int, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Get user activity (owner only)"""
    # Verify ownership
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
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
async def update_user(user_id: int, request: UserUpdateRequest, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Update user profile (owner only)"""
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized - you can only modify your own users")
    
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
async def update_subscription(request: SubscriptionRequest, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Update member subscription (owner only)"""
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == request.user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="Member not found")
    if user.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized - you can only modify your own members")
    
    from datetime import datetime
    try:
        user.subscription_expiry = datetime.fromisoformat(request.expiry_date.replace("Z", "+00:00"))
        user.plan_type = request.plan_type
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid date format")
        
    return {"message": "Subscription updated successfully"}

@app.put("/api/settings/notifications")
async def update_notification_settings(request: NotificationSettingsRequest, db: AsyncSession = Depends(get_db), auth_owner_id: int = Depends(get_current_user)):
    """Update notification settings (authenticated owner only)"""
    if request.owner_id != auth_owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
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
async def rename_user(user_id: int, request: RenameRequest, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Rename user (owner only)"""
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    user.name = request.name
    await db.commit()
    return {"message": "User renamed successfully"}

@app.put("/api/users/{user_id}/blacklist")
async def toggle_blacklist(user_id: int, request: BlacklistRequest, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Toggle user blacklist status (owner only)"""
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    user.is_blacklisted = request.is_blacklisted
    await db.commit()
    return {"message": "Blacklist status updated"}

@app.post("/api/register")
async def register_user(request: RegisterRequest, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    try:
        if request.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
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
        result = await db.execute(select(RegisteredFace).where(RegisteredFace.name == request.name, RegisteredFace.owner_id == owner_id))
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    """Delete user (owner only)"""
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
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

