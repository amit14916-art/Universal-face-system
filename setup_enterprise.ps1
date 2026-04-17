# Enterprise SOTA Environment Setup Script
Write-Host "=========================================="
Write-Host " Setting up Enterprise SOTA Environment"
Write-Host "=========================================="

$VENV_DIR = "venv311"

# 1. Create Python 3.11 Virtual Environment
if (-Not (Test-Path -Path $VENV_DIR)) {
    Write-Host "-> Creating Python 3.11 Virtual Environment..."
    py -3.11 -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Python 3.11 is not installed or available via 'py -3.11'. Please ensure winget installation finished."
        exit 1
    }
} else {
    Write-Host "-> Python 3.11 Virtual Environment already exists."
}

# 2. Activate and Install SOTA Dependencies
Write-Host "-> Installing Enterprise Dependencies (DeepFace, FAISS, DeepSORT)..."
& .\$VENV_DIR\Scripts\pip install fastapi uvicorn sqlalchemy psycopg2-binary asyncpg google-cloud-vision python-dotenv python-multipart pydantic pillow
& .\$VENV_DIR\Scripts\pip install deepface faiss-cpu deep-sort-realtime opencv-python

Write-Host "=========================================="
Write-Host " Enterprise Environment Setup Complete!"
Write-Host "=========================================="
Write-Host "You can now run the enterprise version by doing:"
Write-Host "  .\$VENV_DIR\Scripts\python run_all.py`n"
