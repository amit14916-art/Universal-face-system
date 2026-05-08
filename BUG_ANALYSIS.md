# Universal Face System - Bug Analysis & Improvement Report

**Date:** May 7, 2026  
**Analysis Scope:** Full codebase review (Python backend, API, database, frontend)

---

## 🔴 CRITICAL BUGS (Fix Immediately)

### 1. **Plaintext Password Storage (CRITICAL SECURITY)**
**Location:** [models.py](models.py#L18), [api.py](api.py#L386)  
**Severity:** CRITICAL  
**Issue:** Passwords are stored in plaintext in the database and compared directly without hashing.

```python
# VULNERABLE - api.py line 454
if not owner or owner.password != request.password:
    raise HTTPException(status_code=401, detail="Invalid credentials")

# Database stores plaintext
password = Column(String, nullable=False)  # models.py line 18
```

**Impact:** 
- Any database breach exposes all user passwords
- No security compliance (GDPR, HIPAA, SOC2)
- Users' passwords visible to admins

**Fix:**
```python
# Use bcrypt for password hashing
import bcrypt

# During signup (api.py)
hashed_password = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
new_owner = GymOwner(password=hashed_password, ...)

# During login (api.py)
if not owner or not bcrypt.checkpw(request.password.encode('utf-8'), owner.password.encode('utf-8')):
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

**Status:** ⛔ Not Started

---

### 2. **Hardcoded Admin Password (CRITICAL SECURITY)**
**Location:** [api.py](api.py#L510)  
**Severity:** CRITICAL  
**Issue:** Hardcoded default admin password "Goal@2026" in source code

```python
# api.py line 510
secret = os.getenv("ADMIN_PASSWORD", "Goal@2026")  # EXPOSED!
```

**Impact:**
- Password visible in Git history and compiled binaries
- Anyone with repo access can gain admin privileges
- Unchanged default allows unauthorized access

**Fix:**
```python
# .env file (never commit)
ADMIN_PASSWORD=<strong-random-string>

# Code
secret = os.getenv("ADMIN_PASSWORD")
if not secret:
    raise ValueError("ADMIN_PASSWORD environment variable not set")
if admin_pass != secret:
    raise HTTPException(status_code=401, detail="Unauthorized access")
```

**Status:** ⛔ Not Started

---

### 3. **Missing Input Validation & Rate Limiting**
**Location:** [api.py](api.py#L375-L393), [api.py](api.py#L440-L453)  
**Severity:** CRITICAL  
**Issue:** No validation on email format, password strength, or rate limiting

```python
# VULNERABLE - Accepts any input
class SignupRequest(BaseModel):
    gym_name: str           # No length check
    email: str              # No email validation
    mobile: str             # No phone validation
    password: str           # No strength requirements
```

**Vulnerabilities:**
- Brute force attacks on login endpoint (no rate limiting)
- Invalid email registrations accepted
- Weak passwords allowed
- SQL-like injection patterns possible in string fields

**Fix:**
```python
from pydantic import BaseModel, EmailStr, Field, validator
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.util import get_remote_address

class SignupRequest(BaseModel):
    gym_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr  # Validates email format
    mobile: str = Field(..., regex=r"^\+?[1-9]\d{1,14}$")  # E.164 format
    password: str = Field(..., min_length=12)
    
    @validator('password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v): raise ValueError('Need uppercase')
        if not any(c.isdigit() for c in v): raise ValueError('Need digit')
        if not any(c in '!@#$%^&*' for c in v): raise ValueError('Need special char')
        return v

# Add rate limiting middleware
@app.post("/api/auth/login")
@limiter.limit("5/minute")  # 5 attempts per minute per IP
async def login(request: Request, auth_request: AuthRequest, db: AsyncSession = Depends(get_db)):
    ...
```

**Status:** ⛔ Not Started

---

### 4. **No Authentication on Critical Endpoints**
**Location:** [api.py](api.py#L330-L345) (camera operations), [api.py](api.py#L574+) (user operations)  
**Severity:** CRITICAL  
**Issue:** Many endpoints lack owner verification - any authenticated user can access other gym owners' data

```python
# VULNERABLE - Only takes owner_id as parameter, no auth check
@app.get("/api/users")
async def get_users(owner_id: int, db: AsyncSession = Depends(get_db)):
    # Attacker can change owner_id to any value
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.owner_id == owner_id))
```

**Impact:**
- User A can view/modify User B's camera feeds
- Cross-tenant data leak
- Unauthorized face data access

**Fix:**
```python
from fastapi.security import HTTPBearer, HTTPAuthCredential
import jwt

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthCredential = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        owner_id = payload.get("owner_id")
        if not owner_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return owner_id
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Modify endpoints
@app.get("/api/users")
async def get_users(db: AsyncSession = Depends(get_db), owner_id: int = Depends(get_current_user)):
    # Now owner_id comes from JWT, not user input
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.owner_id == owner_id))
```

**Status:** ⛔ Not Started

---

## 🟠 MAJOR BUGS (Fix in Next Sprint)

### 5. **Race Condition in Frame Streaming**
**Location:** [main.py](main.py#L140), [api.py](api.py#L195)  
**Severity:** MAJOR  
**Issue:** `last_frame` is updated without locking, causing potential corruption during streaming

```python
# Unsafe read/write in main.py (no lock)
self.last_frame = frame  # Line 140 - written without lock

