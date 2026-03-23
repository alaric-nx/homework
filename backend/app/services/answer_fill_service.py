from __future__ import annotations

import base64
import io
import os
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import logging
from typing import Any

from app.core.errors import AppError
from app.core.models import HomeworkParseResponse

logger = logging.getLogger(__name__)


@dataclass
class AnswerFillService:
    FILL_TEXT_COLOR = (220, 20, 20)
    # Ratio fallback for worksheets where line detection fails.
    LEFT_X_RATIO = 0.185
    RIGHT_X_RATIO = 0.56
    START_Y_RATIO = 0.806
    LINE_GAP_RATIO = 0.048
    FONT_RATIO = 0.024
    TEXT_TOP_RATIO = 0.16
    TEXT_LEFT_RATIO = 0.10
    TEXT_BASELINE_PULL = 0.35

    def fill_answers_to_image_base64_and_file(
        self, image_bytes: bytes, parsed: HomeworkParseResponse
    ) -> tuple[str, str]:
        try:
            from PIL import Image, ImageDraw
        except Exception as exc:
            raise AppError(
                "INTERNAL_ERROR", "Pillow is required for image answer filling."
            ) from exc

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise AppError("INVALID_REQUEST", "Invalid image bytes.") from exc

        answers = self._build_answer_map(parsed)
        logger.info(
            "answer_fill_parsed_answers keys=%s preview=%s",
            sorted(answers.keys()),
            parsed.reference_answer[:200].replace("\n", " "),
        )
        draw = ImageDraw.Draw(image)
        w, h = image.size
        font_size = max(18, int(min(w, h) * self.FONT_RATIO))
        direct_map = self._build_direct_placement_map(parsed, w, h)
        use_direct = len(direct_map) >= max(3, max(1, len(answers) // 2))
        logger.info(
            "answer_fill_direct mode=%s direct_count=%s answer_count=%s",
            use_direct,
            len(direct_map),
            len(answers),
        )

        line_map, ocr_map, model_map = self._build_line_map_fused(parsed, answers, w, h)
        if not line_map:
            line_map = self._build_ratio_line_map(answers, w, h)
        logger.info("answer_fill_lines line_map=%s", line_map)
        calib_source_boxes = [line for _, line in direct_map.values()] if use_direct else list(line_map.values())
        layout_calib = self._build_layout_calibration(calib_source_boxes, w, h)
        logger.info("answer_fill_layout_calib=%s", layout_calib)

        debug_points: list[tuple[int, int, int, int, str]] = []
        debug_ocr: list[tuple[int, int, int, int, str]] = []
        debug_model: list[tuple[int, int, int, int, str]] = []
        drawn_nums: set[int] = set()

        if use_direct:
            for num in sorted(direct_map.keys()):
                text, line = direct_map[num]
                self._draw_text_fit_line(
                    draw, text, line, w, h, font_size, layout_calib
                )
                debug_points.append((*line, f"{num}:{text}"))
                drawn_nums.add(num)

        for num in sorted(answers.keys()):
            if num in drawn_nums:
                continue
            text = answers.get(num)
            if text:
                line = line_map.get(num)
                if line is not None:
                    self._draw_text_fit_line(
                        draw, text, line, w, h, font_size, layout_calib
                    )
                    debug_points.append((*line, f"{num}:{text}"))
            o = ocr_map.get(num)
            m = model_map.get(num)
            if o is not None:
                debug_ocr.append((*o, f"OCR#{num}"))
            if m is not None:
                debug_model.append((*m, f"MODEL#{num}"))

        out = io.BytesIO()
        image.save(out, format="JPEG", quality=90)
        out_bytes = out.getvalue()
        file_path = self._write_output_file(out_bytes)
        self._write_debug_overlay(image, debug_points, debug_ocr, debug_model)
        return base64.b64encode(out_bytes).decode("utf-8"), str(file_path)

    def _build_direct_placement_map(
        self, parsed: HomeworkParseResponse, image_w: int, image_h: int
    ) -> dict[int, tuple[str, tuple[int, int, int, int]]]:
        out: dict[int, tuple[str, tuple[int, int, int, int]]] = {}
        for p in parsed.answer_placements:
            text = (p.text or "").strip()
            if not text:
                continue
            if not p.bbox_norm or len(p.bbox_norm) != 4:
                continue
            x0, y0, x1, y1 = p.bbox_norm
            try:
                ax0 = int(max(0, min(image_w - 2, round(x0 * image_w))))
                ay0 = int(max(0, min(image_h - 2, round(y0 * image_h))))
                ax1 = int(max(ax0 + 1, min(image_w - 1, round(x1 * image_w))))
                ay1 = int(max(ay0 + 1, min(image_h - 1, round(y1 * image_h))))
            except Exception:
                continue
            w = max(50, ax1 - ax0)
            h = max(14, ay1 - ay0)
            if w > int(image_w * 0.8) or h > int(image_h * 0.2):
                continue
            num = int(p.number)
            prev = out.get(num)
            if prev is None or len(text) >= len(prev[0]):
                out[num] = (text, (ax0, ay0, w, h))
        return out

    def _build_answer_map(self, parsed: HomeworkParseResponse) -> dict[int, str]:
        by_text = self._parse_answer_map(parsed.reference_answer)
        by_placements: dict[int, str] = {}
        for p in parsed.answer_placements:
            num = int(p.number)
            text = (p.text or "").strip()
            if 1 <= num <= 99 and text:
                # 同编号优先留更长文本，避免 "bus" 覆盖 "a bus"
                prev = by_placements.get(num, "")
                if len(text) >= len(prev):
                    by_placements[num] = text
        if not by_text:
            return by_placements
        if not by_placements:
            return by_text
        merged = dict(by_text)
        for num, text in by_placements.items():
            prev = merged.get(num, "")
            if not prev or len(text) >= len(prev):
                merged[num] = text
        return merged

    def _parse_answer_map(self, reference_answer: str) -> dict[int, str]:
        answer_map: dict[int, str] = {}
        sequential_chunks: list[str] = []
        raw_text = (reference_answer or "").strip()
        if not raw_text:
            return answer_map

        # 全局编号提取：兼容单行紧凑格式（如 "1 a doll;2 a bus;3 a ball"）
        compact = " ".join(raw_text.splitlines())
        global_pattern = re.compile(
            r"(?:^|[\s,;，；、/])(\d{1,2})\s*[\.\)\-:：]?\s*(.+?)(?=(?:[\s,;，；、/]+(?:\d{1,2})\s*[\.\)\-:：]?\s*)|$)"
        )
        for m in global_pattern.finditer(compact):
            idx = int(m.group(1))
            ans = m.group(2).strip(" ;,，；、/").strip()
            if 1 <= idx <= 99 and ans:
                prev = answer_map.get(idx, "")
                if len(ans) >= len(prev):
                    answer_map[idx] = ans
        if answer_map:
            return answer_map

        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = re.match(r"^(\d+)[\.)]?\s+(.+)$", line)
            if match:
                idx = int(match.group(1))
                ans = match.group(2).strip()
                if 1 <= idx <= 99 and ans:
                    answer_map[idx] = ans
                continue

            sequential_chunks.append(line)
            for match in re.finditer(
                r"(\d+)[\.)]?\s+([^\d]+?)(?=\s+\d+[\.)]?\s+|$)", line
            ):
                idx = int(match.group(1))
                ans = match.group(2).strip()
                if 1 <= idx <= 99 and ans:
                    answer_map[idx] = ans
        if answer_map:
            return answer_map

        slot = 1
        for line in sequential_chunks:
            pieces = [
                p.strip()
                for p in re.split(r"[;\n,，、/]+", line)
                if p.strip()
            ]
            for piece in pieces:
                answer_map[slot] = piece
                slot += 1
        return answer_map

    def _build_line_map_fused(
        self,
        parsed: HomeworkParseResponse,
        answers: dict[int, str],
        image_w: int,
        image_h: int,
    ) -> tuple[
        dict[int, tuple[int, int, int, int]],
        dict[int, tuple[int, int, int, int]],
        dict[int, tuple[int, int, int, int]],
    ]:
        ocr_map = self._build_line_map_from_ocr(parsed.ocr_result, answers, image_w, image_h)
        ocr_candidates = self._collect_ocr_candidate_rows(parsed.ocr_result, image_w)
        model_map = self._build_line_map_from_model_placements(parsed, answers, image_w, image_h)
        model_map = self._filter_model_map_by_ocr_region(model_map, ocr_map)
        model_map = self._filter_model_map_by_ocr_candidates(model_map, ocr_candidates)
        if not ocr_map:
            return model_map, ocr_map, model_map
        if not model_map:
            return ocr_map, ocr_map, model_map

        fused: dict[int, tuple[int, int, int, int]] = {}
        for num in sorted(answers.keys()):
            o = ocr_map.get(num)
            m = model_map.get(num)
            if o and m:
                fused[num] = self._fuse_single_box(o, m)
            elif o:
                fused[num] = o
            elif m:
                fused[num] = m
        fused = self._post_normalize_line_map(
            fused,
            answers,
            ocr_map,
            model_map,
            ocr_candidates,
            image_w,
            image_h,
        )
        return fused, ocr_map, model_map

    def _build_line_map_from_model_placements(
        self,
        parsed: HomeworkParseResponse,
        answers: dict[int, str],
        image_w: int,
        image_h: int,
    ) -> dict[int, tuple[int, int, int, int]]:
        mapping: dict[int, tuple[int, int, int, int]] = {}
        for placement in parsed.answer_placements:
            num = int(placement.number)
            if num not in answers:
                continue
            if not placement.bbox_norm or len(placement.bbox_norm) != 4:
                continue
            x0, y0, x1, y1 = placement.bbox_norm
            try:
                ax0 = int(max(0, min(image_w - 2, round(x0 * image_w))))
                ay0 = int(max(0, min(image_h - 2, round(y0 * image_h))))
                ax1 = int(max(ax0 + 1, min(image_w - 1, round(x1 * image_w))))
                ay1 = int(max(ay0 + 1, min(image_h - 1, round(y1 * image_h))))
            except Exception:
                continue
            w = max(50, ax1 - ax0)
            h = max(14, ay1 - ay0)
            if w > int(image_w * 0.8) or h > int(image_h * 0.15):
                continue
            mapping[num] = (ax0, ay0, w, h)
        return mapping

    def _filter_model_map_by_ocr_region(
        self,
        model_map: dict[int, tuple[int, int, int, int]],
        ocr_map: dict[int, tuple[int, int, int, int]],
    ) -> dict[int, tuple[int, int, int, int]]:
        if not model_map or not ocr_map:
            return model_map
        xs = [x for x, _, _, _ in ocr_map.values()]
        ys = [y for _, y, _, _ in ocr_map.values()]
        x2s = [x + w for x, _, w, _ in ocr_map.values()]
        y2s = [y + h for _, y, _, h in ocr_map.values()]
        if not xs or not ys:
            return model_map
        min_x = min(xs)
        min_y = min(ys)
        max_x = max(x2s)
        max_y = max(y2s)
        pad_x = max(40, int((max_x - min_x) * 0.35))
        pad_y = max(24, int((max_y - min_y) * 0.35))
        out: dict[int, tuple[int, int, int, int]] = {}
        for num, box in model_map.items():
            x, y, w, h = box
            cx = x + w / 2
            cy = y + h / 2
            if (
                min_x - pad_x <= cx <= max_x + pad_x
                and min_y - pad_y <= cy <= max_y + pad_y
            ):
                out[num] = box
        return out if out else {}

    def _fuse_single_box(
        self,
        ocr_box: tuple[int, int, int, int],
        model_box: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        ox, oy, ow, oh = ocr_box
        mx, my, mw, mh = model_box
        ocx = ox + ow / 2
        ocy = oy + oh / 2
        mcx = mx + mw / 2
        mcy = my + mh / 2

        # 近场融合：OCR 定宽，模型定高/中心；远场冲突：优先 OCR
        if abs(ocy - mcy) <= max(18, int(min(oh, mh) * 2.0)):
            cx = int(round(ocx * 0.7 + mcx * 0.3))
            cy = int(round(ocy * 0.6 + mcy * 0.4))
            w = int(round(ow * 0.75 + mw * 0.25))
            h = int(round(oh * 0.5 + mh * 0.5))
            x = max(0, cx - w // 2)
            y = max(0, cy - h // 2)
            return (x, y, max(50, w), max(14, h))
        return ocr_box

    def _filter_model_map_by_ocr_candidates(
        self,
        model_map: dict[int, tuple[int, int, int, int]],
        ocr_candidates: list[tuple[int, int, int, int]],
    ) -> dict[int, tuple[int, int, int, int]]:
        if not model_map:
            return model_map
        # OCR 候选过少时不做强过滤，避免“只识别出一条线”把模型框几乎全抹掉
        if len(ocr_candidates) < 3:
            return model_map

        out: dict[int, tuple[int, int, int, int]] = {}
        for num, box in model_map.items():
            if self._min_center_distance(box, ocr_candidates) <= 180:
                out[num] = box
        return out

    def _min_center_distance(
        self,
        box: tuple[int, int, int, int],
        candidates: list[tuple[int, int, int, int]],
    ) -> float:
        bx, by, bw, bh = box
        cx = bx + bw / 2
        cy = by + bh / 2
        best = float("inf")
        for x, y, w, h in candidates:
            ox = x + w / 2
            oy = y + h / 2
            d = ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5
            if d < best:
                best = d
        return best

    def _build_line_map_from_ocr(
        self,
        ocr_result,
        answers: dict[int, str],
        image_w: int,
        image_h: int,
    ) -> dict[int, tuple[int, int, int, int]]:
        numbered_candidates, row_candidates = self._collect_ocr_candidates(
            ocr_result=ocr_result,
            answers=answers,
            image_w=image_w,
        )
        mapped: dict[int, tuple[int, int, int, int]] = dict(numbered_candidates)
        if len(mapped) >= len(answers):
            return mapped

        # 编号不足：用 OCR 下划线行按阅读顺序补齐
        for row in self._dedupe_rows_by_y(row_candidates):
            # 若和已映射题目几乎同一行同列，跳过
            if any(abs(row[1] - ex[1]) <= 12 and abs(row[0] - ex[0]) <= 40 for ex in mapped.values()):
                continue
            for num in sorted(answers.keys()):
                if num not in mapped:
                    mapped[num] = row
                    break
            if len(mapped) >= len(answers):
                break
        return mapped

    def _collect_ocr_candidates(
        self,
        ocr_result,
        answers: dict[int, str],
        image_w: int,
    ) -> tuple[
        dict[int, tuple[int, int, int, int]],
        list[tuple[int, int, int, int]],
    ]:
        if not ocr_result or not getattr(ocr_result, "blocks", None):
            return {}, []

        row_candidates: list[tuple[int, int, int, int]] = []
        numbered_candidates: dict[int, tuple[int, int, int, int, int, int]] = {}

        for line_text, bbox, order_score in self._iter_ocr_rows(ocr_result):
            line_box = self._estimate_write_box_from_line(line_text, bbox, image_w)
            if line_box is None:
                continue
            if not self._is_probably_answer_row(line_text):
                continue
            row_candidates.append(line_box)
            num_match = re.match(r"^\s*(\d{1,2})[\.\)\-:]?\s+.+$", line_text)
            if not num_match:
                continue
            num = int(num_match.group(1))
            if num not in answers:
                continue
            candidate = (
                order_score,
                -line_box[2],
                line_box[0],
                line_box[1],
                line_box[2],
                line_box[3],
            )
            prev = numbered_candidates.get(num)
            if prev is None or candidate < prev:
                numbered_candidates[num] = candidate

        mapped = {k: (v[2], v[3], v[4], v[5]) for k, v in numbered_candidates.items()}
        return mapped, self._dedupe_rows_by_y(row_candidates)

    def _collect_ocr_candidate_rows(
        self,
        ocr_result,
        image_w: int,
    ) -> list[tuple[int, int, int, int]]:
        if not ocr_result or not getattr(ocr_result, "blocks", None):
            return []
        rows: list[tuple[int, int, int, int]] = []
        for line_text, bbox, _ in self._iter_ocr_rows(ocr_result):
            line_box = self._estimate_write_box_from_line(line_text, bbox, image_w)
            if line_box is None:
                continue
            if self._is_probably_answer_row(line_text):
                rows.append(line_box)
        return self._dedupe_rows_by_y(rows)

    def _is_probably_answer_row(self, line_text: str) -> bool:
        text = (line_text or "").strip().lower()
        if not text:
            return False
        if any(
            bad in text
            for bad in (
                "colourful toys",
                "what are they",
                "write",
                "date",
            )
        ):
            return False
        if "_" in text:
            return True
        # 无下划线题型：保留以编号开头的短行，过滤标题/说明/日期等
        if re.match(r"^\d{1,2}[\.\)\-:]?\s+", text):
            return True
        return False

    def _post_normalize_line_map(
        self,
        mapping: dict[int, tuple[int, int, int, int]],
        answers: dict[int, str],
        ocr_map: dict[int, tuple[int, int, int, int]],
        model_map: dict[int, tuple[int, int, int, int]],
        ocr_candidates: list[tuple[int, int, int, int]],
        image_w: int,
        image_h: int,
    ) -> dict[int, tuple[int, int, int, int]]:
        if not mapping:
            return mapping
        dense_ocr_candidates = (
            ocr_candidates
            if len(ocr_candidates) >= max(3, min(6, len(answers)))
            else []
        )
        candidate_source = dense_ocr_candidates or list((ocr_map or model_map or mapping).values())
        sequence_fallback = self._build_sequence_fallback_map(
            answers=answers,
            base_candidates=list(candidate_source),
            image_w=image_w,
            image_h=image_h,
        )
        sample_boxes = list(candidate_source)
        widths = sorted([w for _, _, w, _ in sample_boxes]) if sample_boxes else []
        heights = sorted([h for _, _, _, h in sample_boxes]) if sample_boxes else []
        median_w = widths[len(widths) // 2] if widths else int(image_w * 0.25)
        median_h = heights[len(heights) // 2] if heights else max(16, int(image_h * 0.03))

        out: dict[int, tuple[int, int, int, int]] = {}
        y_range = self._robust_y_range(list(mapping.values()))
        for num, box in mapping.items():
            x, y, w, h = box
            cy = y + h / 2
            if y_range is not None:
                lo, hi = y_range
                if cy < lo or cy > hi:
                    if num in sequence_fallback:
                        out[num] = sequence_fallback[num]
                    continue
            if (
                w > max(int(median_w * 2.5), int(image_w * 0.7))
                or h > max(int(median_h * 2.5), int(image_h * 0.15))
                or x < 0
                or y < 0
                or x + w > image_w
                or y + h > image_h
            ):
                if num in sequence_fallback:
                    out[num] = sequence_fallback[num]
                continue
            # 异常长条回收：限制到中位宽度附近，避免整块 OCR 被当作答案区
            if len(sample_boxes) >= 3 and w > int(median_w * 1.8):
                cx = x + w // 2
                w2 = max(60, int(median_w * 1.2))
                x2 = max(0, min(image_w - w2 - 1, cx - w2 // 2))
                out[num] = (x2, y, w2, h)
                continue
            out[num] = box

        for num in sorted(answers.keys()):
            if num not in out and num in sequence_fallback:
                out[num] = sequence_fallback[num]
        return out

    def _robust_y_range(
        self, boxes: list[tuple[int, int, int, int]]
    ) -> tuple[float, float] | None:
        if len(boxes) < 4:
            return None
        ys = sorted([y + h / 2 for _, y, _, h in boxes])
        q1 = ys[len(ys) // 4]
        q3 = ys[(len(ys) * 3) // 4]
        iqr = max(12.0, q3 - q1)
        pad = max(20.0, iqr * 1.5)
        return q1 - pad, q3 + pad

    def _build_ratio_line_map(
        self, answers: dict[int, str], image_w: int, image_h: int
    ) -> dict[int, tuple[int, int, int, int]]:
        return self._build_sequence_fallback_map(
            answers=answers,
            base_candidates=[],
            image_w=image_w,
            image_h=image_h,
        )

    def _build_sequence_fallback_map(
        self,
        answers: dict[int, str],
        base_candidates: list[tuple[int, int, int, int]],
        image_w: int,
        image_h: int,
    ) -> dict[int, tuple[int, int, int, int]]:
        nums = sorted(answers.keys())
        if not nums:
            return {}

        candidates = self._dedupe_rows_by_y(base_candidates)
        if candidates:
            ordered = sorted(candidates, key=lambda b: (b[1], b[0]))
            mapping: dict[int, tuple[int, int, int, int]] = {}
            for i, num in enumerate(nums):
                if i < len(ordered):
                    mapping[num] = ordered[i]
            if len(mapping) == len(nums):
                return mapping

            gap = self._median_gap([y for _, y, _, _ in ordered]) if len(ordered) >= 2 else max(24, int(image_h * 0.05))
            widths = [w for _, _, w, _ in ordered]
            heights = [h for _, _, _, h in ordered]
            base_x, base_y, base_w, base_h = ordered[-1]
            avg_w = int(sum(widths) / len(widths)) if widths else base_w
            avg_h = int(sum(heights) / len(heights)) if heights else base_h
            for num in nums:
                if num in mapping:
                    continue
                base_y += gap
                mapping[num] = (base_x, base_y, avg_w, avg_h)
            return mapping

        x = int(image_w * 0.2)
        w = int(image_w * 0.6)
        h = max(16, int(image_h * 0.03))
        start_y = int(image_h * 0.35)
        gap = max(24, int(image_h * 0.07))
        return {n: (x, start_y + i * gap, w, h) for i, n in enumerate(nums)}

    def _median_gap(self, ys: list[int]) -> int:
        if len(ys) < 2:
            return 40
        ys = sorted(ys)
        gaps = [max(8, ys[i + 1] - ys[i]) for i in range(len(ys) - 1)]
        gaps = sorted(gaps)
        return gaps[len(gaps) // 2]

    def _dedupe_rows_by_y(
        self, rows: list[tuple[int, int, int, int]]
    ) -> list[tuple[int, int, int, int]]:
        if not rows:
            return []
        rows = sorted(rows, key=lambda r: (r[1], r[0]))
        out: list[tuple[int, int, int, int]] = []
        for row in rows:
            if not out:
                out.append(row)
                continue
            px, py, pw, ph = out[-1]
            x, y, w, h = row
            # 仅在同列且同一行附近才合并，避免左右列同 y 被误合并
            if abs(y - py) <= 14 and abs(x - px) <= 120:
                if w > pw:
                    out[-1] = row
            else:
                out.append(row)
        return out

    def _iter_ocr_rows(self, ocr_result):
        for block in ocr_result.blocks or []:
            label = (getattr(block, "label", "") or "").lower()
            if label in {"image", "figure", "table", "chart", "formula"}:
                continue
            bbox = self._block_bbox(block)
            if bbox is None:
                continue
            text = (getattr(block, "text", "") or "").strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if not lines:
                continue
            bx, by, bw, bh = bbox
            per_h = max(12.0, bh / max(1, len(lines)))
            order_score = (
                int(getattr(block, "order", 10**6))
                if getattr(block, "order", None) is not None
                else 10**6
            )
            for i, line_text in enumerate(lines):
                row_y = int(by + i * per_h + per_h * 0.35)
                row_bbox = (int(bx), row_y, int(max(40, bw)), int(max(12, per_h * 0.75)))
                # 同行多题（如“5 ___ ___ 2 ___ ___”）拆成多个虚拟行
                segments = self._split_numbered_segments(line_text)
                if not segments:
                    yield line_text, row_bbox, order_score * 100 + i
                    continue
                for seg_idx, (seg_text, start_ratio, end_ratio) in enumerate(segments):
                    sx = int(row_bbox[0] + row_bbox[2] * start_ratio)
                    sw = int(max(40, row_bbox[2] * (end_ratio - start_ratio)))
                    seg_bbox = (sx, row_bbox[1], sw, row_bbox[3])
                    yield seg_text, seg_bbox, order_score * 100 + i * 10 + seg_idx

    def _split_numbered_segments(self, line_text: str) -> list[tuple[str, float, float]]:
        matches = list(re.finditer(r"(\d{1,2})[\.\)\-:]?\s+", line_text))
        if len(matches) <= 1:
            return []
        spans: list[tuple[str, float, float]] = []
        n = len(line_text)
        for i, m in enumerate(matches):
            s = m.start()
            e = matches[i + 1].start() if i + 1 < len(matches) else n
            seg = line_text[s:e].strip()
            if not seg:
                continue
            start_ratio = max(0.0, min(1.0, s / max(1, n)))
            end_ratio = max(start_ratio + 0.08, min(1.0, e / max(1, n)))
            spans.append((seg, start_ratio, end_ratio))
        return spans

    def _estimate_write_box_from_line(
        self,
        line_text: str,
        row_bbox: tuple[int, int, int, int],
        image_w: int,
    ) -> tuple[int, int, int, int] | None:
        x, y, w, h = row_bbox
        if w <= 20:
            return None

        # 优先按下划线位置估计答案起点；没有下划线则按“编号后”估计
        idx_blank = line_text.find("_")
        if idx_blank >= 0:
            ratio = idx_blank / max(1, len(line_text))
            start_x = int(x + w * max(0.18, min(0.85, ratio - 0.02)))
        else:
            m = re.match(r"^\s*\d{1,2}[\.\)\-:]?\s*", line_text)
            if m:
                ratio = len(m.group(0)) / max(1, len(line_text))
                start_x = int(x + w * max(0.2, min(0.7, ratio + 0.05)))
            else:
                start_x = int(x + w * 0.25)

        line_w = int(max(70, w - (start_x - x) - 8))
        start_x = max(0, min(start_x, image_w - 10))
        line_w = max(50, min(line_w, image_w - start_x - 4))
        line_h = max(14, h)
        return (start_x, y, line_w, line_h)

    def _write_output_file(self, image_bytes: bytes) -> Path:
        output_dir = self._get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = (output_dir / f"filled-{ts}.jpg").resolve()
        path.write_bytes(image_bytes)
        logger.info("answer_fill_saved path=%s", path)
        return path

    def _get_output_dir(self) -> Path:
        # 优先支持显式配置，默认固定到 backend/output，避免受启动 cwd 影响。
        configured = os.getenv("HOMEWORK_OUTPUT_DIR", "").strip()
        if configured:
            p = Path(configured).expanduser()
            return p if p.is_absolute() else (Path.cwd() / p)
        return (Path(__file__).resolve().parents[2] / "output").resolve()

    def _write_debug_overlay(
        self,
        image,
        final_points: list[tuple[int, int, int, int, str]],
        ocr_points: list[tuple[int, int, int, int, str]],
        model_points: list[tuple[int, int, int, int, str]],
    ) -> None:
        try:
            from PIL import ImageDraw
        except Exception:
            return
        overlay = image.copy()
        draw = ImageDraw.Draw(overlay)
        # OCR candidate boxes: blue
        for x, y, w, h, label in ocr_points:
            draw.rectangle(
                [(x, y - 2), (x + w, y + max(2, h))], outline=(60, 120, 255), width=2
            )
            draw.text((x, max(0, y - 16)), label, fill=(40, 90, 220))
        # Model candidate boxes: orange
        for x, y, w, h, label in model_points:
            draw.rectangle(
                [(x, y - 2), (x + w, y + max(2, h))], outline=(255, 140, 0), width=2
            )
            draw.text((x, max(0, y - 30)), label, fill=(220, 110, 0))
        # Final write boxes: green
        for x, y, w, h, label in final_points:
            draw.rectangle(
                [(x, y - 2), (x + w, y + max(2, h))], outline=(0, 180, 0), width=2
            )
            draw.text((x, max(0, y - 18)), label, fill=(0, 120, 0))
        draw.text((12, 12), "BLUE=OCR  ORANGE=MODEL  GREEN=FINAL", fill=(20, 20, 20))
        output_dir = self._get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        debug_path = (output_dir / f"filled-debug-{ts}.jpg").resolve()
        overlay.save(debug_path, format="JPEG", quality=90)
        logger.info("answer_fill_debug_saved path=%s", debug_path)

    def _build_layout_calibration(
        self,
        boxes: list[tuple[int, int, int, int]],
        image_w: int,
        image_h: int,
    ) -> dict[str, Any]:
        default = {
            "left_ratio": self.TEXT_LEFT_RATIO,
            "top_ratio": self.TEXT_TOP_RATIO,
            "baseline_pull": self.TEXT_BASELINE_PULL,
            "effective_h_cap": int(max(24, image_h * 0.03)),
        }
        rows = self._dedupe_rows_by_y([b for b in boxes if b[2] >= 40 and b[3] >= 12])
        if len(rows) < 3:
            return {"default": default, "columns": []}

        centers = sorted([x + w / 2 for x, _, w, _ in rows])
        split_threshold = max(140.0, image_w * 0.22)
        split_idx = -1
        best_gap = 0.0
        for i in range(len(centers) - 1):
            gap = centers[i + 1] - centers[i]
            if gap > split_threshold and gap > best_gap:
                best_gap = gap
                split_idx = i

        if split_idx >= 0:
            pivot = (centers[split_idx] + centers[split_idx + 1]) / 2
            left_rows = [r for r in rows if r[0] + r[2] / 2 <= pivot]
            right_rows = [r for r in rows if r[0] + r[2] / 2 > pivot]
            groups = [left_rows, right_rows]
        else:
            groups = [rows]

        columns: list[dict[str, Any]] = []
        for grp in groups:
            if len(grp) < 2:
                continue
            ys = sorted([y for _, y, _, _ in grp])
            hs = sorted([h for _, _, _, h in grp])
            gaps = [max(8, ys[i + 1] - ys[i]) for i in range(len(ys) - 1)]
            med_h = hs[len(hs) // 2] if hs else 24
            med_gap = sorted(gaps)[len(gaps) // 2] if gaps else max(24, med_h + 8)
            density = max(0.4, min(1.8, med_h / max(1, med_gap)))

            top_ratio = max(0.10, min(0.22, 0.18 - (density - 0.9) * 0.06))
            baseline_pull = max(0.22, min(0.48, 0.34 + (density - 0.9) * 0.10))
            left_ratio = max(0.06, min(0.15, 0.09 + (1.0 - min(1.0, density)) * 0.03))
            effective_h_cap = int(max(20, min(image_h * 0.045, med_h * 1.05, med_gap * 0.92)))

            x0 = min(x for x, _, _, _ in grp)
            x1 = max(x + w for x, _, w, _ in grp)
            columns.append(
                {
                    "x0": int(x0),
                    "x1": int(x1),
                    "left_ratio": left_ratio,
                    "top_ratio": top_ratio,
                    "baseline_pull": baseline_pull,
                    "effective_h_cap": effective_h_cap,
                }
            )
        return {"default": default, "columns": columns}

    def _resolve_text_style(
        self,
        line: tuple[int, int, int, int],
        layout_calib: dict[str, Any] | None,
    ) -> dict[str, float]:
        fallback: dict[str, float] = {
            "left_ratio": self.TEXT_LEFT_RATIO,
            "top_ratio": self.TEXT_TOP_RATIO,
            "baseline_pull": self.TEXT_BASELINE_PULL,
            "effective_h_cap": 28.0,
        }
        if not layout_calib:
            return fallback
        default = dict(fallback)
        default.update(layout_calib.get("default") or {})
        cols = layout_calib.get("columns") or []
        x, _, w, _ = line
        cx = x + w / 2
        for col in cols:
            if col.get("x0", -1) - 20 <= cx <= col.get("x1", -1) + 20:
                merged = dict(default)
                merged.update(col)
                return merged
        return default


    def _draw_text_fit_line(
        self,
        draw,
        text: str,
        line: tuple[int, int, int, int],
        image_w: int,
        image_h: int,
        base_font_size: int,
        layout_calib: dict[str, Any] | None = None,
    ) -> None:
        x, y, w, h = line
        style = self._resolve_text_style(line, layout_calib)
        target_w = max(40, w - 8)
        # 模型框有时偏高，直接按整框排版会让文本视觉下沉；
        # 这里使用“有效行高”来贴近横线区域。
        effective_h = max(
            16,
            min(
                h,
                int(style.get("effective_h_cap", max(26, image_h * 0.03))),
                int(max(22, image_h * 0.04)),
            ),
        )
        target_h = max(14, int(effective_h * 1.2))
        font_size = max(13, min(base_font_size, int(target_h * 1.45)))

        font = self._load_font(font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # 宽高双约束自适应
        while font_size > 10 and (tw > target_w or th > target_h):
            font_size -= 1
            font = self._load_font(font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

        # 回写更接近真实填写：左对齐到空线起点附近，而不是水平居中。
        x_text = x + max(4, int(w * float(style.get("left_ratio", self.TEXT_LEFT_RATIO))))
        x_text = min(x_text, max(0, image_w - tw - 1))
        # 写在目标框内部，优先落在线区中部，避免整体漂到框上方
        # 以有效行高为锚点上移，并扣除一部分字高，贴近横线
        y_text = (
            y
            + max(1, int(effective_h * float(style.get("top_ratio", self.TEXT_TOP_RATIO))))
            - int(th * float(style.get("baseline_pull", self.TEXT_BASELINE_PULL)))
        )
        y_text = max(0, min(y_text, image_h - th - 1))
        draw.text((x_text, y_text), text, fill=self.FILL_TEXT_COLOR, font=font)

    def _load_font(self, size: int):
        from PIL import ImageFont

        for name in ("Arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _block_bbox(self, block) -> tuple[float, float, float, float] | None:
        bbox = getattr(block, "bbox", None)
        if isinstance(bbox, list) and len(bbox) == 4:
            x0, y0, x1, y1 = bbox
            try:
                return float(x0), float(y0), float(x1 - x0), float(y1 - y0)
            except Exception:
                return None
        polygon = getattr(block, "polygon", None)
        if isinstance(polygon, list) and polygon:
            xs = []
            ys = []
            for point in polygon:
                if isinstance(point, list) and len(point) >= 2:
                    xs.append(point[0])
                    ys.append(point[1])
            if xs and ys:
                try:
                    x0 = float(min(xs))
                    y0 = float(min(ys))
                    x1 = float(max(xs))
                    y1 = float(max(ys))
                    return x0, y0, x1 - x0, y1 - y0
                except Exception:
                    return None
        return None
