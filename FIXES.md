# Universal Face System - Quick Fixes Guide

This file provides ready-to-implement fixes for the critical bugs identified in `BUG_ANALYSIS.md`.

---

## Fix #1: Password Hashing (Replace plaintext passwords)

### Step 1: Install bcrypt
```bash
pip install bcrypt
```

### Step 2: Update api.py - Signup Endpoint

**Replace:** Lines 375-395 in api.py

```python
import bcrypt

@app.post("/api/auth/signup")
async def signup(request: SignupRequest, req: Request, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(GymOwner).where(GymOwner.email == request.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Registration failed")  # Generic error
    
    # Hash the password with bcrypt
    hashed_password = bcrypt.hashpw(
        request.password.encode('utf-8'), 
        bcrypt.gensalt(rounds=12)
    ).decode('utf-8')
    
    new_owner = GymOwner(
        gym_name=request.gym_name,
        email=request.email,
        mobile=request.mobile,
        password=hashed_password,  # Store hashed password
        last_ip=req.headers.get("x-forwarded-for") or req.client.host
    )
    db.add(new_owner)
    await db.commit()
    await db.refresh(new_owner)
    
    # Trigger Admin Notification
    asyncio.create_task(send_admin_signup_notification(new_owner))
    
    return {"message": "Account created successfully", "status": "success"}
```

### Step 3: Update api.py - Login Endpoint

**Replace:** Lines 440-453 in api.py

```python
@app.post("/api/auth/login")
async def login(request: AuthRequest, db: AsyncSession = Depends(get_db)):
    # Match either email or mobile number
    result = await db.execute(
        select(GymOwner).where(
            or_(
                GymOwner.email == request.identifier,
                GymOwner.mobile == request.identifier
            )
        )
    )
    owner = result.scalars().first()
    
    # Verify password using bcrypt
    if not owner:
        # User not found - still use bcrypt verify to prevent timing attacks
        bcrypt.checkpw(request.password.encode('utf-8'), b'$2b$12$invalid')  # Dummy check
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check password hash
    if not bcrypt.checkpw(request.password.encode('utf-8'), owner.password.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "message": "Login successful", 
        "status": "success", 
        "owner_id": owner.id,
        "gym_name": owner.gym_name
    }
```

**Status:** Ready to implement ✅

---

## Fix #2: Remove Hardcoded Admin Password

### Step 1: Create .env file (DO NOT COMMIT)

```env
ADMIN_PASSWORD=YourSecureRandomPasswordHere_123!@#
```

### Step 2: Update api.py - Admin Endpoint

**Replace:** Lines 508-514 in api.py

```python
@app.get("/api/admin/owners")
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
```

### Step 3: Update startup check in api.py

**Add** to the lifespan function after `async def lifespan(app: FastAPI):`

```python
    # Validate admin password is configured
    if not os.getenv("ADMIN_PASSWORD"):
        print("⚠️  WARNING: ADMIN_PASSWORD environment variable not set!")
        print("   Set it before deployment: export ADMIN_PASSWORD='<random-strong-password>'")
```

**Status:** Ready to implement ✅

---

## Fix #3: Input Validation & Rate Limiting

### Step 1: Install packages

```bash
pip install email-validator slowapi pydantic
```

### Step 2: Update models in api.py

**Replace:** Lines 77-91 in api.py

```python
from pydantic import BaseModel, EmailStr, Field, validator
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

class AuthRequest(BaseModel):
    identifier: str  # Email or mobile
    password: str = Field(..., min_length=8, description="At least 8 characters")

class SignupRequest(BaseModel):
    gym_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr  # Validates email format automatically
    mobile: str = Field(..., regex=r"^\+?[1-9]\d{1,14}$")  # E.164 format
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

class RegisterRequest(BaseModel):
    owner_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=2, max_length=100)
    role: str = Field(default="member", max_length=50)
    image_base64: str
```

### Step 3: Update signup and login with rate limiting

**Replace login function in api.py** (around line 440):

```python
@app.post("/api/auth/login")
@limiter.limit("5/minute")  # Maximum 5 login attempts per minute
async def login(request: Request, auth_request: AuthRequest, db: AsyncSession = Depends(get_db)):
    # ... rest of login code ...
```

### Step 4: Add rate limiting middleware

**Add** after app creation (around line 158):

```python
from slowapi.errors import RateLimitExceeded

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )
```

**Status:** Ready to implement ✅

---

## Fix #4: Add Authentication Token (JWT)

### Step 1: Install JWT package

```bash
pip install python-jose python-multipart
```

### Step 2: Add JWT utilities to api.py

**Add** at the top of api.py:

```python
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi.security import HTTPBearer, HTTPAuthCredential

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

async def get_current_user(credentials: HTTPAuthCredential = Depends(security)) -> int:
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
```

### Step 3: Update login endpoint to return token

**Modify login function** (around line 440):

```python
@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, auth_request: AuthRequest, db: AsyncSession = Depends(get_db)):
    # ... existing validation code ...
    
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
```

### Step 4: Update protected endpoints

**Example - Replace get_users function** (around line 574):

