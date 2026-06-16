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
        # Try local config first
        local_config = Path.cwd() / ".config" / "llm.json"
        if local_config.exists():
            try:
                with open(local_config, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load local config: %s", e)

        # Try global config
        global_config = Path.home() / ".config" / "llm" / "config.json"
        if global_config.exists():
            try:
                with open(global_config, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load global config: %s", e)

        return {}

    def _resolve_provider_and_model(
        self, model_str: str | None, config: dict[str, Any]
    ) -> tuple[str, str]:
        # 1. Determine model_str to use
        effective_model = (model_str or "").strip() or self.settings.llm_model.strip()
        if not effective_model:
            effective_model = config.get("model", "").strip() or "cpa/claude-opus-4-6-thinking"

        # 2. Extract provider and clean model name
        if "/" in effective_model:
            provider, model_name = effective_model.split("/", 1)
        else:
            provider = "cpa"
            model_name = effective_model

        return provider, model_name

    def _load_api_credentials(self, provider: str, config: dict[str, Any]) -> tuple[str, str]:
        # 1. Try environment variables for this specific provider first (e.g. HW_CPA_API_BASE_URL, HW_CPA_API_KEY)
        prefix = provider.upper().replace("-", "_")
        base_url = os.getenv(f"HW_{prefix}_API_BASE_URL") or os.getenv(f"{prefix}_API_BASE_URL")
        api_key = os.getenv(f"HW_{prefix}_API_KEY") or os.getenv(f"{prefix}_API_KEY")
        
        if base_url and api_key:
            return base_url, api_key

        # 2. Try general environment variables
        base_url = os.getenv("HW_API_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        api_key = os.getenv("HW_API_KEY") or os.getenv("OPENAI_API_KEY")
        if base_url and api_key:
            return base_url, api_key

        # 3. Try to extract from the config dict
        provider_opts = config.get("provider", {}).get(provider, {}).get("options", {})
        url = provider_opts.get("baseURL")
        key = provider_opts.get("apiKey")
        if url and key:
            return url, key

        # 4. Fallback to hardcoded defaults (cpa provider)
        if provider == "cpa":
            return "https://api-ai.for2.top/v1", "sk-api-for2_DevOps"

        raise AppError(
            "MODEL_FAILED",
            f"No API credentials configured for provider '{provider}'."
        )

    async def generate_json(
        self,
        prompt: str,
        file_paths: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.llm_enabled:
            raise AppError(
                "MODEL_FAILED",
                "LLM integration is disabled.",
            )

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

        content = [{"type": "text", "text": prompt}]
        for path in file_paths or []:
            try:
                p = Path(path)
                if p.exists():
                    img_bytes = p.read_bytes()
                    encoded = base64.b64encode(img_bytes).decode("utf-8")
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded}"
                        }
                    })
            except Exception as e:
                logger.error("Failed to read/encode file %s: %s", path, e)

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "response_format": {"type": "json_object"}
        }

        # Setup proxy if configured
        proxy = None
        if self.settings.proxy_all:
            proxy = self.settings.proxy_all
        elif self.settings.proxy_https:
            proxy = self.settings.proxy_https
        elif self.settings.proxy_http:
            proxy = self.settings.proxy_http

        timeout = httpx.Timeout(self.settings.llm_timeout_sec, connect=10.0)
        
        try:
            if proxy:
                client = httpx.AsyncClient(timeout=timeout, proxy=proxy)
            else:
                client = httpx.AsyncClient(timeout=timeout)
                
            async with client:
                response = await client.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
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
                "MODEL_FAILED", f"LLM API request failed with status {response.status_code}."
            )

        try:
            resp_data = response.json()
            content_text = resp_data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("Failed to parse LLM API response JSON: %s", exc)
            raise AppError("MODEL_FAILED", "Failed to parse LLM API response JSON.")

        self._dump_raw_output(
            prompt=prompt, stdout_text=content_text, stderr_text=""
        )

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
        required = {
            "question_meaning_zh",
            "answer_lines",
            "explanation_zh",
            "key_vocabulary",
            "speak_units",
            "uncertainty",
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