# Read without lock in api.py
frame = node.last_frame  # Line 195
if frame is not None:
    ret, buffer = cv2.imencode('.jpg', frame, ...)  # Might read corrupted data
```

**Impact:**
- Streaming clients receive corrupted or partial frames
- MJPEG stream quality degradation
- Potential crashes during frame encoding

**Fix:**
```python
# main.py
import threading

self._frame_lock = threading.RLock()

# In _run_impl where frame is captured
with self._frame_lock:
    self.last_frame = frame

# api.py - gen_frames
if node_name in engine.global_nodes:
    node = engine.global_nodes[node_name]
    with node._frame_lock:  # Acquire lock before reading
        frame = node.last_frame
    if frame is not None:
        ret, buffer = cv2.imencode('.jpg', frame, ...)
```

**Status:** ⛔ Not Started

---

### 6. **Unbounded Job Queue Can Cause Memory Exhaustion**
**Location:** [main.py](main.py#L34)  
**Severity:** MAJOR  
**Issue:** Job queue has max size of 100, but no back-pressure or rejection logic

```python
JOB_QUEUE_MAXSIZE = int(os.environ.get("SENTINEL_JOB_QUEUE_MAX", "100"))
shared_job_queue = queue.Queue(maxsize=JOB_QUEUE_MAXSIZE)  # Line 34

# In processing loop:
shared_job_queue.put(job)  # BLOCKS if queue full - no timeout!
```

**Impact:**
- If face recognition slows down (GPU load), queue fills
- Frame capture thread blocks indefinitely
- Live stream becomes non-responsive
- Under high concurrent streams, system hangs

**Fix:**
```python
import queue

JOB_QUEUE_MAXSIZE = 100
JOB_QUEUE_TIMEOUT = 0.5  # seconds

# In capture loop where job is queued
try:
    shared_job_queue.put(job, timeout=JOB_QUEUE_TIMEOUT)
except queue.Full:
    log_print(f"[{self.name}] Job queue full, dropping frame to maintain FPS")
    # Optionally: drop oldest job
    try:
        shared_job_queue.get_nowait()
        shared_job_queue.put(job, block=False)
    except:
        pass
