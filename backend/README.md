# Homework English Assistant Backend (MVP)

## 1) Goals
- Receive homework photos from Android app.
- Parse exercise meaning in Chinese.
- Return reference answer and short parent-friendly explanation.
- Provide pronunciation for words and full sentences (click-to-speak).
- Keep output stable with strict JSON schema.

## 2) Architecture Choice
Use `Android + Remote Backend`.

Backend responsibilities:
- OCR extraction from image.
- LLM reasoning and structured parsing.
- Pronunciation content generation and TTS URL generation.
- Safety controls (child mode, uncertainty flags, fallback).
- Observability (logs, trace ids, cost/latency metrics).

## 3) Directory Layout
- `src/api`: HTTP routes/controllers
- `src/orchestrators`: business workflow pipeline
- `src/services/ocr`: OCR adapter(s)
- `src/services/llm`: LLM adapter(s)
- `src/services/tts`: TTS adapter(s)
- `src/services/storage`: object storage adapter(s)
- `src/schemas`: request/response JSON schemas
- `src/config`: env and runtime configs
- `src/core`: domain models and errors
- `src/utils`: shared helpers
- `tests/unit`: unit tests
- `tests/integration`: integration tests
- `docs`: API and prompt design docs

## 4) Core API (v1)
### `POST /v1/homework/parse`
Input:
- image file or image_url
- grade (optional)
- expected_type (optional: choose/fill/read/translate)
- locale (default: zh-CN)

Output (strict JSON):
- `question_text`: recognized exercise text
- `question_meaning_zh`: what this asks in Chinese
- `reference_answer`: recommended answer
- `explanation_zh`: short explanation for parent
- `key_vocabulary`: list of words with IPA + meaning
- `speak_units`: clickable units (word/sentence)
- `uncertainty`: confidence + warning message

### `POST /v1/tts/speak`
Input:
- text
- voice
- speed

Output:
- `audio_url` (or base64 audio)

## 5) Orchestration Flow
1. Upload image -> storage
2. OCR -> raw text + bbox + confidence
3. Exercise classifier (optional)
4. LLM parse with schema constraint
5. Validate output against schema
6. Generate TTS units (word/sentence)
7. Return normalized response

Fallback rules:
- If OCR confidence is low, return `uncertainty.requires_review = true`.
- If schema validation fails, retry with stricter prompt once.
- If still fails, return partial result + error_code.

## 6) Skills Positioning (Important)
Skills are great for:
- Defining parse policy by exercise type.
- Standardizing output style and pedagogy level.
- Rapidly iterating prompts/rules.

Production recommendation:
- Do not rely on runtime skill files directly in app serving path.
- Convert skill logic into versioned backend assets:
  - prompt templates
  - policy configs
  - schema validators
- Keep these assets hot-updatable through config store.

## 7) First Milestone (MVP)
- Single endpoint `/v1/homework/parse`
- One OCR provider + one LLM provider + one TTS provider
- Fixed JSON schema output
- Parent mode only (no student chat)
- Basic logging and request id

## 8) Non-Functional Baseline
- p95 latency target: <= 6s (single image)
- timeout: 12s
- retries: max 1 per downstream provider
- image retention default: 24h (configurable)
- privacy: encrypted at rest and in transit

## 9) Implemented in This MVP
- `app/main.py`: FastAPI entry, request-id middleware, unified error handler
- `app/api/routes.py`: `/healthz` and `/v1/homework/parse`
- `app/skills/common/subject_router.py`: subject routing (english/chinese/math; MVP only english enabled)
- `app/skills/common/ocr_skill.py`: OCR skill placeholder adapter
- `app/skills/english/english_solver_skill.py`: English solver skill with OpenCode adapter + fallback
- `app/skills/common/response_schema_guard.py`: JSON schema guard + strict validation
- `schemas/homework_parse.schema.json`: fixed output schema

## 10) Quick Start
1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Start API:
```bash
cd backend
./start_backend.sh
```

3. Test request:
```bash
curl -X POST "http://127.0.0.1:8000/v1/homework/parse?expected_type=english" \
  -H "content-type: image/jpeg" \
  --data-binary "@/absolute/path/to/homework.jpg"
```

5. Parse and fill answers back into image:
```bash
curl -sS -X POST "http://127.0.0.1:8000/v1/homework/parse-fill?expected_type=english" \
  -H "content-type: image/jpeg" \
  --data-binary "@/absolute/path/to/homework.jpg" > /tmp/parse-fill.json
```
Return fields:
- `result`: structured parse result
- `filled_image_base64`: image with answers filled into answer area
- `filled_image_path`: saved file path (backend/output/filled-*.jpg)

Answer fill behavior:
- Tries automatic blank-line detection in the answer area (layout-adaptive).
- Falls back to ratio-based placement only when line detection fails.

View latest filled image:
```bash
cd backend
ls -t output/filled-*.jpg | head -n 1
```

4. Check OCR provider availability:
```bash
curl -sS http://127.0.0.1:8000/v1/ocr/providers
```

## 11) OpenCode Integration Notes
- Backend does not install `opencode`; it only calls your local command when enabled.
- Runtime config is in `backend/config.env` (recommended single place).
- `HW_OPENCODE_MODEL` can be empty (recommended) to use opencode default model.
- Log settings:
  - `HW_APP_LOG_LEVEL=DEBUG`
  - `HW_APP_LOG_OUTPUT=file`
  - `HW_APP_LOG_FILE=logs/backend.log`
  - `HW_OPENCODE_RAW_LOG_DIR=logs/opencode`
- Expected CLI contract:
```bash
opencode run --format json --model <model> "<prompt>"
```
- If your local `opencode` command differs, only adjust:
`app/services/opencode_client.py`

## 12) OCR Plugin Providers
- OCR skill is now pluggable and tries providers in configured order.
- Configure in `backend/config.env`:
  - `HW_OCR_PROVIDER_ORDER=paddle_cloud,rapidocr,paddleocr,tesseract,mock`
  - `HW_OCR_LANG=en`
  - `HW_OCR_FETCH_URL_ENABLED=true`
- Built-in provider adapters:
  - `paddle_cloud` (uses `PADDLEOCR_DOC_PARSING_API_URL` + `PADDLEOCR_ACCESS_TOKEN`)
  - `rapidocr` (package: `rapidocr-onnxruntime`)
  - `paddleocr` (package: `paddleocr`)
  - `tesseract` (packages/binary: `pytesseract` + `Pillow` + system `tesseract`)
  - `mock` (always available fallback)
- Optional install examples:
```bash
pip install rapidocr-onnxruntime
pip install paddleocr
pip install pytesseract Pillow
```

## 13) Skills Search/Install (Project Scope)
- We searched via `find-skills` and installed:
  - `ocr-document-processor`
  - `paddleocr-text-recognition`
  - `paddleocr-doc-parsing`
- Installed paths:
  - `/Users/y/Documents/CodexSpace/homework/.agents/skills/ocr-document-processor`
  - `/Users/y/Documents/CodexSpace/homework/.agents/skills/paddleocr-text-recognition`
  - `/Users/y/Documents/CodexSpace/homework/.agents/skills/paddleocr-doc-parsing`

## 14) Error Code Baseline
- `INVALID_REQUEST`
- `UNSUPPORTED_SUBJECT`
- `OCR_FAILED`
- `MODEL_FAILED`
- `SCHEMA_VALIDATION_FAILED`
- `TIMEOUT`
- `INTERNAL_ERROR`
