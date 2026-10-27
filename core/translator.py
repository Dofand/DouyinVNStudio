"""Translation engine translating Chinese subtitles to Vietnamese using Helsinki-NLP/opus-mt-zh-vi."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "Helsinki-NLP/opus-mt-zh-vi"


def find_cached_snapshot(model_name: str, cache_dir: Optional[str | Path]) -> Optional[str]:
    """Find local snapshot folder for model if already cached to avoid HuggingFace network requests."""
    if not cache_dir:
        return None
    cache_path = Path(cache_dir).resolve()
    repo_folder = f"models--{model_name.replace('/', '--')}"
    snapshots_dir = cache_path / repo_folder / "snapshots"
    if snapshots_dir.exists() and snapshots_dir.is_dir():
        for snap in snapshots_dir.iterdir():
            if snap.is_dir() and (snap / "config.json").exists():
                return str(snap)
    return None


class TranslatorEngine:
    """Translates Chinese text segments to Vietnamese."""

    def __init__(
        self,
        model_name_or_path: str = DEFAULT_MODEL_NAME,
        cache_dir: Optional[str | Path] = None,
        device: str = "cpu",
        mock_mode: bool = False,
    ):
        self.model_name_or_path = model_name_or_path
        self.cache_dir = str(cache_dir) if cache_dir else None
        self.device = device
        self.mock_mode = mock_mode
        self._tokenizer = None
        self._model = None

    def _load_model(self):
        """Lazy load MarianMT model and tokenizer."""
        if self._model is not None and self._tokenizer is not None:
            return self._tokenizer, self._model

        if self.mock_mode:
            logger.info("Chạy chế độ Translator Mock (không nạp model MarianMT).")
            return None, None

        from transformers import MarianMTModel, MarianTokenizer

        snapshot_path = find_cached_snapshot(self.model_name_or_path, self.cache_dir)
        load_target = snapshot_path or self.model_name_or_path
        local_only = bool(snapshot_path)

        logger.info(f"Nạp mô hình dịch thuật từ: {load_target} (offline={local_only})...")
        self._tokenizer = MarianTokenizer.from_pretrained(
            load_target,
            cache_dir=self.cache_dir if not snapshot_path else None,
            local_files_only=local_only,
        )
        self._model = MarianMTModel.from_pretrained(
            load_target,
            cache_dir=self.cache_dir if not snapshot_path else None,
            local_files_only=local_only,
        )
        if self.device == "cuda":
            import torch
            if torch.cuda.is_available():
                self._model = self._model.to("cuda")

        return self._tokenizer, self._model

    def translate_text(self, text_zh: str) -> str:
        """Translate a single Chinese string into Vietnamese."""
        text_zh = text_zh.strip()
        if not text_zh:
            return ""

        if self.mock_mode:
            # Deterministic dictionary for known mock texts and fallback
            mock_dict = {
                "大家好，今天给大家分享一个非常实用的技巧。": "Xin chào mọi người, hôm nay tôi sẽ chia sẻ một mẹo rất hữu ích.",
                "如果觉得有用，请点赞收藏关注我。": "Nếu thấy hữu ích, hãy bấm thích, lưu lại và theo dõi tôi nhé.",
                "我们下期视频再见！": "Hẹn gặp lại các bạn trong video tiếp theo!",
                "你好": "Xin chào",
                "谢谢": "Cảm ơn",
                "再见": "Tạm biệt",
            }
            if text_zh in mock_dict:
                return mock_dict[text_zh]
            return f"[Dịch]: {text_zh}"

        tokenizer, model = self._load_model()
        import torch

        inputs = tokenizer([text_zh], return_tensors="pt", padding=True, truncation=True)
        if self.device == "cuda" and torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        translated_tokens = model.generate(**inputs, max_length=128, num_beams=4)
        translated_text = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        return translated_text.strip()

    def translate_batch(
        self,
        texts: List[str],
        batch_size: int = 8,
    ) -> List[str]:
        """Translate a batch of Chinese strings."""
        if not texts:
            return []

        if self.mock_mode:
            return [self.translate_text(t) for t in texts]

        tokenizer, model = self._load_model()
        import torch

        results: List[str] = []
        for i in range(0, len(texts), batch_size):
            batch = [t if t.strip() else "..." for t in texts[i : i + batch_size]]
            inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
            if self.device == "cuda" and torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}

            translated_tokens = model.generate(**inputs, max_length=128, num_beams=4)
            translated_batch = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)
            for orig, trans in zip(texts[i : i + batch_size], translated_batch):
                clean_trans = trans.strip()
                if not orig.strip():
                    results.append("")
                elif not clean_trans:
                    results.append(orig)  # Fallback to original text if translation returned empty
                else:
                    results.append(clean_trans)
        return results

    def translate_segments(
        self,
        zh_segments: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Translates a list of Chinese segments into bilingual segments.
        Returns: [{"id": 1, "start": 0.0, "end": 2.5, "text_zh": "...", "text_vi": "..."}]
        """
        if not zh_segments:
            return []

        if progress_callback:
            progress_callback(5, "Đang chuẩn bị mô hình dịch thuật Trung - Việt...")

        total = len(zh_segments)
        texts_zh = [s.get("text", s.get("text_zh", "")).strip() for s in zh_segments]

        batch_size = 4
        translated_vi: List[str] = []

        for i in range(0, total, batch_size):
            if is_cancelled and is_cancelled():
                logger.info("Quá trình dịch bị hủy bởi người dùng.")
                break

            batch_texts = texts_zh[i : i + batch_size]
            batch_vi = self.translate_batch(batch_texts, batch_size=batch_size)
            translated_vi.extend(batch_vi)

            if progress_callback:
                pct = min(95, int(10 + (len(translated_vi) / total) * 85))
                preview = batch_vi[0][:20] if batch_vi else ""
                progress_callback(pct, f"Đang dịch câu {len(translated_vi)}/{total}: {preview}...")

        output_segments: List[Dict[str, Any]] = []
        for idx, (orig, vi_text) in enumerate(zip(zh_segments, translated_vi), start=1):
            text_zh = orig.get("text", orig.get("text_zh", "")).strip()
            # Clean Vietnamese text
            final_vi = vi_text.strip() if vi_text.strip() else text_zh
            output_segments.append({
                "id": idx,
                "start": orig.get("start", 0.0),
                "end": orig.get("end", 0.0),
                "text_zh": text_zh,
                "text_vi": final_vi,
                "verified": False,
            })

        if progress_callback:
            progress_callback(100, f"Đã dịch thành công {len(output_segments)} câu sang tiếng Việt.")

        return output_segments
