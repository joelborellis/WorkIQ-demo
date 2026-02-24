"""
Dev entry point.

Run with:
  python main.py
  uv run python main.py

In production, call uvicorn directly (see Dockerfile / Azure Container App config):
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
