import subprocess
import os
import sys

# 1. Run user creation and database setup
print("Starting database setup (create_users.py)...")
try:
    from core.config import settings
    # Print the database URLs with password masked for debugging
    def mask_password(url: str) -> str:
        if "@" in url:
            prefix, rest = url.split("@", 1)
            if ":" in prefix:
                proto_user, _ = prefix.rsplit(":", 1)
                return f"{proto_user}:***@{rest}"
        return url

    print(f"DATABASE_URL: {mask_password(settings.DATABASE_URL)}")
    print(f"DATABASE_URL_SYNC: {mask_password(settings.DATABASE_URL_SYNC)}")
except Exception as e:
    print(f"Error printing settings: {e}")

subprocess.run([sys.executable, "create_users.py"], check=True)

# 2. Start Celery worker in the background
print("Starting Celery background worker...")
celery_process = subprocess.Popen([
    sys.executable, "-m", "celery", "-A", "workers.celery_app", "worker", "--loglevel=info"
])

# 3. Start FastAPI Uvicorn server in the foreground
port = os.environ.get("PORT", "8000")
print(f"Starting Uvicorn server on port {port}...")
try:
    subprocess.run([
        sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", port
    ], check=True)
finally:
    # Ensure Celery is terminated when the main process exits
    print("Shutting down Celery worker...")
    celery_process.terminate()
    try:
        celery_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        celery_process.kill()
