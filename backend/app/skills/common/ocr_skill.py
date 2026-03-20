from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.errors import AppError
from app.core.models import OCRResult

logger = logging.getLogger(__name__)


class OCRProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        ...

    def extract(self, image_bytes: bytes | None, image_url: str | None) -> OCRResult | None:
        ...


@dataclass
class MockOCRProvider:
    name: str = "mock"

    def is_available(self) -> bool:
        return True

    def extract(self, image_bytes: bytes | None, image_url: str | None) -> OCRResult | None:
        if image_url:
            return OCRResult(text=f"[image_url_input] {image_url}", confidence=0.4)
        if image_bytes:
            return OCRResult(text="[image_binary_input]", confidence=0.5)
        return None


@dataclass
class TesseractOCRProvider:
    lang: str = "eng"
    name: str = "tesseract"

    def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401

            return True
        except Exception:
            return False

    def extract(self, image_bytes: bytes | None, image_url: str | None) -> OCRResult | None:
        if not image_bytes:
            return None
        import io

        import pytesseract
        from PIL import Image

        text = pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)), lang=self.lang).strip()
        if not text:
            return None
        return OCRResult(text=text, confidence=0.55)


@dataclass
class PaddleOCROCRProvider:
    lang: str = "en"
    use_angle_cls: bool = True
    name: str = "paddleocr"

    def is_available(self) -> bool:
        try:
            from paddleocr import PaddleOCR  # noqa: F401

            return True
        except Exception:
            return False

    def extract(self, image_bytes: bytes | None, image_url: str | None) -> OCRResult | None:
        if not image_bytes:
            return None
        from paddleocr import PaddleOCR

        engine = PaddleOCR(use_angle_cls=self.use_angle_cls, lang=self.lang, show_log=False)
        image_path = self._write_temp_image(image_bytes)
        try:
            result = engine.ocr(str(image_path), cls=self.use_angle_cls)
        finally:
            image_path.unlink(missing_ok=True)

        segments: list[str] = []
        scores: list[float] = []
        if isinstance(result, list):
            for block in result:
                if not isinstance(block, list):
                    continue
                for item in block:
                    if (
                        isinstance(item, list)
                        and len(item) >= 2
                        and isinstance(item[1], (list, tuple))
                        and len(item[1]) >= 2
                    ):
                        text = str(item[1][0]).strip()
                        if text:
                            segments.append(text)
                            try:
                                scores.append(float(item[1][1]))
                            except Exception:
                                pass
        if not segments:
            return None
        conf = sum(scores) / len(scores) if scores else 0.65
        return OCRResult(text="\n".join(segments), confidence=min(max(conf, 0.0), 1.0))

    def _write_temp_image(self, image_bytes: bytes) -> Path:
        with tempfile.NamedTemporaryFile(prefix="hw_ocr_", suffix=".jpg", delete=False) as fp:
            fp.write(image_bytes)
            return Path(fp.name)


@dataclass
class PaddleCloudOCRProvider:
    api_url: str
    token: str
    timeout_sec: int = 120
    name: str = "paddle_cloud"

    def is_available(self) -> bool:
        return bool(self.api_url and self.token)

    def extract(self, image_bytes: bytes | None, image_url: str | None) -> OCRResult | None:
        if not image_bytes and not image_url:
            return None

        params: dict[str, object] = {"visualize": False}
        if image_url:
            params["file_url"] = image_url
        else:
            params["file"] = base64.b64encode(image_bytes or b"").decode("utf-8")
            params["fileType"] = 1

        headers = {"Authorization": f"token {self.token}", "Content-Type": "application/json"}
        with httpx.Client(timeout=float(self.timeout_sec)) as client:
            resp = client.post(self.api_url, json=params, headers=headers)

        if resp.status_code >= 400:
            raise RuntimeError(f"paddle_cloud http={resp.status_code} body={resp.text[:200]}")

        data = resp.json()
        if data.get("errorCode", 0) != 0:
            raise RuntimeError(f"paddle_cloud api_error={data.get('errorMsg', 'unknown')}")

        text = self._extract_text(data).strip()
        if not text:
            return None
        return OCRResult(text=text, confidence=0.85)

    def _extract_text(self, data: dict) -> str:
        raw = data.get("result", data)
        pages = raw.get("layoutParsingResults", []) if isinstance(raw, dict) else raw
        if not isinstance(pages, list):
            return ""
        segments: list[str] = []
        for page in pages:
            if not isinstance(page, dict):
                continue
            md = page.get("markdown", {})
            if isinstance(md, dict) and isinstance(md.get("text"), str) and md["text"].strip():
                segments.append(md["text"].strip())
                continue
            pruned = page.get("prunedResult", {})
            blocks = pruned.get("parsing_res_list", []) if isinstance(pruned, dict) else []
            if isinstance(blocks, list):
                for block in blocks:
                    if isinstance(block, dict):
                        c = block.get("block_content")
                        if isinstance(c, str) and c.strip():
                            segments.append(c.strip())
        return "\n\n".join(segments)


