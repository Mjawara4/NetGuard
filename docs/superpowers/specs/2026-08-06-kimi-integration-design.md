# Kimi LLM Provider Integration Design

**Date:** 2026-08-06  
**Status:** Approved  
**Scope:** Add Moonshot/Kimi as a selectable LLM provider across all NetGuard LLM call sites.

## 1. Goal

Allow every NetGuard component that currently calls OpenAI or Gemini to also call **Kimi (Moonshot AI)** by setting `LLM_PROVIDER=kimi` and `KIMI_API_KEY`. The target model is `kimi-k2.5`.

## 2. Motivation

The user wants to replace Google (Gemini) with Kimi for LLM-powered features. Currently the provider logic is duplicated across multiple files, making it hard to add or switch providers. This design adds Kimi and reduces that duplication.

## 3. Architecture

We introduce a small shared helper module on each side of the application:

- **Backend:** `backend/app/core/llm_client.py`
- **Agents:** `agents/llm_client.py`

Each helper exposes one primary function:

```python
def chat_completion(prompt: str, response_format: str | None = None) -> str | None:
    ...
```

Callers pass a prompt and optionally request JSON output. The helper:

1. Reads `LLM_PROVIDER` and the matching API key at import time.
2. Dispatches to Gemini, OpenAI, or Kimi.
3. Returns the raw response text after stripping markdown fences.
4. Returns `None` and logs on error or missing configuration.

### Files updated to use the helper

- `backend/app/services/alert_grouping.py`
- `backend/app/routers/ai_ops.py`
- `backend/app/routers/ai_analytics.py`
- `agents/reporter_agent.py`
- `agents/ai_fix_agent.py`

### Configuration changes

- Add `KIMI_API_KEY` to `.env.production` (gitignored).
- Pass `KIMI_API_KEY` and `LLM_PROVIDER` into `ai-fix-agent` and `reporter-agent` in `docker-compose.yml`.
- No new Python dependency is required because Kimi’s API is OpenAI-compatible and `openai` is already installed.

## 4. Components

### 4.1 `backend/app/core/llm_client.py`

- Reads `LLM_PROVIDER`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `KIMI_API_KEY`.
- Validates that the active provider has a non-empty key.
- Implements provider-specific calls:
  - `gemini` → `google.genai.Client`, model `gemini-2.5-flash-lite`
  - `openai` → `openai.OpenAI`, model `gpt-3.5-turbo`
  - `kimi` → `openai.OpenAI(base_url="https://api.moonshot.cn/v1")`, model `kimi-k2.5`
- Strips ` ```json ... ``` ` fences from responses.
- Never logs API key values.

### 4.2 `agents/llm_client.py`

- Same public contract as the backend helper.
- Also supports the generic `LLM_API_KEY` fallback for backward compatibility.
- Uses the agents’ existing logging style.

### 4.3 Updated call sites

Each existing LLM caller is simplified to:

```python
from app.core.llm_client import chat_completion  # backend
# or
from llm_client import chat_completion             # agents

response_text = chat_completion(prompt, response_format="json_object")
```

Inline Gemini/OpenAI branches are removed.

## 5. Data Flow

1. **Startup:** Helper module reads environment configuration once.
2. **Prompt building:** Existing agent/router builds its prompt unchanged.
3. **Single call:** Caller invokes `chat_completion(prompt)`.
4. **Dispatch:** Helper selects the provider and calls the appropriate API.
5. **Cleaning:** Helper strips markdown fences and returns raw text.
6. **Parsing:** Caller parses JSON or uses the text directly, preserving existing fallback logic.

## 6. Error Handling

| Scenario | Behavior |
|---|---|
| Missing provider key | Log warning, return `None`, caller falls back to template/mock |
| Kimi API network/auth error | Log error, return `None`, caller falls back |
| Unknown provider | Log error, return `None` |
| Malformed JSON from LLM | Handled by existing caller-side cleanup/parse logic |

The design preserves the codebase’s existing “fail soft” behavior.

## 7. Testing Plan

1. **Backend regression:** Run `LLM_PROVIDER=openai` and `LLM_PROVIDER=gemini` through alert creation and AI chat to confirm no regressions.
2. **Kimi integration:** Run `LLM_PROVIDER=kimi` with a valid `KIMI_API_KEY`, create an alert, and verify incident renaming succeeds.
3. **Agent regression:** Start `ai-fix-agent` and `reporter-agent` with each provider and confirm no `Unknown provider` errors.
4. **Missing-key fallback:** Run with `LLM_PROVIDER=kimi` and no key to confirm graceful fallback.

## 8. Security Notes

- The `KIMI_API_KEY` value is secret and must only live in `.env.production` (already gitignored) or runtime secrets, never in code or logs.
- The helper logs provider selection and error messages but must not log the key.

## 9. Out of Scope

- Removing Gemini or OpenAI support.
- Changing prompt content or model parameters beyond provider/model selection.
- Unifying the backend and agents into a single shared package.

## 10. Open Questions

None. All requirements clarified:
- Scope: all LLM call sites
- Provider model: add Kimi alongside OpenAI/Gemini
- Kimi model: `kimi-k2.5`