```

**Status:** ⛔ Not Started

---

### 7. **No Connection Pooling Management**
**Location:** [database.py](database.py#L35-L42)  
**Severity:** MAJOR  
**Issue:** Database connection pool size is fixed at 10, can exhaust under load

```python
# database.py
pool_size=10,           # Only 10 connections
max_overflow=5,         # Can have max 15 connections total
pool_recycle=60         # Connections recycled every 60 seconds
```

**Impact:**
- With 40+ API endpoints under concurrent load, connections exhaust
- New requests wait indefinitely for connection
- Database queries timeout
- Cascading failures in face recognition

**Fix:**
```python
# Use environment-based sizing
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
POOL_OVERFLOW = int(os.getenv("DB_POOL_OVERFLOW", "10"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

engine = create_async_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=POOL_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_pre_ping=True,
    pool_recycle=300  # Increased from 60
)
```

**Status:** ⛔ Not Started

---

### 8. **Uncaught Exception in Email Notification Thread**
**Location:** [api.py](api.py#L398-L438)  
**Severity:** MAJOR  
**Issue:** Exception in `send_admin_signup_notification` is caught but only logged

```python
# Line 394
asyncio.create_task(send_admin_signup_notification(new_owner))

# But if there's SMTP error or network issue, it's only logged
except Exception as e:
    logger.error(f"Failed to send admin notification: {e}")
```

**Impact:**
- Silent failures in background tasks
- Admin doesn't know about new signups
- No alerting if SMTP server is down

**Fix:**
```python
import logging

async def send_admin_signup_notification(owner):
    try:
        # ... email sending code ...
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error sending admin notification: {e}", exc_info=True)
        # Optionally: send Slack/PagerDuty alert
        await send_alert(f"Failed to notify admin about signup from {owner.email}")
    except Exception as e:
        logger.error(f"Unexpected error in notification: {e}", exc_info=True)
        raise  # Re-raise to surface the error
```

**Status:** ⛔ Not Started

---

## 🟡 MEDIUM BUGS (Fix Soon)

### 9. **No HTTPS/TLS Support**
**Location:** [api.py](api.py#L109-113)  
**Severity:** MEDIUM  
**Issue:** API runs over HTTP without encryption

```python
# CORS allows any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Defaults to "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Allows any header including Authorization!
)
```

**Impact:**
- Credentials transmitted in plaintext over network
- MITM attacks can intercept face biometric data
- Mobile apps vulnerable to app-level network sniffing

**Fix:**
```python
# Restrict CORS to known origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://yourdomain.com").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Deploy with HTTPS (nginx or reverse proxy)
# Enforce HSTS header
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response
```

**Status:** ⛔ Not Started

---

### 10. **User Enumeration Vulnerability**
**Location:** [api.py](api.py#L375-L380), [api.py](api.py#L440-L453)  
**Severity:** MEDIUM  
**Issue:** Different error messages for "user exists" vs "user not found" reveals user enumeration

```python
# VULNERABLE - Reveals registered users
result = await db.execute(select(GymOwner).where(GymOwner.email == request.email))
if result.scalars().first():
    raise HTTPException(status_code=400, detail="Email already registered")  # DIFFERENT MESSAGE

# Login also reveals this
if not owner or owner.password != request.password:
    raise HTTPException(status_code=401, detail="Invalid credentials")  # SAME MESSAGE - but delays reveal user exists
```

**Impact:**
- Attackers can enumerate valid email addresses
- Used in password reset attacks
- Can map all users in system

**Fix:**
```python
# Use generic error messages
raise HTTPException(status_code=400, detail="Invalid email or password")  # Same message for all failures

# Add artificial delay to defeat timing attacks
import asyncio
import random
await asyncio.sleep(random.uniform(0.5, 2.0))
```

**Status:** ⛔ Not Started

---

### 11. **DeepSort Silently Fails Without Fallback**
**Location:** [main.py](main.py#L30-33)  
**Severity:** MEDIUM  
**Issue:** If DeepSort import fails, entire system fails without graceful degradation

```python
try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
except ImportError:
    DeepSort = None
    DEEPSORT_AVAILABLE = False
    print("WARNING: DeepSort not found...")

# Later in code
self.tracker = (
    DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0)
    if DEEPSORT_AVAILABLE
    else None
)

# But no fallback tracking - uses None tracker
if self.tracker is None:
    # What happens here? No detection/tracking!
```

**Impact:**
- System runs but doesn't detect any faces
- Users think face detection is "broken"
- No warning about missing dependency

**Fix:**
```python
# Create fallback simple tracker (CENTROID-based)
class SimpleCentroidTracker:
    def __init__(self, max_disappeared=30):
        self.max_disappeared = max_disappeared
        self.tracked_objects = {}
        self.next_object_id = 0
    
    def register(self, centroid):
        self.tracked_objects[self.next_object_id] = centroid
        self.next_object_id += 1
    
    def update(self, detections):
        # Simple centroid matching (when DeepSort unavailable)
        ...

