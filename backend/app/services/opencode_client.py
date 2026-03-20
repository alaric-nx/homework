from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class OpencodeClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_json(self, prompt: str, file_paths: list[str] | None = None) -> dict[str, Any]:
        if not self.settings.opencode_enabled:
            raise AppError("MODEL_FAILED", "OpenCode integration is disabled (set HW_OPENCODE_ENABLED=true).")

        env = self._build_env()

        cmd = [self.settings.opencode_cmd, "run", "--format", "json"]
        if self.settings.opencode_model.strip():
            cmd.extend(["--model", self.settings.opencode_model.strip()])
        for path in file_paths or []:
            cmd.extend(["--file", path])
        # Ensure positional prompt is not consumed by --file array parsing.
        cmd.extend(["--", prompt])
        logger.info("opencode_cmd_prepared files=%s model=%s", len(file_paths or []), self.settings.opencode_model or "<default>")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.settings.opencode_timeout_sec)
        except asyncio.TimeoutError as exc:
            raise AppError("TIMEOUT", "OpenCode request timed out.") from exc
        except FileNotFoundError as exc:
            raise AppError("MODEL_FAILED", f"Cannot find opencode command: {self.settings.opencode_cmd}") from exc

        stdout_text = stdout.decode("utf-8", errors="ignore")
        stderr_text = stderr.decode("utf-8", errors="ignore")
        self._dump_raw_output(prompt=prompt, stdout_text=stdout_text, stderr_text=stderr_text)

        if proc.returncode != 0:
            logger.error(
                "opencode_exit_nonzero stderr=%s stdout_head=%s",
                stderr_text.strip(),
                stdout_text[:300].replace("\n", "\\n"),
            )
            raise AppError("MODEL_FAILED", "OpenCode process returned non-zero exit code.")

        logger.info(
            "opencode_raw_output stdout_len=%s stderr_len=%s stdout_head=%s",
            len(stdout_text),
            len(stderr_text),
            stdout_text[:300].replace("\n", "\\n"),
        )

        try:
            payload = self._parse_json_payload(stdout_text)
            self._raise_if_opencode_error(payload)
            return payload
        except json.JSONDecodeError as exc:
            raise AppError("MODEL_FAILED", "OpenCode output is not valid JSON.") from exc

    def _build_env(self) -> dict[str, str]:
        import os

        env = os.environ.copy()
        if self.settings.proxy_http:
            env["HTTP_PROXY"] = self.settings.proxy_http
            env["http_proxy"] = self.settings.proxy_http
        if self.settings.proxy_https:
            env["HTTPS_PROXY"] = self.settings.proxy_https
            env["https_proxy"] = self.settings.proxy_https
        if self.settings.proxy_all:
            env["ALL_PROXY"] = self.settings.proxy_all
            env["all_proxy"] = self.settings.proxy_all
        return env

    def _raise_if_opencode_error(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        if payload.get("type") != "error":
            return
        err = payload.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("name") or "OpenCode returned an error payload."
        else:
            msg = "OpenCode returned an error payload."
        raise AppError("MODEL_FAILED", msg)

    def _parse_json_payload(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if not text:
            raise json.JSONDecodeError("empty output", raw, 0)

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
            "reference_answer",
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
            base_dir = Path(self.settings.opencode_raw_log_dir)
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
            logger.debug("opencode_raw_dump_written path=%s", target)
        except Exception as exc:
            logger.warning("opencode_raw_dump_failed error=%s", exc)
