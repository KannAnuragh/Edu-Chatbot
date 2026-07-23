import subprocess
# Cache invalidation comment to force Render to re-run COPY command
import os
import sys

# 1. Run user creation and database setup
print("Starting database setup (create_users.py)...")
try:
    from core.config import settings
    # Print all env keys for debugging (without exposing values)
    print("Environment Variable Keys available in container:")
    db_keys = []
    for key in sorted(os.environ.keys()):
        if "DB" in key.upper() or "POSTGRES" in key.upper() or "URL" in key.upper():
            db_keys.append(key)
        else:
            print(f"  {key}")
    print("\nDatabase/URL related Environment Variables:")
    for key in db_keys:
        val = os.environ.get(key, "")
        # Mask password
        if "@" in val:
            prefix, rest = val.split("@", 1)
            if ":" in prefix:
                proto_user, _ = prefix.rsplit(":", 1)
                val = f"{proto_user}:***@{rest}"
        print(f"  {key} = {val}")
except Exception as e:
    print(f"Error printing settings: {e}")

subprocess.run([sys.executable, "create_users.py"], check=True)

# 2. Limit memory usage for PyTorch/Celery on Render free tier
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

print("Starting Celery background worker (solo pool)...")
celery_process = subprocess.Popen([
    sys.executable, "-m", "celery", "-A", "workers.celery_app", "worker", "--pool=solo", "--loglevel=info"
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
