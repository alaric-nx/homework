from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.core.models import OCRResult
from app.services.opencode_client import OpencodeClient

logger = logging.getLogger(__name__)


class EnglishSolverSkill:
    def __init__(self, opencode_client: OpencodeClient) -> None:
        self.opencode_client = opencode_client

    async def solve(
        self,
        ocr: OCRResult,
        image_bytes: bytes | None = None,
        image_url: str | None = None,
        strict_mode: bool = False,
    ) -> dict[str, Any]:
        prompt = self._build_prompt(ocr, strict_mode=strict_mode)
        tmp_file: Path | None = None
        try:
            files: list[str] = []
            if image_bytes:
                tmp_file = self._write_temp_image(image_bytes)
                files.append(str(tmp_file))
            # image_url is not attached as file; keep for prompt hint only.
            if image_url:
                prompt = f"{prompt}\n补充信息：原图 URL 为 {image_url}\n"
            return await self.opencode_client.generate_json(prompt, file_paths=files)
        finally:
            if tmp_file is not None:
                tmp_file.unlink(missing_ok=True)

    def _build_prompt(self, ocr: OCRResult, strict_mode: bool) -> str:
        strict_flag = "严格JSON模式" if strict_mode else "正常模式"
        ocr_text = (ocr.text or "").strip()
        if not ocr_text:
            ocr_text = "[OCR为空]"

        ordered_number_hints = self._extract_number_hints(ocr)
        numbered_hint_text = (
            "\n".join(f"{k}: {v}" for k, v in ordered_number_hints.items())
            if ordered_number_hints
            else "[无可用编号提示]"
        )
        block_preview = self._build_block_preview(ocr, max_items=20)

        return (
            "你是小学英语作业解析助手。\n"
            f"当前模式：{strict_flag}\n"
            "必须严格遵守：\n"
            "1) 只输出一个 JSON 对象，不要 markdown，不要代码块，不要任何额外文字。\n"
            "2) 只允许以下字段：question_meaning_zh, reference_answer, explanation_zh, key_vocabulary, speak_units, uncertainty。\n"
            "3) key_vocabulary 是数组，元素字段：word, meaning_zh, ipa(可空)。\n"
            "4) speak_units 是数组，元素字段：unit_type(只能是word或sentence), text。\n"
            "5) uncertainty 字段：requires_review(boolean), confidence(0到1), reason(可空字符串)。\n"
            "6) 字段必须齐全，不能缺失，不能新增字段。\n"
            "7) question_meaning_zh 必须分两行：第一行是题目中文翻译，第二行说明题目要做什么。\n"
            "8) 你会收到题目图片附件，必须优先根据图片内容识别每个编号对应的玩具并填写答案（image-first）。\n"
            "9) OCR 只是辅助信息（OCR-assist）。如果 OCR 与图片冲突，以图片为准。\n"
            "10) 若题目含编号，请按检测到的编号顺序给答案；若无编号，按图片语义正常作答。\n"
            f"OCR全文如下：\n{ocr_text}\n\n"
            f"OCR按编号整理（辅助）如下：\n{numbered_hint_text}\n\n"
            f"OCR块预览（辅助）如下：\n{block_preview}\n"
        )

    def _extract_number_hints(self, ocr: OCRResult) -> dict[int, str]:
        hints: dict[int, str] = {}
        lines: list[str] = []

        for block in sorted(
            ocr.blocks, key=lambda b: (b.order is None, b.order if b.order is not None else 10**9)
        ):
            text = (block.text or "").strip()
            if text:
                lines.extend(text.splitlines())

        if ocr.text.strip():
            lines.extend(ocr.text.splitlines())

        # 支持 1 xx / 1. xx / 1) xx / 1- xx / 1: xx
        line_pattern = re.compile(r"^\s*(\d{1,2})[\.\)\-:]?\s+(.+?)\s*$")
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            m = line_pattern.match(line)
            if not m:
                continue
            num = int(m.group(1))
            if num <= 0 or num > 99:
                continue
            content = m.group(2).strip()
            if content and num not in hints:
                hints[num] = content

        return dict(sorted(hints.items(), key=lambda item: item[0]))

    def _build_block_preview(self, ocr: OCRResult, max_items: int) -> str:
        if not ocr.blocks:
            return "[]"
        preview = []
        for block in sorted(
            ocr.blocks, key=lambda b: (b.order is None, b.order if b.order is not None else 10**9)
        )[:max_items]:
            preview.append(
                {
                    "order": block.order,
                    "label": block.label,
                    "text": block.text,
                }
            )
        return json.dumps(preview, ensure_ascii=False)

    def fallback_output(
        self, ocr: OCRResult, reason: str | None = None
    ) -> dict[str, Any]:
        if reason:
            logger.warning("english_solver_fallback reason=%s", reason)
        base_text = ocr.text if ocr.text.strip() else "题目文本识别为空"
        return {
            "question_meaning_zh": f"请根据题目完成英语作业（OCR文本：{base_text}）。",
            "reference_answer": "请根据题干补全正确答案（当前为后端占位答案）。",
            "explanation_zh": "这是 MVP 阶段的兜底讲解，等待 opencode 接入后会输出更准确解析。",
            "key_vocabulary": [
                {"word": "answer", "meaning_zh": "答案", "ipa": "/ˈɑːnsər/"}
            ],
            "speak_units": [
                {"unit_type": "word", "text": "answer"},
                {"unit_type": "sentence", "text": "Please complete the exercise."},
            ],
            "uncertainty": {
                "requires_review": True,
                "confidence": min(ocr.confidence, 0.6),
                "reason": reason or "使用了兜底策略，请家长人工复核。",
            },
        }

    def _write_temp_image(self, image_bytes: bytes) -> Path:
        with tempfile.NamedTemporaryFile(
            prefix="hw_solver_", suffix=".jpg", delete=False
        ) as fp:
            fp.write(image_bytes)
            return Path(fp.name)
