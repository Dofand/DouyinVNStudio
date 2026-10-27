"""Task repository for SQLite database persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from storage.database import get_db_connection, init_db


class SubtitleItem(BaseModel):
    """Represents a single subtitle unit."""
    id: int
    start: float  # in seconds
    end: float    # in seconds
    text_zh: str
    text_vi: str
    verified: bool = False


class TaskModel(BaseModel):
    """Full task data model."""
    id: str
    title: str
    source_type: str  # 'url' or 'file'
    source_path: str
    status: str = "pending"  # pending, acquiring, inspecting, transcribing, translating, review_ready, removing_subtitles, rendering, validating, completed, failed, cancelled
    progress: int = 0
    current_step: str = ""
    video_width: int = 0
    video_height: int = 0
    duration: float = 0.0
    fps: float = 0.0
    has_audio: bool = True
    subtitles: List[SubtitleItem] = Field(default_factory=list)
    output_video_path: str = ""
    output_srt_path: str = ""
    workspace_dir: str = ""
    error_message: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TaskRepository:
    """CRUD operations for tasks."""

    def __init__(self, db_file: Optional[Path] = None):
        self.db_file = db_file
        init_db(self.db_file)

    def _row_to_model(self, row: Any) -> TaskModel:
        subs_raw = row["subtitles_json"] or "[]"
        try:
            subs_data = json.loads(subs_raw)
            subs = [SubtitleItem(**item) for item in subs_data]
        except Exception:
            subs = []

        return TaskModel(
            id=row["id"],
            title=row["title"],
            source_type=row["source_type"],
            source_path=row["source_path"],
            status=row["status"],
            progress=row["progress"],
            current_step=row["current_step"],
            video_width=row["video_width"] or 0,
            video_height=row["video_height"] or 0,
            duration=row["duration"] or 0.0,
            fps=row["fps"] or 0.0,
            has_audio=bool(row["has_audio"]),
            subtitles=subs,
            output_video_path=row["output_video_path"] or "",
            output_srt_path=row["output_srt_path"] or "",
            workspace_dir=row["workspace_dir"] or "",
            error_message=row["error_message"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(self, task: TaskModel) -> TaskModel:
        conn = get_db_connection(self.db_file)
        subs_json = json.dumps([s.model_dump() for s in task.subtitles], ensure_ascii=False)
        with conn:
            conn.execute("""
                INSERT INTO tasks (
                    id, title, source_type, source_path, status, progress, current_step,
                    video_width, video_height, duration, fps, has_audio,
                    subtitles_json, output_video_path, output_srt_path, workspace_dir,
                    error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                task.id, task.title, task.source_type, task.source_path, task.status,
                task.progress, task.current_step, task.video_width, task.video_height,
                task.duration, task.fps, 1 if task.has_audio else 0,
                subs_json, task.output_video_path, task.output_srt_path,
                task.workspace_dir, task.error_message, task.created_at, task.updated_at
            ))
        conn.close()
        return task

    def get(self, task_id: str) -> Optional[TaskModel]:
        conn = get_db_connection(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return self._row_to_model(row)
        return None

    def list_all(self, limit: int = 100) -> List[TaskModel]:
        conn = get_db_connection(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?;", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_model(r) for r in rows]

    def update_progress(self, task_id: str, status: str, progress: int, current_step: str, error_message: str = "") -> None:
        conn = get_db_connection(self.db_file)
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("""
                UPDATE tasks
                SET status = ?, progress = ?, current_step = ?, error_message = ?, updated_at = ?
                WHERE id = ?;
            """, (status, progress, current_step, error_message, now, task_id))
        conn.close()

    def update_media_info(self, task_id: str, width: int, height: int, duration: float, fps: float, has_audio: bool) -> None:
        conn = get_db_connection(self.db_file)
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("""
                UPDATE tasks
                SET video_width = ?, video_height = ?, duration = ?, fps = ?, has_audio = ?, updated_at = ?
                WHERE id = ?;
            """, (width, height, duration, fps, 1 if has_audio else 0, now, task_id))
        conn.close()

    def update_subtitles(self, task_id: str, subtitles: List[SubtitleItem]) -> None:
        conn = get_db_connection(self.db_file)
        subs_json = json.dumps([s.model_dump() for s in subtitles], ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("""
                UPDATE tasks
                SET subtitles_json = ?, updated_at = ?
                WHERE id = ?;
            """, (subs_json, now, task_id))
        conn.close()

    def update_outputs(self, task_id: str, video_path: str, srt_path: str) -> None:
        conn = get_db_connection(self.db_file)
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("""
                UPDATE tasks
                SET output_video_path = ?, output_srt_path = ?, updated_at = ?
                WHERE id = ?;
            """, (video_path, srt_path, now, task_id))
        conn.close()

    def delete(self, task_id: str) -> bool:
        conn = get_db_connection(self.db_file)
        with conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?;", (task_id,))
            affected = cursor.rowcount
        conn.close()
        return affected > 0
