"""
SQLite storage for jobs and clips.
Auto-migrates missing columns on startup.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Float, Integer, String, Text, DateTime, ForeignKey, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(String(240), default="")
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    candidates_found: Mapped[int] = mapped_column(Integer, default=0)
    clips_rendered: Mapped[int] = mapped_column(Integer, default=0)
    caption_style: Mapped[str] = mapped_column(String(30), default="viral")
    transcript_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    clips: Mapped[list["Clip"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(16), ForeignKey("jobs.id"))
    index: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    duration: Mapped[float] = mapped_column(Float)
    score: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    hook: Mapped[str] = mapped_column(String(200))
    caption_style: Mapped[str] = mapped_column(String(30), default="viral")

    job: Mapped["Job"] = relationship(back_populates="clips")


_engine = None
_SessionLocal = None


def _migrate_schema(engine) -> None:
    """Add any missing columns to existing tables (SQLite-friendly)."""
    with engine.connect() as conn:
        # jobs table columns we care about
        rows = conn.execute(text("PRAGMA table_info(jobs)")).fetchall()
        if not rows:
            return  # table will be created by create_all
        existing = {row[1] for row in rows}  # column name is index 1

        alterations = []
        if "stage" not in existing:
            alterations.append("ALTER TABLE jobs ADD COLUMN stage VARCHAR(40) DEFAULT 'queued'")
        if "progress" not in existing:
            alterations.append("ALTER TABLE jobs ADD COLUMN progress FLOAT DEFAULT 0.0")
        if "message" not in existing:
            alterations.append("ALTER TABLE jobs ADD COLUMN message VARCHAR(240) DEFAULT ''")
        if "error" not in existing:
            alterations.append("ALTER TABLE jobs ADD COLUMN error TEXT")
        if "finished_at" not in existing:
            alterations.append("ALTER TABLE jobs ADD COLUMN finished_at DATETIME")
        if "transcript_path" not in existing:
            alterations.append("ALTER TABLE jobs ADD COLUMN transcript_path TEXT")
        if "result_json" not in existing:
            alterations.append("ALTER TABLE jobs ADD COLUMN result_json TEXT")
        if "caption_style" not in existing:
            alterations.append("ALTER TABLE jobs ADD COLUMN caption_style VARCHAR(30) DEFAULT 'viral'")

        for sql in alterations:
            conn.execute(text(sql))
        if alterations:
            conn.commit()


def init_db() -> None:
    global _engine, _SessionLocal
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{settings.db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(_engine)
    try:
        _migrate_schema(_engine)
    except Exception as e:
        # Non-fatal — worst case user deletes the db file
        import logging
        logging.getLogger(__name__).warning(f"Schema migration skipped: {e}")
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


def create_job(job_id: str, source_type: str, source: str, caption_style: str) -> None:
    session = get_session()
    try:
        job = Job(
            id=job_id,
            source_type=source_type,
            source=source,
            status="running",
            stage="queued",
            progress=0.0,
            message="Job queued",
            caption_style=caption_style,
        )
        session.add(job)
        session.commit()
    finally:
        session.close()


def update_job_progress(
    job_id: str,
    *,
    stage: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    status: str | None = None,
) -> None:
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if not job:
            return
        if stage is not None:
            job.stage = stage
        if progress is not None:
            job.progress = max(0.0, min(100.0, float(progress)))
        if message is not None:
            job.message = message[:240]
        if status is not None:
            job.status = status
        session.commit()
    finally:
        session.close()


def save_job_result(result: dict[str, Any], source_type: str, source: str, caption_style: str) -> None:
    session = get_session()
    try:
        job = session.get(Job, result["job_id"])
        if not job:
            job = Job(
                id=result["job_id"],
                source_type=source_type,
                source=source,
                caption_style=caption_style,
            )
            session.add(job)

        job.status = "completed"
        job.stage = "done"
        job.progress = 100.0
        job.message = f"Rendered {result.get('clips_rendered', 0)} clips"
        job.duration = result.get("duration")
        job.candidates_found = result.get("candidates_found", 0)
        job.clips_rendered = result.get("clips_rendered", 0)
        job.transcript_path = result.get("transcript_path")
        job.result_json = json.dumps(result)
        job.finished_at = datetime.utcnow()
        job.error = None

        for old in list(job.clips):
            session.delete(old)

        for c in result.get("clips", []):
            session.add(
                Clip(
                    job_id=result["job_id"],
                    index=c["index"],
                    path=c["path"],
                    start=c["start"],
                    end=c["end"],
                    duration=c["duration"],
                    score=c["score"],
                    title=c.get("title", ""),
                    hook=c.get("hook", ""),
                    caption_style=c.get("caption_style", caption_style),
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def mark_job_failed(job_id: str, error: str) -> None:
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if not job:
            return
        job.status = "failed"
        job.stage = "error"
        job.message = error[:240]
        job.error = error
        job.finished_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()



def cancel_job(job_id: str) -> bool:
    """Mark a running job as cancelled. Returns True if status was updated."""
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if not job:
            return False
        if job.status not in ("running", "pending", "queued"):
            return False
        job.status = "cancelled"
        job.stage = "cancelled"
        job.message = "Cancelled by user"
        job.finished_at = datetime.utcnow()
        session.commit()
        return True
    finally:
        session.close()


def is_job_cancelled(job_id: str) -> bool:
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if not job:
            return False
        return job.status == "cancelled"
    finally:
        session.close()


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    session = get_session()
    try:
        jobs = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(limit)).all()
        return [
            {
                "id": j.id,
                "source_type": j.source_type,
                "source": j.source,
                "status": j.status,
                "stage": j.stage,
                "progress": j.progress,
                "message": j.message,
                "duration": j.duration,
                "candidates_found": j.candidates_found,
                "clips_rendered": j.clips_rendered,
                "caption_style": j.caption_style,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ]
    finally:
        session.close()


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if not job:
            return None
        clips = [
            {
                "index": c.index,
                "path": c.path,
                "start": c.start,
                "end": c.end,
                "duration": c.duration,
                "score": c.score,
                "title": c.title,
                "hook": c.hook,
                "caption_style": c.caption_style,
            }
            for c in sorted(job.clips, key=lambda x: x.index)
        ]
        return {
            "id": job.id,
            "source_type": job.source_type,
            "source": job.source,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "message": job.message,
            "duration": job.duration,
            "candidates_found": job.candidates_found,
            "clips_rendered": job.clips_rendered,
            "caption_style": job.caption_style,
            "transcript_path": job.transcript_path,
            "error": job.error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "clips": clips,
        }
    finally:
        session.close()
