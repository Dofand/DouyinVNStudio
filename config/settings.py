"""Configuration management for DouyinVN Studio using Pydantic."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_system_binary(binary_name: str) -> str:
    """Detect binary in PATH or common Windows locations."""
    found = shutil.which(binary_name)
    if found:
        return str(Path(found).resolve())

    # Common Windows winget / chocolatey / local paths
    user_home = Path.home()
    common_search_paths = [
        user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages",
        Path("C:/ProgramData/chocolatey/bin"),
        Path("C:/ffmpeg/bin"),
        Path("C:/Program Files/ffmpeg/bin"),
    ]
    exe_name = f"{binary_name}.exe" if not binary_name.endswith(".exe") else binary_name
    for search_dir in common_search_paths:
        if search_dir.exists():
            matches = list(search_dir.glob(f"**/{exe_name}"))
            if matches:
                return str(matches[0].resolve())
    return ""


class SubtitleStyle(BaseModel):
    """Subtitle visual styling configuration for FFmpeg / ASS."""
    font_name: str = "Segoe UI"
    font_size: int = 24
    primary_color: str = "&H00FFFFFF"   # White (AABBGGRR)
    outline_color: str = "&H00000000"   # Black
    back_color: str = "&H80000000"      # Shadow / Box
    outline_width: float = 2.5
    bold: bool = True
    italic: bool = False
    alignment: int = 2                 # 2 = Bottom Center
    margin_v: int = 35                 # Vertical margin from bottom
    margin_l: int = 20
    margin_r: int = 20
    max_chars_per_line: int = 38


class AppSettings(BaseModel):
    """Global application settings."""
    # Executable paths
    ffmpeg_path: str = Field(default_factory=lambda: find_system_binary("ffmpeg"))
    ffprobe_path: str = Field(default_factory=lambda: find_system_binary("ffprobe"))
    vsr_path: str = ""

    # Processing directories
    workspace_dir: str = str(PROJECT_ROOT / "workspace")
    models_cache_dir: str = str(PROJECT_ROOT / "models")
    output_dir: str = str(PROJECT_ROOT / "output")
    logs_dir: str = str(PROJECT_ROOT / "logs")

    # AI Model Settings
    whisper_model: str = "tiny"  # tiny, base, small, medium
    whisper_device: str = "cpu"  # cpu, cuda, auto
    whisper_compute_type: str = "int8"  # int8, float16, float32

    translator_model: str = "Helsinki-NLP/opus-mt-zh-vi"
    translator_device: str = "cpu"

    # Subtitle removal
    subtitle_remove_mode: Literal["vsr", "ffmpeg_delogo", "ffmpeg_blur", "skip"] = "ffmpeg_delogo"
    subtitle_zone_mode: Literal["auto", "top", "bottom", "both", "custom"] = "auto"
    vsr_inpaint_mode: str = "sttn-auto"
    # Subtitle region coordinates [ymin, ymax, xmin, xmax] as float ratios (0.0 to 1.0)
    subtitle_area_ratio: Tuple[float, float, float, float] = (0.75, 0.95, 0.05, 0.95)

    # Subtitle burning style
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)

    # Pipeline behavior
    auto_pipeline: bool = True  # True means automatic full pipeline without pausing for review
    offline_mode: bool = False
    mock_mode: bool = False      # Safe testing mode without loading heavy AI models
    crf: int = 18                # FFmpeg H.264 quality (18-23 is visually lossless)
    preset: str = "medium"       # FFmpeg preset (veryfast, faster, fast, medium, slow)

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        for d in [self.workspace_dir, self.models_cache_dir, self.output_dir, self.logs_dir]:
            os.makedirs(d, exist_ok=True)

    def to_file(self, file_path: Optional[Path] = None) -> None:
        """Save settings to JSON file."""
        target = file_path or (PROJECT_ROOT / "config" / "settings.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, file_path: Optional[Path] = None) -> "AppSettings":
        """Load settings from JSON file or create defaults."""
        target = file_path or (PROJECT_ROOT / "config" / "settings.json")
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                settings = cls(**data)
                # If ffmpeg is not set or not found, try system lookup
                if not settings.ffmpeg_path or not Path(settings.ffmpeg_path).exists():
                    settings.ffmpeg_path = find_system_binary("ffmpeg")
                if not settings.ffprobe_path or not Path(settings.ffprobe_path).exists():
                    settings.ffprobe_path = find_system_binary("ffprobe")
                settings.ensure_directories()
                return settings
            except Exception:
                pass
        settings = cls()
        settings.ensure_directories()
        settings.to_file(target)
        return settings