@dataclass
class RapidOCROCRProvider:
    name: str = "rapidocr"

    def is_available(self) -> bool:
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401

            return True
        except Exception:
            return False

    def extract(self, image_bytes: bytes | None, image_url: str | None) -> OCRResult | None:
        if not image_bytes:
            return None
        from rapidocr_onnxruntime import RapidOCR

        image_path = self._write_temp_image(image_bytes)
        try:
            engine = RapidOCR()
            result, _ = engine(str(image_path))
        finally:
            image_path.unlink(missing_ok=True)

        if not result:
            return None
        segments: list[str] = []
        scores: list[float] = []
        for row in result:
            if isinstance(row, (list, tuple)) and len(row) >= 3:
                text = str(row[1]).strip()
                if text:
                    segments.append(text)
                    try:
                        scores.append(float(row[2]))
                    except Exception:
                        pass
        if not segments:
            return None
        conf = sum(scores) / len(scores) if scores else 0.7
        return OCRResult(text="\n".join(segments), confidence=min(max(conf, 0.0), 1.0))

    def _write_temp_image(self, image_bytes: bytes) -> Path:
        with tempfile.NamedTemporaryFile(prefix="hw_ocr_", suffix=".jpg", delete=False) as fp:
            fp.write(image_bytes)
            return Path(fp.name)


class OCRSkill:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.providers = self._build_providers(settings)

    async def extract_text(self, image_bytes: bytes | None, image_url: str | None) -> OCRResult:
        if image_bytes is None and not image_url:
            raise AppError("INVALID_REQUEST", "Either image file or image_url is required.")

        resolved_image_bytes = image_bytes or self._download_image_if_needed(image_url)
        if resolved_image_bytes is None and not image_url:
            raise AppError("OCR_FAILED", "OCR input is empty.")

        last_error: Exception | None = None
        for provider in self.providers:
            if not provider.is_available():
                logger.info("ocr_provider_unavailable provider=%s", provider.name)
                continue
            try:
                logger.info("ocr_provider_attempt provider=%s", provider.name)
                result = await asyncio.to_thread(provider.extract, resolved_image_bytes, image_url)
                if result and result.text.strip():
                    logger.info("ocr_provider_success provider=%s confidence=%.3f", provider.name, result.confidence)
                    return result
            except Exception as exc:
                last_error = exc
                logger.warning("ocr_provider_failed provider=%s error=%s", provider.name, exc)

        if last_error:
            raise AppError("OCR_FAILED", f"OCR providers failed: {last_error}") from last_error
        raise AppError("OCR_FAILED", "No OCR provider produced text.")

    def _download_image_if_needed(self, image_url: str | None) -> bytes | None:
        if not image_url or not self.settings.ocr_fetch_url_enabled:
            return None
        try:
            with urllib.request.urlopen(image_url, timeout=10) as resp:
                return resp.read()
        except Exception as exc:
            logger.warning("ocr_fetch_image_url_failed url=%s error=%s", image_url, exc)
            return None

    def _build_providers(self, settings: Settings) -> list[OCRProvider]:
        order = [item.strip().lower() for item in settings.ocr_provider_order.split(",") if item.strip()]
        providers: list[OCRProvider] = []
        for name in order:
            if name == "paddle_cloud":
                providers.append(
                    PaddleCloudOCRProvider(
                        api_url=settings.paddleocr_doc_parsing_api_url,
                        token=settings.paddleocr_access_token,
                        timeout_sec=settings.paddleocr_timeout_sec,
                    )
                )
            elif name == "rapidocr":
                providers.append(RapidOCROCRProvider())
            elif name == "paddleocr":
                providers.append(PaddleOCROCRProvider(lang=settings.ocr_lang))
            elif name == "tesseract":
                t_lang = "eng" if settings.ocr_lang.lower().startswith("en") else settings.ocr_lang
                providers.append(TesseractOCRProvider(lang=t_lang))
            elif name == "mock":
                providers.append(MockOCRProvider())
        if not providers:
            providers.append(MockOCRProvider())
        return providers

    def list_providers(self) -> list[dict[str, object]]:
        return [{"name": provider.name, "available": bool(provider.is_available())} for provider in self.providers]
