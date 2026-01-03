"""Minimal FastAPI application for testing agent-sandbox."""

from fastapi import FastAPI

app = FastAPI(title="Test Project", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
