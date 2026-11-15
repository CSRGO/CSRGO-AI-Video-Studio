from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime
from backend.database.db import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True)
    topic = Column(Text, nullable=False)
    mode = Column(String(32), default="topic") # "topic" or "github"
    source_url = Column(String(1024), nullable=True)
    target_duration = Column(Integer, default=45) # seconds
    actual_duration = Column(Float, nullable=True)
    aspect_ratio = Column(String(16), default="9:16") # 9:16, 16:9, 1:1, 4:5
    resolution = Column(String(32), default="1080x1920")
    fps = Column(Integer, default=24)
    language = Column(String(32), default="en")
    voice = Column(String(64), default="af_bella")
    speaking_speed = Column(Float, default=1.0)
    style_slug = Column(String(64), default="swiss-motion")
    music_enabled = Column(Boolean, default=True)
    sfx_enabled = Column(Boolean, default=True)
    subtitles_enabled = Column(Boolean, default=True)
    draft_render = Column(Boolean, default=False)
    status = Column(String(32), default="draft") # draft, processing, completed, failed
    stage = Column(String(64), default="created")
    progress = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    output_video_path = Column(String(1024), nullable=True)
    preview_video_path = Column(String(1024), nullable=True)
    thumbnail_path = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RenderJob(Base):
    __tablename__ = "render_jobs"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), index=True, nullable=False)
    status = Column(String(32), default="queued") # queued, running, completed, failed, cancelled
    stage = Column(String(64), default="initialized")
    progress = Column(Integer, default=0) # 0 to 100
    message = Column(String(512), default="")
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