```python
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
```

**Apply same pattern to all endpoints that take `owner_id` as parameter**

**Status:** Ready to implement ✅

---

## Fix #5: Race Condition in Frame Streaming

### Step 1: Add lock to SentinelNode

**Replace** SentinelNode.__init__ in main.py (around line 88):

```python
class SentinelNode:
    def __init__(self, source_id, name="Node", owner_id=None, rotation=None, use_p2p=False, p2p_uid="", p2p_user="admin", p2p_pass=""):
        self.source_id = source_id
        self.name = name
        self.owner_id = owner_id
        self.rotation = rotation 
        self.use_p2p = use_p2p
        self.p2p_uid = p2p_uid
        self.p2p_user = p2p_user
        self.p2p_pass = p2p_pass
        self.use_onvif = False
        self.onvif_port = 80
        self.onvif_user = "admin"
        self.onvif_pass = ""
        self.running = False
        self.status = "Initializing"
        self.tracker = (
            DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0)
            if DEEPSORT_AVAILABLE
            else None
        )
        self.cap = None
        self._frame_lock = threading.RLock()  # ADD THIS LINE
        self.last_frame = None
        self.fps = 0
        self.active_tracks = 0
```

### Step 2: Protect frame writes in capture loop

**Find where `self.last_frame = frame` is set** (search in main.py):

Replace with:
```python
        with self._frame_lock:  # Acquire lock before writing
            self.last_frame = frame
```

### Step 3: Protect frame reads in streaming

**Replace** gen_frames function in api.py (around line 195):

```python
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
        
        await asyncio.sleep(0.05)  # ~20 FPS for stability
```

**Status:** Ready to implement ✅

---

## Fix #6: Queue Back-Pressure

### Step 1: Update job queue handling

**Find** where `shared_job_queue.put(job)` is called in main.py and replace with:

```python
import queue

JOB_QUEUE_TIMEOUT = 0.5  # Drop frames if queue is full

try:
    shared_job_queue.put(job, timeout=JOB_QUEUE_TIMEOUT)
except queue.Full:
    log_print(f"[{self.name}] Job queue full, dropping frame to maintain stream FPS")
    # Try to drop oldest job and add new one
    try:
        old_job = shared_job_queue.get_nowait()
        log_print(f"[{self.name}] Dropped track {old_job[0]} to make room")
        shared_job_queue.put(job, block=False)
    except queue.Empty:
        pass  # Queue was just emptied by another thread
```

**Status:** Ready to implement ✅

---

## Fix #7: Add pgvector HNSW Index

### Step 1: Create database migration file

Create file: `migrations/add_pgvector_index.sql`

```sql
-- Add HNSW index for fast face similarity search
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_face_encoding_hnsw 
ON registered_faces USING hnsw (face_encoding l2_ops)
WITH (m=16, ef_construction=200);

-- Add partial index for faster queries on active users
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_face_encoding_active 
ON registered_faces USING hnsw (face_encoding l2_ops)
WHERE is_active = true AND is_blacklisted = false;

-- Gather statistics
ANALYZE registered_faces;
```

### Step 2: Run migration

```bash
# Connect to your PostgreSQL database
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f migrations/add_pgvector_index.sql
```

### Step 3: Update face_service.py to use the partial index

**Update** process_tracker_crop function (around line 135):

```python
        # Query now uses the HNSW index automatically
        query = select(RegisteredFace).where(
            RegisteredFace.owner_id == owner_id,
            RegisteredFace.is_active == True,           # Enables partial index
            RegisteredFace.is_blacklisted == False,    # Enables partial index
            RegisteredFace.face_encoding.l2_distance(embedding) < 1.40,
        ).order_by(RegisteredFace.face_encoding.l2_distance(embedding)).limit(1)
        
        result = await session.execute(query)
        p = result.scalars().first()
```

**Status:** Ready to implement ✅

---

## Testing Checklist

After implementing fixes, test:

- [ ] **Password Hashing**: Create new user, verify password hashed in DB, login works
- [ ] **Admin Password**: Set `ADMIN_PASSWORD` env var, verify admin endpoint requires it
- [ ] **Input Validation**: Try weak password (should fail), invalid email (should fail)
- [ ] **Rate Limiting**: Make 6 login attempts in 1 minute (6th should fail with 429)
- [ ] **JWT Auth**: Login gets token, use token in Authorization header for other endpoints
- [ ] **Frame Streaming**: Stream for 5 min, check for corrupted frames
- [ ] **Job Queue**: Run 10 concurrent streams, verify FPS maintained
- [ ] **pgvector Index**: Query 10,000 faces, verify < 50ms response time

---

## Deployment Checklist

```bash
# 1. Set environment variables
export ADMIN_PASSWORD="YourSecurePassword123!@#"
export JWT_SECRET="YourJWTSecret456$%^"

# 2. Install new dependencies
pip install -r requirements.txt

# 3. Create database indexes
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f migrations/add_pgvector_index.sql

# 4. Restart service
systemctl restart universal-face-system  # or docker-compose restart

# 5. Verify health
curl http://localhost:8000/health
```

