"""Unit tests for SQLite database and task repository."""

import uuid
from pathlib import Path
import pytest

from storage.task_repository import SubtitleItem, TaskModel, TaskRepository


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_douyin.db"
    return TaskRepository(db_file=db_file)


def test_create_and_get_task(repo):
    task_id = str(uuid.uuid4())
    task = TaskModel(
        id=task_id,
        title="Test Task 1",
        source_type="file",
        source_path="c:/test/sample.mp4",
        status="pending",
    )
    repo.create(task)

    fetched = repo.get(task_id)
    assert fetched is not None
    assert fetched.id == task_id
    assert fetched.title == "Test Task 1"
    assert fetched.status == "pending"


def test_update_progress_and_subtitles(repo):
    task_id = str(uuid.uuid4())
    task = TaskModel(
        id=task_id,
        title="Test Task 2",
        source_type="url",
        source_path="https://v.douyin.com/test/",
    )
    repo.create(task)

    repo.update_progress(task_id, status="translating", progress=50, current_step="Đang dịch")
    subs = [
        SubtitleItem(id=1, start=0.0, end=2.0, text_zh="你好", text_vi="Xin chào", verified=True)
    ]
    repo.update_subtitles(task_id, subs)

    updated = repo.get(task_id)
    assert updated.status == "translating"
    assert updated.progress == 50
    assert len(updated.subtitles) == 1
    assert updated.subtitles[0].text_vi == "Xin chào"
    assert updated.subtitles[0].verified is True


def test_list_and_delete(repo):
    task_id = str(uuid.uuid4())
    task = TaskModel(
        id=task_id,
        title="To be deleted",
        source_type="file",
        source_path="test.mp4",
    )
    repo.create(task)
    assert len(repo.list_all()) >= 1

    del_ok = repo.delete(task_id)
    assert del_ok is True
    assert repo.get(task_id) is None
