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

    def fill_answers_to_image_base64_and_file(self, image_bytes: bytes, parsed: HomeworkParseResponse) -> tuple[str, str]:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception as exc:
            raise AppError("INTERNAL_ERROR", "Pillow is required for image answer filling.") from exc

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise AppError("INVALID_REQUEST", "Invalid image bytes.") from exc

        answers = self._parse_answer_map(parsed.reference_answer)
        draw = ImageDraw.Draw(image)

        w, h = image.size
        font_size = max(18, int(min(w, h) * self.FONT_RATIO))
        try:
            font = ImageFont.truetype("Arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        left_order = [1, 3, 5, 7, 9]
        right_order = [2, 4, 6, 8]
        detected = self._detect_answer_lines(image)

        for i, num in enumerate(left_order):
            text = answers.get(num)
            if text:
                if i < len(detected["left"]):
                    self._draw_text_fit_line(draw, text, detected["left"][i], w, h, font_size)
                else:
                    # fallback placement
                    left_x = int(w * self.LEFT_X_RATIO)
                    start_y = int(h * self.START_Y_RATIO)
                    line_gap = int(h * self.LINE_GAP_RATIO)
                    fallback_line = (left_x, start_y + i * line_gap, int(w * 0.26), 2)
                    self._draw_text_fit_line(draw, text, fallback_line, w, h, font_size)

        for i, num in enumerate(right_order):
            text = answers.get(num)
            if text:
                if i < len(detected["right"]):
                    self._draw_text_fit_line(draw, text, detected["right"][i], w, h, font_size)
                else:
                    # fallback placement
                    right_x = int(w * self.RIGHT_X_RATIO)
                    start_y = int(h * self.START_Y_RATIO)
                    line_gap = int(h * self.LINE_GAP_RATIO)
                    fallback_line = (right_x, start_y + i * line_gap, int(w * 0.26), 2)
                    self._draw_text_fit_line(draw, text, fallback_line, w, h, font_size)

        out = io.BytesIO()
        image.save(out, format="JPEG", quality=90)
        out_bytes = out.getvalue()
        file_path = self._write_output_file(out_bytes)
        return base64.b64encode(out_bytes).decode("utf-8"), str(file_path)

    def _parse_answer_map(self, reference_answer: str) -> dict[int, str]:
        answer_map: dict[int, str] = {}
        for raw_line in reference_answer.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = re.match(r"^(\d+)\s+(.+)$", line)
            if not match:
                continue
            idx = int(match.group(1))
            ans = match.group(2).strip()
            if 1 <= idx <= 9 and ans:
                answer_map[idx] = ans
        return answer_map

    def _write_output_file(self, image_bytes: bytes) -> Path:
        output_dir = Path.cwd() / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = (output_dir / f"filled-{ts}.jpg").resolve()
        path.write_bytes(image_bytes)
        return path

    def _detect_answer_lines(self, image) -> dict[str, list[tuple[int, int, int, int]]]:
        """
        Detect answer blank lines from the lower-half worksheet area.
        Returns {"left": [(x,y,w,h)...], "right": [...]}, both sorted by y.
        """
        try:
            import cv2
            import numpy as np
        except Exception:
            return {"left": [], "right": []}

        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        h, w = gray.shape[:2]
        roi_top = int(h * 0.66)
        roi = gray[roi_top:, :]

        # Highlight dark horizontal strokes.
        bw = cv2.threshold(roi, 180, 255, cv2.THRESH_BINARY_INV)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(24, w // 20), 1))
        horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(horiz, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        raw_lines: list[tuple[int, int, int, int]] = []
        for c in contours:
            x, y, ww, hh = cv2.boundingRect(c)
            # Keep likely answer lines; reject short fragments and thick blocks.
            if ww < int(w * 0.14) or ww > int(w * 0.38):
                continue
            if hh > max(9, int(h * 0.01)):
                continue
            abs_y = y + roi_top
            if abs_y < int(h * 0.68):
                continue
            raw_lines.append((x, abs_y, ww, hh))

        # Merge nearly duplicated detections by y/x proximity.
        raw_lines.sort(key=lambda t: (t[1], t[0]))
        merged: list[tuple[int, int, int, int]] = []
        for ln in raw_lines:
            if not merged:
                merged.append(ln)
                continue
            px, py, pw, ph = merged[-1]
            x, y, ww, hh = ln
            if abs(y - py) <= 6 and abs(x - px) <= 40:
                # keep longer one
                merged[-1] = (x, y, ww, hh) if ww > pw else merged[-1]
            else:
                merged.append(ln)

        # Split to left/right columns by center x with coarse x-range filtering.
        mid_x = w // 2
        left = [
            ln
            for ln in merged
            if ln[0] + ln[2] // 2 < mid_x and ln[0] > int(w * 0.06) and ln[0] < int(w * 0.45)
        ]
        right = [
            ln
            for ln in merged
            if ln[0] + ln[2] // 2 >= mid_x and ln[0] > int(w * 0.48) and ln[0] < int(w * 0.92)
        ]
        left = self._collapse_same_row_lines(left)
        right = self._collapse_same_row_lines(right)

        left = self._normalize_line_count(left, count=5)
        right = self._normalize_line_count(right, count=4)
        logger.debug("answer_line_detect left=%s right=%s", left, right)
        return {"left": left, "right": right}

    def _collapse_same_row_lines(self, lines: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        """
        In one answer row there can be multiple underline segments.
        Cluster by y and keep the longest segment (main writing line) in each row.
        """
        if not lines:
            return []
        lines = sorted(lines, key=lambda t: t[1])
        clusters: list[list[tuple[int, int, int, int]]] = []
        for ln in lines:
            if not clusters:
                clusters.append([ln])
                continue
            _, last_y, _, _ = clusters[-1][-1]
            if abs(ln[1] - last_y) <= 14:
                clusters[-1].append(ln)
            else:
                clusters.append([ln])

        collapsed: list[tuple[int, int, int, int]] = []
        for cluster in clusters:
            # choose longest line segment in this row as primary writing area
            best = max(cluster, key=lambda t: t[2])
            collapsed.append(best)
        collapsed.sort(key=lambda t: t[1])
        return collapsed

    def _normalize_line_count(self, lines: list[tuple[int, int, int, int]], count: int) -> list[tuple[int, int, int, int]]:
        if not lines:
            return []
        lines = sorted(lines, key=lambda t: t[1])[:count]
        if len(lines) >= count:
            return lines

        # Fill missing rows by interpolating vertical gaps from existing detections.
        ys = [y for _, y, _, _ in lines]
        if len(ys) >= 2:
            gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
            gap = int(sum(gaps) / len(gaps))
            if gap < 8:
                gap = 8
        else:
            gap = 52
        x, y, w, h = lines[-1]
        while len(lines) < count:
            y += gap
            lines.append((x, y, w, h))
        return lines

    def _draw_text_fit_line(
        self,
        draw,
        text: str,
        line: tuple[int, int, int, int],
        image_w: int,
        image_h: int,
        base_font_size: int,
    ) -> None:
        from PIL import ImageFont

        x, y, w, _ = line
        target_w = max(40, w - 10)
        font_size = base_font_size

        # Fit text width to line width.
        while font_size >= 12:
            font = self._load_font(font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            if tw <= target_w:
                break
            font_size -= 1
        else:
            font = self._load_font(12)
            bbox = draw.textbbox((0, 0), text, font=font)

        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x_text = x + max(4, (target_w - tw) // 2)
        try:
            ascent, _ = font.getmetrics()
            y_text = max(0, y - ascent + 2)
        except Exception:
            y_text = max(0, y - int(th * 0.85))
        draw.text((x_text, y_text), text, fill=self.FILL_TEXT_COLOR, font=font)

    def _load_font(self, size: int):
        from PIL import ImageFont

        for name in ("Arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()
