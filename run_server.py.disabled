#!/usr/bin/env python3
"""Run Kratos AI Server with Dashboard"""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# Import Kratos API routes
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from api.routes import router as kratos_router

app = FastAPI(
    title="Kratos AI",
    description="Self-Healing Kubernetes Intelligence",
    version="0.1.0"
)

# Mount API routes
app.include_router(kratos_router)

# Serve dashboard static files
dashboard_dist = Path(__file__).parent / "dashboard" / "dist"
if dashboard_dist.exists():
    app.mount("/assets", StaticFiles(directory=dashboard_dist / "assets"), name="assets")
    
    @app.get("/")
    async def serve_dashboard():
        return FileResponse(dashboard_dist / "index.html")
    
    @app.get("/{path:path}")
    async def catch_all(path: str):
        # Check if it is an API route
        if path.startswith("api/"):
            return {"error": "Not found"}
        # Serve index.html for SPA routing
        return FileResponse(dashboard_dist / "index.html")

if __name__ == "__main__":
    print("Starting Kratos AI Server...")
    print("Dashboard: http://localhost:8080")
    print("API Docs:  http://localhost:8080/docs")
    uvicorn.run(app, host="0.0.0.0", port=8080)
