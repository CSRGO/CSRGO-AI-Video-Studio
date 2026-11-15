from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.database.db import init_db

# Initialize database tables
init_db()

app = FastAPI(title="CSRGO AI Video Studio", version="1.0.0", description="Fully local AI-powered educational video studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router, prefix="/api")

@app.on_event("startup")
def on_startup():
    import threading
    from backend.services.ollama_manager import ollama_manager
    threading.Thread(target=ollama_manager.verify_and_initialize, kwargs={"skip_smoke_test": True}, daemon=True).start()

@app.get("/")
def root():
    return {"name": "CSRGO AI Video Studio", "status": "running", "version": "1.0.0", "docs": "/docs"}
