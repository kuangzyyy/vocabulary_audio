"""Tests for photo OCR result -> normalized word/line/sentence data."""

from __future__ import annotations

from types import SimpleNamespace

from backend.app.services.photo_ocr import WORD_BOX_METHOD, _parse_ocr_result


def quad(x0: float, y0: float, x1: float, y1: float):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def make_result(
    *,
    boxes,
    txts,
    scores=None,
    word_results=None,
):
    return SimpleNamespace(
        boxes=boxes,
        txts=tuple(txts),
        scores=tuple(scores or [0.99] * len(txts)),
        word_results=word_results,
    )


def parse(result):
    return _parse_ocr_result(
        result,
        photo_id="a" * 32,
        filename="page.jpg",
        display_width=1000,
        display_height=1000,
        ocr_width=1000,
        ocr_height=1000,
    )


def test_word_results_are_used_directly_without_line_subdivision() -> None:
    result = make_result(
        boxes=[quad(100, 100, 900, 160)],
        txts=["Hello world. This is a test."],
        word_results=(
            (
                ("Hello", 0.99, quad(100, 100, 220, 160)),
                ("world.", 0.99, quad(235, 100, 360, 160)),
                ("This", 0.98, quad(390, 100, 460, 160)),
                ("is", 0.98, quad(470, 100, 500, 160)),
                ("a", 0.98, quad(510, 100, 530, 160)),
                ("test.", 0.98, quad(540, 100, 620, 160)),
            ),
        ),
    )

    data = parse(result)

    assert data.has_text is True
    assert data.has_english is True
    assert data.message is None
    assert data.quality_warning is None
    assert data.word_box_method == WORD_BOX_METHOD
    assert [word.text for word in data.words] == [
        "Hello",
        "world",
        "This",
        "is",
        "a",
        "test",
    ]
    assert len({word.bbox[0] for word in data.words}) == len(data.words)
    assert all(0 <= value <= 1 for word in data.words for value in word.bbox)
    assert all(word.sentence_id for word in data.words)
    assert [sentence.text for sentence in data.sentences] == [
        "Hello world.",
        "This is a test.",
    ]
    assert data.sentences[0].segments[0].bbox[0] == 0.1


def test_multi_line_sentence_has_one_segment_per_line() -> None:
    result = make_result(
        boxes=[quad(100, 100, 900, 160), quad(100, 180, 500, 240)],
        txts=["This is a long", "wrapped sentence."],
        word_results=(
            (
                ("This", 0.99, quad(100, 100, 170, 160)),
                ("is", 0.99, quad(180, 100, 210, 160)),
                ("a", 0.99, quad(220, 100, 240, 160)),
                ("long", 0.99, quad(250, 100, 320, 160)),
            ),
            (
                ("wrapped", 0.99, quad(100, 180, 220, 240)),
                ("sentence.", 0.99, quad(230, 180, 380, 240)),
            ),
        ),
    )

    data = parse(result)

    assert len(data.sentences) == 1
    sentence = data.sentences[0]
    assert sentence.text == "This is a long wrapped sentence."
    assert len(sentence.segments) == 2
    assert sentence.segments[0].line_id == "l-0"
    assert sentence.segments[1].line_id == "l-1"


def test_missing_word_boxes_do_not_create_fake_words() -> None:
    result = make_result(
        boxes=[quad(100, 100, 900, 160)],
        txts=["Hello world."],
        word_results=None,
    )

    data = parse(result)

    assert data.has_text is True
    assert data.has_english is True
    assert data.words == []
    assert data.message is not None
    assert "没有返回单词级坐标" in data.message
    assert data.quality_warning is not None
    assert "没有使用行框推算" in data.quality_warning
    assert len(data.sentences) == 1


def test_character_level_word_results_are_not_presented_as_words() -> None:
    result = make_result(
        boxes=[quad(100, 100, 900, 160)],
        txts=["Hello world"],
        word_results=(
            tuple(
                (char, 0.9, quad(100 + index * 30, 100, 125 + index * 30, 160))
                for index, char in enumerate("Hello world")
            ),
        ),
    )

    data = parse(result)

    assert data.words == []
    assert data.has_english is True
    assert data.message is not None
    assert "没有返回单词级坐标" in data.message


def test_non_english_text_has_explicit_message() -> None:
    result = make_result(
        boxes=[quad(100, 100, 900, 160)],
        txts=["12345 67890"],
        word_results=None,
    )

    data = parse(result)

    assert data.has_text is True
    assert data.has_english is False
    assert data.words == []
    assert "没有检测到英文" in (data.message or "")


def test_empty_ocr_result_has_no_fake_content() -> None:
    result = SimpleNamespace(boxes=None, txts=None, scores=None, word_results=None)

    data = parse(result)

    assert data.has_text is False
    assert data.has_english is False
    assert data.words == []
    assert data.lines == []
    assert data.sentences == []
    assert "没有识别到文字" in (data.message or "")


def test_low_confidence_adds_quality_warning() -> None:
    result = make_result(
        boxes=[quad(100, 100, 900, 160)],
        txts=["Hello world."],
        word_results=(
            (
                ("Hello", 0.2, quad(100, 100, 220, 160)),
                ("world.", 0.2, quad(235, 100, 360, 160)),
            ),
        ),
    )

    data = parse(result)

    assert data.quality_warning is not None
    assert "置信度较低" in data.quality_warning