# Initialize with fallback
self.tracker = (
    DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0)
    if DEEPSORT_AVAILABLE
    else SimpleCentroidTracker()
)

if not DEEPSORT_AVAILABLE:
    log_print(f"WARNING: Using fallback centroid tracker (performance degraded)")
```

**Status:** ⛔ Not Started

---

### 12. **No Timeout on Async Operations**
**Location:** [main.py](main.py#L58-61), [face_service.py](face_service.py#L90+)  
**Severity:** MEDIUM  
**Issue:** Async database operations can hang indefinitely

```python
# main.py
ASYNC_OP_TIMEOUT_SEC = float(os.environ.get("SENTINEL_ASYNC_TIMEOUT", "120"))

def run_async(coro, timeout=ASYNC_OP_TIMEOUT_SEC):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=timeout)  # Can timeout with ThreadPoolExecutor
```

**Impact:**
- Database query hangs (network issue) blocks face recognition
- Worker threads hang indefinitely
- System becomes unresponsive

**Fix:**
```python
# Add timeout with better error handling
async def process_tracker_crop(...):
    try:
        async with asyncio.timeout(30):  # Python 3.11+
            async with AsyncSessionLocalBG() as session:
                query = select(RegisteredFace).where(...)
                result = await session.execute(query)
    except asyncio.TimeoutError:
        logger.error(f"pgvector search timeout for track {track_id}")
        return None, "Search Timeout"
```

**Status:** ⛔ Not Started

---

### 13. **No ONVIF URL Validation Before Saving**
**Location:** [api.py](api.py#L241-307)  
**Severity:** MEDIUM  
**Issue:** Camera URLs are saved without validation - invalid URLs cause crashes later

```python
# No validation before saving to database
camera_node = CameraNode(
    owner_id=request.owner_id,
    name=node_name,
    url=final_url,  # Not validated!
    use_onvif=request.use_onvif,
    # ...
)
db.add(camera_node)
await db.commit()

# Later when loading - crashes if URL invalid
node = engine.SentinelNode(url, name)  # URL parsing fails here!
```

**Impact:**
- Invalid URLs cause frame capture to fail
- No clear error message to user
- Camera node never connects

**Fix:**
```python
from urllib.parse import urlparse
import asyncio

