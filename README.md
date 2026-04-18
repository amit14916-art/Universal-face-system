# 🛡️ Universal Face Sentinel (AI Vision System)

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
