from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.database.db import init_db

# Initialize database tables
init_db()

app = FastAPI(title="CSRGO AI Video Studio", version="1.0.0", description="Fully local AI-powered educational video studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router, prefix="/api")

@app.on_event("startup")
def on_startup():
    # A restarted process cannot retain worker threads; expose interrupted work honestly.
    from backend.database.db import get_connection
    with get_connection() as conn:
        conn.execute("UPDATE projects SET status='failed', stage='interrupted', error_message='Backend restarted during production. Start production again.' WHERE status IN ('processing','queued')")

@app.get("/")
def root():
    return {"name": "CSRGO AI Video Studio", "status": "running", "version": "1.0.0", "docs": "/docs"}
