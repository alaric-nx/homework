from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import logging

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
    FONT_RATIO = 0.019

    def fill_answers_to_image_base64_and_file(
        self, image_bytes: bytes, parsed: HomeworkParseResponse
    ) -> tuple[str, str]:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception as exc:
            raise AppError(
                "INTERNAL_ERROR", "Pillow is required for image answer filling."
            ) from exc

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise AppError("INVALID_REQUEST", "Invalid image bytes.") from exc

        answers = self._parse_answer_map(parsed.reference_answer)
        logger.info(
            "answer_fill_parsed_answers keys=%s preview=%s",
            sorted(answers.keys()),
            parsed.reference_answer[:200].replace("\n", " "),
        )
        draw = ImageDraw.Draw(image)
        w, h = image.size
        font_size = max(18, int(min(w, h) * self.FONT_RATIO))
        try:
            font = ImageFont.truetype("Arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        line_map = self._build_line_map_from_ocr(parsed.ocr_result, answers, w, h)
        if not line_map:
            line_map = self._build_ratio_line_map(answers, w, h)
        logger.info("answer_fill_lines line_map=%s", line_map)

        debug_points: list[tuple[int, int, int, int, str]] = []

        for num in sorted(answers.keys()):
            text = answers.get(num)
            if text:
                line = line_map.get(num)
                if line is not None:
                    self._draw_text_fit_line(draw, text, line, w, h, font_size)
                    debug_points.append((*line, f"{num}:{text}"))

        out = io.BytesIO()
        image.save(out, format="JPEG", quality=90)
        out_bytes = out.getvalue()
        file_path = self._write_output_file(out_bytes)
        self._write_debug_overlay(image, debug_points)
        return base64.b64encode(out_bytes).decode("utf-8"), str(file_path)

    def _parse_answer_map(self, reference_answer: str) -> dict[int, str]:
        answer_map: dict[int, str] = {}
        for raw_line in reference_answer.splitlines():
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

            for match in re.finditer(
                r"(\d+)[\.)]?\s+([^\d]+?)(?=\s+\d+[\.)]?\s+|$)", line
            ):
                idx = int(match.group(1))
                ans = match.group(2).strip()
                if 1 <= idx <= 99 and ans:
                    answer_map[idx] = ans
        return answer_map

    def _build_line_map_from_ocr(
        self,
        ocr_result,
        answers: dict[int, str],
        image_w: int,
        image_h: int,
    ) -> dict[int, tuple[int, int, int, int]]:
        if not ocr_result or not getattr(ocr_result, "blocks", None):
            return {}

        mapped: dict[int, tuple[int, int, int, int]] = {}
        row_candidates: list[tuple[int, int, int, int]] = []
        numbered_candidates: dict[int, tuple[int, int, int, int, int, int]] = {}
        # value: (order_score, -line_w, x, y, w, h)

        for line_text, bbox, order_score in self._iter_ocr_rows(ocr_result):
            x, y, w, h = bbox
            line_box = self._estimate_write_box_from_line(line_text, bbox, image_w)
            if line_box is None:
                continue

            if "_" in line_text:
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

        mapped.update({k: (v[2], v[3], v[4], v[5]) for k, v in numbered_candidates.items()})
        if len(mapped) >= len(answers):
            return mapped

        # 编号不足：用 OCR 行按阅读顺序补齐
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

    def _build_ratio_line_map(
        self, answers: dict[int, str], image_w: int, image_h: int
    ) -> dict[int, tuple[int, int, int, int]]:
        nums = sorted(answers.keys())
        if not nums:
            return {}

        if all(1 <= n <= 9 for n in nums):
            line_map: dict[int, tuple[int, int, int, int]] = {}
            left_nums = [n for n in nums if n % 2 == 1]
            right_nums = [n for n in nums if n % 2 == 0]
            gap = int(image_h * self.LINE_GAP_RATIO)
            base_y = int(image_h * self.START_Y_RATIO)
            left_x = int(image_w * self.LEFT_X_RATIO)
            right_x = int(image_w * self.RIGHT_X_RATIO)
            line_w = int(image_w * 0.26)
            line_h = max(16, int(image_h * 0.018))
            for i, n in enumerate(left_nums):
                line_map[n] = (left_x, base_y + i * gap, line_w, line_h)
            for i, n in enumerate(right_nums):
                line_map[n] = (right_x, base_y + i * gap, line_w, line_h)
            return line_map

        # 通用题型：单列等间距兜底
        x = int(image_w * 0.2)
        w = int(image_w * 0.6)
        h = max(16, int(image_h * 0.02))
        start_y = int(image_h * 0.74)
        gap = max(24, int(image_h * 0.055))
        return {n: (x, start_y + i * gap, w, h) for i, n in enumerate(nums)}

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
            bbox = self._block_bbox(block)
            if bbox is None:
                continue
            text = (getattr(block, "text", "") or "").strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            # 空文本块也保留一行，用于兜底定位
            if not lines:
                lines = ["___"]
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
                yield line_text, row_bbox, order_score * 10 + i

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
        output_dir = Path.cwd() / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = (output_dir / f"filled-{ts}.jpg").resolve()
        path.write_bytes(image_bytes)
        return path

    def _write_debug_overlay(
        self, image, debug_points: list[tuple[int, int, int, int, str]]
    ) -> None:
        try:
            from PIL import ImageDraw
        except Exception:
            return
        overlay = image.copy()
        draw = ImageDraw.Draw(overlay)
        for x, y, w, h, label in debug_points:
            draw.rectangle(
                [(x, y - 2), (x + w, y + max(2, h))], outline=(0, 180, 0), width=2
            )
            draw.text((x, max(0, y - 18)), label, fill=(0, 120, 0))
        output_dir = Path.cwd() / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        debug_path = (output_dir / f"filled-debug-{ts}.jpg").resolve()
        overlay.save(debug_path, format="JPEG", quality=90)


    def _draw_text_fit_line(
        self,
        draw,
        text: str,
        line: tuple[int, int, int, int],
        image_w: int,
        image_h: int,
        base_font_size: int,
    ) -> None:
        x, y, w, h = line
        target_w = max(40, w - 8)
        target_h = max(14, int(h * 1.2))
        font_size = max(12, min(base_font_size, int(target_h * 1.25)))

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

        x_text = x + max(2, (target_w - tw) // 2)
        # 文本落在下划线略上方，避免压线
        y_text = max(0, y - th - max(2, int(h * 0.25)))
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
