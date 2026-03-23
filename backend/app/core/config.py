from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _load_env_file(
    path: Path,
    *,
    overwrite: bool = False,
    protected_keys: set[str] | None = None,
) -> None:
    if not path.exists() or not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]
        if protected_keys and key in protected_keys:
            continue
        if overwrite:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


def _bootstrap_env() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    protected = set(os.environ.keys())
    _load_env_file(backend_dir / "config.env", overwrite=False, protected_keys=protected)
    # .env 与 config.env 同 key 时，.env 优先（但不覆盖系统已存在环境变量）
    _load_env_file(backend_dir / ".env", overwrite=True, protected_keys=protected)

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
    _bootstrap_env()
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
