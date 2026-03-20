from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

@dataclass(frozen=True)
class Settings:
    app_name: str = "homework-backend"
    app_env: str = "dev"
    app_log_level: str = "INFO"
    app_log_output: str = "stdout"
    app_log_file: str = "logs/backend.log"
    opencode_enabled: bool = False
    opencode_timeout_sec: int = 25
    opencode_model: str = ""
    opencode_cmd: str = "opencode"
    proxy_http: str = ""
    proxy_https: str = ""
    proxy_all: str = ""
    ocr_provider_order: str = "paddle_cloud,rapidocr,paddleocr,tesseract,mock"
    ocr_lang: str = "en"
    ocr_fetch_url_enabled: bool = True
    paddleocr_doc_parsing_api_url: str = ""
    paddleocr_access_token: str = ""
    paddleocr_timeout_sec: int = 120
    opencode_raw_log_dir: str = "logs/opencode"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("HW_APP_NAME", "homework-backend"),
        app_env=os.getenv("HW_APP_ENV", "dev"),
        app_log_level=os.getenv("HW_APP_LOG_LEVEL", "INFO"),
        app_log_output=os.getenv("HW_APP_LOG_OUTPUT", "stdout"),
        app_log_file=os.getenv("HW_APP_LOG_FILE", "logs/backend.log"),
        opencode_enabled=os.getenv("HW_OPENCODE_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
        opencode_timeout_sec=int(os.getenv("HW_OPENCODE_TIMEOUT_SEC", "25")),
        opencode_model=os.getenv("HW_OPENCODE_MODEL", ""),
        opencode_cmd=os.getenv("HW_OPENCODE_CMD", "opencode"),
        proxy_http=os.getenv("HW_PROXY_HTTP", ""),
        proxy_https=os.getenv("HW_PROXY_HTTPS", ""),
        proxy_all=os.getenv("HW_PROXY_ALL", ""),
        ocr_provider_order=os.getenv("HW_OCR_PROVIDER_ORDER", "paddle_cloud,rapidocr,paddleocr,tesseract,mock"),
        ocr_lang=os.getenv("HW_OCR_LANG", "en"),
        ocr_fetch_url_enabled=os.getenv("HW_OCR_FETCH_URL_ENABLED", "true").lower()
        in {"1", "true", "yes", "on"},
        paddleocr_doc_parsing_api_url=os.getenv("PADDLEOCR_DOC_PARSING_API_URL", "").strip(),
        paddleocr_access_token=os.getenv("PADDLEOCR_ACCESS_TOKEN", "").strip(),
        paddleocr_timeout_sec=int(os.getenv("PADDLEOCR_TIMEOUT", "120")),
        opencode_raw_log_dir=os.getenv("HW_OPENCODE_RAW_LOG_DIR", "logs/opencode"),
    )
