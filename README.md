# 🛡️ Universal Face Sentinel (AI Vision System)
Universal Face System (Face Sentinel Enterprise)

![JavaScript](https://img.shields.io/badge/language-JavaScript-yellow.svg)
![Runtime](https://img.shields.io/badge/runtime-Node.js-green.svg)
![Engine](https://img.shields.io/badge/engine-Computer%20Vision-blue.svg)

An enterprise-grade, local-first computer vision attendance and facial verification engine designed for sub-second biometric extraction and synchronous edge-to-cloud logging.

---

## 🏗️ Functional Core

- **Biometric Extraction Pipeline:** Employs optimized facial landmark extraction vectors via local models (`face-api.js` / native bindings) to perform verification without heavy cloud latency.
- **Local-First Caching Strategy:** Saves active structural signatures on edge databases to guarantee 100% operational uptime for commercial client ecosystems (such as gyms, retail, corporate entry) even during network drops.
- **State Synchronizer:** Runs decoupled worker intervals to securely batch-upload off-line access matrices to central cloud instances once connectivity resumes.

---

## 🗂️ System Anatomy

```text
universal_face_system/
├── src/
│   ├── index.js             # Main server startup & hardware integration
│   ├── middleware/          # Access management and validation filters
│   ├── recognition/         # Frame capturing & facial vector extraction
│   └── database/            # Local data caching schemas
├── public/                  # Real-time WebUI video stream templates
├── config.json              # Frame sampling configurations & tolerances
└── package.json             # Engine script and runtime configuration
A high-performance, real-time biometric identification and tracking system built with **Deep Learning** and **Asynchronous Python**. This system is designed for multi-camera environments to detect, identify, and track individuals with high precision using the DeepSort algorithm.

---

## 🚀 Core Features
* **Real-time Detection:** High-speed face detection using OpenCV and dlib.
* **Intelligent Tracking:** Implements **DeepSort** for unique ID assignment and frame-to-frame persistence.
* **Async Architecture:** Built on **FastAPI** with asynchronous processing to handle high-concurrency video streams.
* **Database Integration:** Seamlessly syncs identified logs with **PostgreSQL/Supabase**.
* **Security First:** Designed for enterprise-level monitoring with robust error logging (`sentinel.log`).

---

## 🛠️ Tech Stack
* **Language:** Python 3.10+
* **AI/ML Frameworks:** DeepSort, Face Recognition, TensorFlow (Back-end logic)
* **Web Framework:** FastAPI (Asynchronous)
* **Computer Vision:** OpenCV
* **Database:** SQLAlchemy / PostgreSQL

---

## 📂 Project Structure
```bash
├── frontend/          # Web dashboard for monitoring
├── models/            # Pre-trained deep learning weights
├── static/            # Static assets and UI components
├── api.py             # FastAPI endpoints
├── face_service.py    # Core AI logic & feature extraction
├── database.py        # DB schema & connection logic
├── main.py            # System entry point
└── requirements.txt   # Dependencies
