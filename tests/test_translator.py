"""Unit tests for translation engine (Chinese to Vietnamese)."""

import pytest
from core.translator import TranslatorEngine


def test_translator_mock_mode():
    engine = TranslatorEngine(mock_mode=True)
    res = engine.translate_text("大家好，今天给大家分享一个非常实用的技巧。")
    assert "Xin chào mọi người" in res

    batch_res = engine.translate_batch(["你好", "谢谢"])
    assert batch_res == ["Xin chào", "Cảm ơn"]


def test_translator_empty_and_whitespace():
    engine = TranslatorEngine(mock_mode=True)
    assert engine.translate_text("") == ""
    assert engine.translate_text("   ") == ""


def test_translator_segments_structure():
    engine = TranslatorEngine(mock_mode=True)
    zh_segments = [
        {"id": 1, "start": 0.0, "end": 2.0, "text": "你好"},
        {"id": 2, "start": 2.5, "end": 4.5, "text": "谢谢"},
    ]
    vi_segments = engine.translate_segments(zh_segments)
    assert len(vi_segments) == 2
    assert vi_segments[0]["text_zh"] == "你好"
    assert vi_segments[0]["text_vi"] == "Xin chào"
    assert vi_segments[0]["start"] == 0.0
    assert vi_segments[0]["end"] == 2.0
    assert vi_segments[1]["text_zh"] == "谢谢"
    assert vi_segments[1]["text_vi"] == "Cảm ơn"


def test_translator_real_offline_model():
    """Test actual cached MarianMT model on CPU."""
    engine = TranslatorEngine(
        model_name_or_path="Helsinki-NLP/opus-mt-zh-vi",
        cache_dir="models",
        mock_mode=False
    )
    # Translate a simple sentence
    res = engine.translate_text("谢谢大家")
    assert len(res) > 0
    # Vietnamese diacritics check
    assert any(c in "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ" for c in res.lower()) or "cảm ơn" in res.lower()
