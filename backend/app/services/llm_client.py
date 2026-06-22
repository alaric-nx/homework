from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
import base64
import httpx
import os

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _load_config(self) -> dict[str, Any]:
        """Load the multi-provider LLM config.

        查找顺序：
        1. 当前工作目录下的 backend/.config/llm.json
        2. 用户级 ~/.config/llm/config.json
        凭据全部来自配置文件 / 环境变量，源码中不内置任何密钥。
        """
        candidates = [
            Path(__file__).resolve().parents[3] / ".config" / "llm.json",
            Path.cwd() / ".config" / "llm.json",
            Path.home() / ".config" / "llm" / "config.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load LLM config %s: %s", path, e)
        return {}

    def _provider_config(self, provider: str, config: dict[str, Any]) -> dict[str, Any]:
        """Return a normalized provider entry: {base_url, api_key, default_model}.

        同时兼容旧版 opencode 风格 provider.<name>.options.{baseURL,apiKey}。
        """
        providers = config.get("providers")
        if isinstance(providers, dict) and provider in providers:
            entry = providers[provider] or {}
            return {
                "base_url": entry.get("base_url") or entry.get("baseURL"),
                "api_key": entry.get("api_key") or entry.get("apiKey"),
                "default_model": entry.get("default_model") or entry.get("model"),
            }

        legacy = config.get("provider", {}).get(provider, {}) if isinstance(config.get("provider"), dict) else {}
        if legacy:
            opts = legacy.get("options", {}) or {}
            return {
                "base_url": opts.get("baseURL") or opts.get("base_url"),
                "api_key": opts.get("apiKey") or opts.get("api_key"),
                "default_model": None,
            }
        return {}

    def _resolve_provider_and_model(
        self, model_str: str | None, config: dict[str, Any]
    ) -> tuple[str, str]:
        # 1. 显式 model 优先（请求参数 > HW_LLM_MODEL）
        effective_model = (model_str or "").strip() or self.settings.llm_model.strip()

        # 2. 形如 "<provider>/<model>" 时，直接拆分
        if "/" in effective_model:
            provider, model_name = effective_model.split("/", 1)
            return provider.strip(), model_name.strip()

        # 3. 选择 active provider：HW_LLM_PROVIDER > 配置文件 active_provider
        provider = (
            self.settings.llm_provider.strip()
            or str(config.get("active_provider") or config.get("default_provider") or "").strip()
        )
        if not provider:
            raise AppError(
                "MODEL_FAILED",
                "No LLM provider selected. Set HW_LLM_PROVIDER or active_provider in backend/.config/llm.json.",
            )

        # 4. model 名：显式 model_str（无 provider 前缀）> provider 的 default_model
        model_name = effective_model or (self._provider_config(provider, config).get("default_model") or "")
        if not model_name:
            raise AppError(
                "MODEL_FAILED",
                f"No model configured for provider '{provider}'. Set default_model in backend/.config/llm.json.",
            )
        return provider, model_name

    def _load_api_credentials(self, provider: str, config: dict[str, Any]) -> tuple[str, str]:
        # 1. 针对该 provider 的环境变量（如 HW_CPA_API_BASE_URL / HW_CPA_API_KEY）
        prefix = provider.upper().replace("-", "_")
        base_url = os.getenv(f"HW_{prefix}_API_BASE_URL") or os.getenv(f"{prefix}_API_BASE_URL")
        api_key = os.getenv(f"HW_{prefix}_API_KEY") or os.getenv(f"{prefix}_API_KEY")

        # 2. 配置文件中的 provider 凭据
        entry = self._provider_config(provider, config)
        base_url = base_url or entry.get("base_url")
        api_key = api_key or entry.get("api_key")

        if base_url and api_key:
            return base_url, api_key

        raise AppError(
            "MODEL_FAILED",
            f"No API credentials configured for provider '{provider}'. "
            "Configure it in backend/.config/llm.json (providers.<name>.base_url/api_key) "
            f"or via env HW_{prefix}_API_BASE_URL / HW_{prefix}_API_KEY.",
        )

    def _build_message_content(
        self, prompt: str, file_paths: list[str] | None
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for path in file_paths or []:
            try:
                p = Path(path)
                if p.exists():
                    img_bytes = p.read_bytes()
                    encoded = base64.b64encode(img_bytes).decode("utf-8")
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        }
                    )
            except Exception as e:
                logger.error("Failed to read/encode file %s: %s", path, e)
        return content

    def _resolve_proxy(self) -> str | None:
        if self.settings.proxy_all:
            return self.settings.proxy_all
        if self.settings.proxy_https:
            return self.settings.proxy_https
        if self.settings.proxy_http:
            return self.settings.proxy_http
        return None

    async def _request_chat_completion(
        self,
        prompt: str,
        file_paths: list[str] | None,
        model: str | None,
    ) -> str:
        """Shared chat-completion call: resolve provider/credentials, POST, return raw content text."""
        if not self.settings.llm_enabled:
            raise AppError("MODEL_FAILED", "LLM integration is disabled.")

        config = self._load_config()
        provider, model_name = self._resolve_provider_and_model(model, config)
        base_url, api_key = self._load_api_credentials(provider, config)

        logger.info(
            "llm_client_prepared provider=%s model=%s files=%s url=%s",
            provider,
            model_name,
            len(file_paths or []),
            base_url,
        )

        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": self._build_message_content(prompt, file_paths)}
            ],
            "response_format": {"type": "json_object"},
        }

        proxy = self._resolve_proxy()
        timeout = httpx.Timeout(self.settings.llm_timeout_sec, connect=10.0)

        try:
            client = (
                httpx.AsyncClient(timeout=timeout, proxy=proxy)
                if proxy
                else httpx.AsyncClient(timeout=timeout)
            )
            async with client:
                response = await client.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise AppError("TIMEOUT", "LLM API request timed out.") from exc
        except Exception as exc:
            logger.error("llm_api_call_exception: %s", exc)
            raise AppError("MODEL_FAILED", f"LLM API request failed: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "llm_api_call_failed status=%s response=%s",
                response.status_code,
                response.text.strip()[:500],
            )
            raise AppError(
                "MODEL_FAILED",
                f"LLM API request failed with status {response.status_code}.",
            )

        try:
            resp_data = response.json()
            content_text = resp_data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("Failed to parse LLM API response JSON: %s", exc)
            raise AppError("MODEL_FAILED", "Failed to parse LLM API response JSON.")

        self._dump_raw_output(prompt=prompt, stdout_text=content_text, stderr_text="")
        return content_text

    async def generate_json(
        self,
        prompt: str,
        file_paths: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        content_text = await self._request_chat_completion(prompt, file_paths, model)

        logger.info(
            "llm_api_raw_output content_len=%s content_head=%s",
            len(content_text),
            content_text[:300].replace("\n", "\\n"),
        )

        try:
            payload = self._parse_json_payload(content_text)
            self._raise_if_error(payload)
            return payload
        except json.JSONDecodeError as exc:
            raise AppError(
                "MODEL_FAILED", "LLM API output is not valid JSON."
            ) from exc

    async def generate_any_json(
        self,
        prompt: str,
        file_paths: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        content_text = await self._request_chat_completion(prompt, file_paths, model)
        try:
            return self._parse_any_json_payload(content_text)
        except json.JSONDecodeError as exc:
            raise AppError(
                "MODEL_FAILED", "LLM API output is not valid JSON."
            ) from exc

    def _raise_if_error(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        if payload.get("type") != "error":
            return
        err = payload.get("error")
        if isinstance(err, dict):
            msg = (
                err.get("message")
                or err.get("name")
                or "LLM API returned an error payload."
            )
        else:
            msg = "LLM API returned an error payload."
        raise AppError("MODEL_FAILED", msg)

    def _parse_json_payload(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if not text:
            raise json.JSONDecodeError("empty output", raw, 0)

        # Handle event stream format
        if text.startswith('{"type":'):
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get('type') == 'text' and 'part' in event:
                        part_text = event['part'].get('text', '')
                        if part_text:
                            return self._parse_json_payload(part_text)
                except json.JSONDecodeError:
                    continue

        # 1) direct JSON
        try:
            parsed = json.loads(text)
            payload = self._extract_candidate_payload(parsed)
            if payload is not None:
                return payload
        except json.JSONDecodeError:
            pass

        # 2) fenced code block ```json ... ```
        fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
        for block in fenced:
            try:
                parsed = json.loads(block.strip())
                payload = self._extract_candidate_payload(parsed)
                if payload is not None:
                    return payload
            except json.JSONDecodeError:
                continue

        # 3) best-effort extract first balanced {...}
        obj = self._extract_first_json_object(text)
        if obj is not None:
            parsed = json.loads(obj)
            payload = self._extract_candidate_payload(parsed)
            if payload is not None:
                return payload

        # 4) parse event-stream / jsonl and search for a valid payload
        objects = self._parse_json_objects(text)
        payload = self._extract_candidate_payload(objects)
        if payload is not None:
            return payload

        raise json.JSONDecodeError("no valid JSON object found", raw, 0)

    def _parse_any_json_payload(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if not text:
            raise json.JSONDecodeError("empty output", raw, 0)

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                self._raise_if_error(parsed)
                return parsed
        except json.JSONDecodeError:
            pass

        fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
        for block in fenced:
            try:
                parsed = json.loads(block.strip())
                if isinstance(parsed, dict):
                    self._raise_if_error(parsed)
                    return parsed
            except json.JSONDecodeError:
                continue

        obj = self._extract_first_json_object(text)
        if obj is not None:
            parsed = json.loads(obj)
            if isinstance(parsed, dict):
                self._raise_if_error(parsed)
                return parsed

        raise json.JSONDecodeError("no valid JSON object found", raw, 0)

    def _extract_first_json_object(self, text: str) -> str | None:
        start = text.find("{")
        while start != -1:
            depth = 0
            in_str = False
            escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]
            start = text.find("{", start + 1)
        return None

    def _parse_json_objects(self, text: str) -> list[dict[str, Any]]:
        objs: list[dict[str, Any]] = []
        for line in text.splitlines():
            s = line.strip()
            if s.lower().startswith("data:"):
                s = s[5:].strip()
            if not s or not s.startswith("{"):
                continue
            try:
                parsed = json.loads(s)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                objs.append(parsed)
        return objs

    def _extract_candidate_payload(self, value: Any) -> dict[str, Any] | None:
        # 仅用最具辨识度的核心字段来"认出"我们的结果对象。
        # 不要求所有字段全齐，这样模型即便漏了某个可选数组，
        # 也能被识别后交给 normalize 补全 / schema 修复，而不是直接判 MODEL_FAILED。
        required = {
            "question_blocks",
            "answer_items",
        }

        def walk(v: Any) -> dict[str, Any] | None:
            if isinstance(v, dict):
                if required.issubset(v.keys()):
                    return v
                # Some event payloads include JSON text in nested fields.
                for k in ("text", "delta", "output_text", "content"):
                    maybe = v.get(k)
                    if isinstance(maybe, str):
                        parsed = self._try_parse_json_str(maybe)
                        if parsed is not None:
                            found = walk(parsed)
                            if found is not None:
                                return found
                for sub in v.values():
                    found = walk(sub)
                    if found is not None:
                        return found
            elif isinstance(v, list):
                for item in v:
                    found = walk(item)
                    if found is not None:
                        return found
            return None

        return walk(value)

    def _try_parse_json_str(self, s: str) -> dict[str, Any] | None:
        candidate = s.strip()
        if not candidate:
            return None
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        obj = self._extract_first_json_object(candidate)
        if obj is None:
            return None
        try:
            parsed = json.loads(obj)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    def _dump_raw_output(self, prompt: str, stdout_text: str, stderr_text: str) -> None:
        try:
            base_dir = Path(self.settings.llm_raw_log_dir)
            if not base_dir.is_absolute():
                base_dir = Path.cwd() / base_dir
            base_dir.mkdir(parents=True, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            target = base_dir / f"{ts}.log"
            target.write_text(
                "\n".join(
                    [
                        "=== PROMPT ===",
                        prompt,
                        "",
                        "=== STDOUT ===",
                        stdout_text,
                        "",
                        "=== STDERR ===",
                        stderr_text,
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            logger.debug("llm_raw_dump_written path=%s", target)
        except Exception as exc:
            logger.warning("llm_raw_dump_failed error=%s", exc)
