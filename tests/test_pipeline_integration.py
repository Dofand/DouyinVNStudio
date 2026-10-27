"""Integration tests for end-to-end video pipeline."""

import subprocess
import uuid
from pathlib import Path
import pytest

from config.settings import AppSettings
from core.pipeline import PipelineCancelledException, VideoProcessingPipeline
from storage.task_repository import SubtitleItem, TaskModel, TaskRepository


@pytest.fixture
def integration_env(tmp_path):
    settings = AppSettings()
    settings.workspace_dir = str(tmp_path / "workspace")
    settings.output_dir = str(tmp_path / "output")
    settings.logs_dir = str(tmp_path / "logs")
    settings.models_cache_dir = str(tmp_path / "models")
    settings.mock_mode = True
    settings.auto_pipeline = False
    settings.subtitle_remove_mode = "skip"
    settings.ensure_directories()

    repo = TaskRepository(db_file=tmp_path / "pipeline_test.db")

    # Generate source test video
    src_video = tmp_path / "video nguồn có dấu tiếng Việt.mp4"
    cmd = [
        settings.ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=480x854:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(src_video)
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    return settings, repo, src_video


def test_pipeline_review_and_resume(integration_env):
    settings, repo, src_video = integration_env

    task = TaskModel(
        id=str(uuid.uuid4()),
        title="IntegrationTask",
        source_type="file",
        source_path=str(src_video),
    )
    repo.create(task)

    pipeline = VideoProcessingPipeline(settings=settings, repository=repo)

    # 1. Run pipeline until review_ready
    res_task = pipeline.run_pipeline(task, start_from_stage="acquire")
    assert res_task.status == "review_ready"
    assert len(res_task.subtitles) > 0

    # User modifies subtitles
    res_task.subtitles[0].text_vi = "Bản dịch đã được người dùng chỉnh sửa hoàn hảo."
    repo.update_subtitles(res_task.id, res_task.subtitles)

    # 2. Resume pipeline from review
    final_task = pipeline.run_pipeline(res_task, start_from_stage="render_only")
    assert final_task.status == "completed"
    assert final_task.progress == 100
    assert Path(final_task.output_video_path).exists()
    assert Path(final_task.output_srt_path).exists()

    # Validate output SRT contains modified text
    srt_content = Path(final_task.output_srt_path).read_text(encoding="utf-8")
    assert "Bản dịch đã được người dùng chỉnh sửa hoàn hảo." in srt_content


def test_pipeline_cancellation(integration_env):
    settings, repo, src_video = integration_env

    task = TaskModel(
        id=str(uuid.uuid4()),
        title="CancelTask",
        source_type="file",
        source_path=str(src_video),
    )
    repo.create(task)

    pipeline = VideoProcessingPipeline(settings=settings, repository=repo)
    pipeline.cancel()  # Immediately cancel

    res_task = pipeline.run_pipeline(task)
    assert res_task.status == "cancelled"


def test_pipeline_full_auto_delogo(integration_env):
    """Test fully automated pipeline with delogo subtitle removal in 1 single pass."""
    settings, repo, src_video = integration_env
    settings.auto_pipeline = True
    settings.subtitle_remove_mode = "ffmpeg_delogo"

    task = TaskModel(
        id=str(uuid.uuid4()),
        title="FullAutoTask",
        source_type="file",
        source_path=str(src_video),
    )
    repo.create(task)

    pipeline = VideoProcessingPipeline(settings=settings, repository=repo)
    final_task = pipeline.run_pipeline(task, start_from_stage="acquire")

    assert final_task.status == "completed"
    assert final_task.progress == 100
    assert Path(final_task.output_video_path).exists()
    assert Path(final_task.output_srt_path).exists()
    assert Path(final_task.output_video_path).stat().st_size > 0