async def validate_camera_url(url: str, timeout: int = 5) -> bool:
    """Test if camera URL is accessible"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['rtsp', 'http', 'https']:
            return False
        
        # For RTSP, try to open stream briefly
        if parsed.scheme == 'rtsp':
            import cv2
            cap = cv2.VideoCapture(url)
            await asyncio.sleep(timeout)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                return ret
        return True
    except Exception as e:
        logger.error(f"Invalid camera URL {url}: {e}")
        return False

# In add_node endpoint
if not await validate_camera_url(final_url):
    raise HTTPException(status_code=400, detail="Camera URL is not accessible")
```

**Status:** ⛔ Not Started

---

## 🔵 PERFORMANCE ISSUES (Fix Later)

### 14. **pgvector Search Not Index-Optimized**
**Location:** [face_service.py](face_service.py#L135)  
**Severity:** PERFORMANCE  
**Issue:** pgvector queries use linear scan instead of HNSW index

```python
# face_service.py line 135 - does full table scan
query = select(RegisteredFace).where(
    RegisteredFace.owner_id == owner_id,
    RegisteredFace.face_encoding.l2_distance(embedding) < 1.40,  # Full scan!
).order_by(RegisteredFace.face_encoding.l2_distance(embedding)).limit(1)
```

**Impact:**
- O(n) query time for each face detection
- At 1000 faces: each recognition takes ~100ms
- At 10 cameras × 5 fps: 50 queries/sec × 100ms = 5s latency

**Fix:**
```sql
-- Add HNSW index in migration
CREATE INDEX idx_face_encoding_hnsw 
ON registered_faces USING hnsw (face_encoding l2_ops)
WITH (m=16, ef_construction=200);

-- Optionally: partial index for active only
CREATE INDEX idx_face_encoding_active 
ON registered_faces USING hnsw (face_encoding l2_ops)
WHERE is_active = true AND is_blacklisted = false;
```

**Benefits:**
- O(log n) search time
- At 1000 faces: ~10ms per search
- Scales to 100k+ faces

**Status:** ⛔ Not Started

---

### 15. **API Response Times Not Logged/Monitored**
**Location:** [api.py](api.py#L165-171)  
**Severity:** PERFORMANCE  
**Issue:** No performance monitoring middleware

```python
# Current logging only shows request/response, not time
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"INCOMING: {request.method} {request.url}")
    response = await call_next(request)  # No timing!
    logger.info(f"OUTGOING: {request.method} {request.url} -> {response.status_code}")
```

**Fix:**
```python
import time
from prometheus_client import Counter, Histogram

REQUEST_TIME = Histogram('request_duration_seconds', 'Request duration', ['method', 'endpoint'])
REQUEST_COUNT = Counter('requests_total', 'Total requests', ['method', 'endpoint', 'status'])

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as e:
        status = 500
        raise
    finally:
        duration = time.time() - start
        endpoint = request.url.path
        REQUEST_TIME.labels(method=request.method, endpoint=endpoint).observe(duration)
        REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=status).inc()
        
        if duration > 1.0:  # Slow request
            logger.warning(f"SLOW: {request.method} {endpoint} took {duration:.2f}s")
```

**Status:** ⛔ Not Started

---

## 🟢 RECOMMENDATIONS

### Architecture Improvements

| Priority | Item | Effort | Benefit |
|----------|------|--------|---------|
| **P0** | Implement bcrypt password hashing | 2 hours | Critical security fix |
| **P0** | Remove hardcoded admin password | 1 hour | Critical security fix |
| **P0** | Add JWT token-based auth | 4 hours | Eliminate owner_id parameter vulnerability |
| **P0** | Add input validation & rate limiting | 3 hours | Prevent brute force/injection |
| **P1** | Fix race condition in frame streaming | 1 hour | Improve stream stability |
| **P1** | Add job queue back-pressure | 2 hours | Prevent system hangs |
| **P1** | Implement pgvector HNSW index | 1 hour | 10x recognition speed improvement |
| **P1** | Add HTTPS/TLS support | 2 hours | Encrypt credentials in transit |
| **P2** | Add monitoring/metrics | 4 hours | Visibility into production |
| **P2** | Implement circuit breaker for SMTP | 2 hours | Graceful fallback for email |

### Infrastructure

1. **Deploy Behind Reverse Proxy (nginx/HAProxy)**
   - Terminate TLS/SSL
   - Rate limiting
   - Request buffering
   - Compression

2. **Use Docker Secrets for Credentials**
   ```yaml
   environment:
     ADMIN_PASSWORD: /run/secrets/admin_password
   secrets:
     admin_password:
       file: ./admin_password.txt  # Never commit!
   ```

3. **Add Monitoring Stack**
   - Prometheus for metrics
   - Grafana for dashboards
   - Alert on slow pgvector queries, dropped frames, failed connections

4. **Database Optimization**
   ```sql
   CREATE INDEX idx_owner_id ON registered_faces(owner_id) WHERE is_active = true;
   CREATE INDEX idx_attendance_timestamp ON attendance_logs(owner_id, timestamp DESC);
   ANALYZE registered_faces;
   ```

### Testing

- [ ] Add unit tests for authentication (password hashing)
- [ ] Integration tests for multi-owner data isolation
- [ ] Load test: 10 concurrent streams × 5 fps = 50 face recognitions/sec
- [ ] Penetration test: SQL injection, CORS bypass, JWT tampering

---

## Summary

**Total Bugs Found:** 15  
**Critical:** 4 (Security)  
**Major:** 4 (Functionality)  
**Medium:** 4 (Security/Stability)  
**Performance:** 3

**Estimated Fix Time:**
- Critical: 12 hours
- Major: 8 hours
- Medium: 10 hours

**Recommendation:** Fix all P0 (critical) items before production deployment.

