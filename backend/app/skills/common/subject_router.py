from __future__ import annotations

from typing import Literal

Subject = Literal["english", "chinese", "math"]


def route_subject(hint: str | None, ocr_text: str | None = None) -> Subject:
    content = f"{hint or ''} {ocr_text or ''}".lower()
    if any(token in content for token in ("math", "数学", "算术", "计算")):
        return "math"
    if any(token in content for token in ("chinese", "语文", "中文")):
        return "chinese"
    return "english"

