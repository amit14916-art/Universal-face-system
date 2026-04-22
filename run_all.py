import multiprocessing
import subprocess
import time
import sys
import os

def run_api():
    print(">> Starting API and Dashboard...")
    try:
        # Use subprocess to run uvicorn to ensure it has its own process and environment
        subprocess.run([sys.executable, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "error"])
    except KeyboardInterrupt:
        pass

def run_recognition():
    print(">> Starting Face Recognition System...")
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    # Ensure current directory is in path
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("========================================")
    print("   UNIVERSAL FACE SYSTEM - READY")
    print("========================================")
    print("Dashboard: http://localhost:8000")
    print("Press Ctrl+C to stop everything")
    print("----------------------------------------")

    run_api()
