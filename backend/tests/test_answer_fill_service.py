from __future__ import annotations

from app.core.models import AnswerPlacement, HomeworkParseResponse, OCRBlock, OCRResult, Uncertainty
from app.services.answer_fill_service import AnswerFillService


def test_collect_ocr_rows_ignores_title_and_keeps_answer_lines() -> None:
    svc = AnswerFillService()
    ocr = OCRResult(
        text="",
        blocks=[
            OCRBlock(
                text="Colourful toys\nWhat are they? Write.",
                bbox=[40, 80, 560, 210],
                order=1,
            ),
            OCRBlock(
                text="1 a ___\n3 ___ ___\n5 ___ ___",
                bbox=[40, 900, 560, 1120],
                order=2,
            ),
            OCRBlock(
                text="Date: ________",
                bbox=[680, 120, 1200, 220],
                order=3,
            ),
        ],
    )
    rows = svc._collect_ocr_candidate_rows(ocr, image_w=1280)
    assert len(rows) >= 3
    assert all(y > 700 for _, y, _, _ in rows)


def test_filter_model_boxes_by_ocr_candidates() -> None:
    svc = AnswerFillService()
    model_map = {
        1: (1030, 140, 120, 40),  # top-right "Date" area, should be removed
        2: (720, 1040, 320, 45),  # near OCR answer rows, should keep
    }
    ocr_rows = [
        (160, 980, 300, 42),
        (700, 1048, 340, 44),
        (140, 1120, 320, 44),
    ]
    out = svc._filter_model_map_by_ocr_candidates(model_map, ocr_rows)
    assert 1 not in out
    assert 2 in out


def test_filter_model_boxes_skips_when_ocr_candidates_too_few() -> None:
    svc = AnswerFillService()
    model_map = {
        1: (1030, 140, 120, 40),
        2: (720, 1040, 320, 45),
    }
    ocr_rows = [(160, 980, 300, 42)]
    out = svc._filter_model_map_by_ocr_candidates(model_map, ocr_rows)
    assert out == model_map


def test_build_answer_map_merges_reference_and_placements() -> None:
    svc = AnswerFillService()
    parsed = HomeworkParseResponse(
        question_meaning_zh="x\ny",
        reference_answer="1 bus\n2 ball",
        explanation_zh="ok",
        key_vocabulary=[],
        speak_units=[],
        uncertainty=Uncertainty(requires_review=False, confidence=0.9, reason=None),
        answer_placements=[
            AnswerPlacement(number=1, text="a bus", bbox_norm=[0.1, 0.1, 0.2, 0.2]),
            AnswerPlacement(number=3, text="a train", bbox_norm=[0.1, 0.3, 0.2, 0.4]),
        ],
        ocr_result=None,
    )
    out = svc._build_answer_map(parsed)
    assert out[1] == "a bus"
    assert out[2] == "ball"
    assert out[3] == "a train"


def test_parse_answer_map_compact_numbered_single_line() -> None:
    svc = AnswerFillService()
    out = svc._parse_answer_map("1 a doll;2 a bus;3 a ball;4 a teddy bear")
    assert out == {
        1: "a doll",
        2: "a bus",
        3: "a ball",
        4: "a teddy bear",
    }


def test_build_direct_placement_map() -> None:
    svc = AnswerFillService()
    parsed = HomeworkParseResponse(
        question_meaning_zh="x\ny",
        reference_answer="1 car",
        explanation_zh="ok",
        key_vocabulary=[],
        speak_units=[],
        uncertainty=Uncertainty(requires_review=False, confidence=0.9, reason=None),
        answer_placements=[
            AnswerPlacement(number=1, text="a car", bbox_norm=[0.1, 0.2, 0.3, 0.25]),
            AnswerPlacement(number=2, text=" ", bbox_norm=[0.4, 0.2, 0.6, 0.25]),
        ],
        ocr_result=None,
    )
    out = svc._build_direct_placement_map(parsed, image_w=1000, image_h=800)
    assert 1 in out
    assert 2 not in out
    text, box = out[1]
    assert text == "a car"
    assert box[2] >= 50


def test_layout_calibration_two_columns() -> None:
    svc = AnswerFillService()
    boxes = [
        (140, 980, 330, 44),
        (140, 1050, 330, 44),
        (140, 1120, 330, 44),
        (700, 980, 330, 44),
        (700, 1050, 330, 44),
        (700, 1120, 330, 44),
    ]
    calib = svc._build_layout_calibration(boxes, image_w=1280, image_h=1370)
    assert "default" in calib
    assert len(calib["columns"]) >= 2
    left_style = svc._resolve_text_style((160, 1000, 320, 44), calib)
    right_style = svc._resolve_text_style((740, 1000, 320, 44), calib)
    assert left_style["effective_h_cap"] >= 20
    assert right_style["effective_h_cap"] >= 20


def test_layout_calibration_fallback_when_insufficient_rows() -> None:
    svc = AnswerFillService()
    calib = svc._build_layout_calibration([(120, 900, 300, 38)], image_w=1280, image_h=1370)
    assert calib["columns"] == []
    style = svc._resolve_text_style((120, 900, 300, 38), calib)
    assert style["left_ratio"] == svc.TEXT_LEFT_RATIO
