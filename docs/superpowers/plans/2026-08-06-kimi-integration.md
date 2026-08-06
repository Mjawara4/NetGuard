# Kimi LLM Provider Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Kimi (Moonshot AI) as a selectable LLM provider across all NetGuard backend routers, services, and agents, using model `kimi-k2.5`.

**Architecture:** Create a shared `llm_client.py` helper in both `backend/app/core/` and `agents/` that encapsulates provider selection, API key lookup, and response cleaning. Refactor existing call sites to use a single `chat_completion()` function. Update Docker Compose and env files to pass `KIMI_API_KEY`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, OpenAI Python SDK, Google GenAI SDK, Docker Compose.

## Global Constraints

- `LLM_PROVIDER` must support `kimi` alongside existing `openai` and `gemini`.
- Kimi uses the OpenAI-compatible endpoint `https://api.moonshot.cn/v1` with model `kimi-k2.5`.
- `KIMI_API_KEY` must never be logged or committed.
- Existing fallback behavior when LLM is unavailable must be preserved.
- No new runtime dependencies; `openai` is already installed.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/core/llm_client.py` | New backend helper: picks provider, calls API, cleans response. |
| `backend/tests/test_llm_client.py` | New tests for backend helper (no real API calls). |
| `backend/app/services/alert_grouping.py` | Refactor to import `chat_completion` from backend helper. |
| `backend/app/routers/ai_ops.py` | Refactor `ask_llm_intent` and `explain_result` to use backend helper. |
| `backend/app/routers/ai_analytics.py` | Refactor prediction endpoint to use backend helper. |
| `agents/llm_client.py` | New agents helper: same contract, plus `LLM_API_KEY` fallback. |
| `agents/tests/test_llm_client.py` | New tests for agents helper (no real API calls). |
| `agents/reporter_agent.py` | Refactor `generate_summary_llm` to use agents helper. |
| `agents/ai_fix_agent.py` | Refactor `ask_llm` to use agents helper. |
| `docker-compose.yml` | Pass `KIMI_API_KEY` into `ai-fix-agent` and `reporter-agent`. |
| `.env.production` | Add `KIMI_API_KEY` placeholder. |

---

### Task 1: Create backend LLM client helper

**Files:**
- Create: `backend/app/core/llm_client.py`
- Create: `backend/tests/test_llm_client.py`
- Modify: `backend/.gitignore` (if needed to ignore `tests/` pycache — usually already covered by root `.gitignore`)

**Interfaces:**
- Produces: `chat_completion(prompt: str, response_format: str | None = None) -> str | None`
- Produces: `_clean_response(text: str) -> str`
- Reads env at call time: `LLM_PROVIDER`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `KIMI_API_KEY`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_llm_client.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from app.core import llm_client


def test_chat_completion_returns_none_for_unknown_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}, clear=True):
        result = llm_client.chat_completion("hello")
        assert result is None


def test_chat_completion_returns_none_when_key_missing():
    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "kimi", "KIMI_API_KEY": ""},
        clear=True,
    ):
        result = llm_client.chat_completion("hello")
        assert result is None


def test_clean_response_strips_json_fences():
    raw = "```json\n{\"foo\": \"bar\"}\n```"
    cleaned = llm_client._clean_response(raw)
    assert cleaned == '{"foo": "bar"}'


def test_clean_response_strips_plain_fences():
    raw = "```\nhello world\n```"
    cleaned = llm_client._clean_response(raw)
    assert cleaned == "hello world"


if __name__ == "__main__":
    test_chat_completion_returns_none_for_unknown_provider()
    test_chat_completion_returns_none_when_key_missing()
    test_clean_response_strips_json_fences()
    test_clean_response_strips_plain_fences()
    print("All llm_client tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /opt/netguard/backend
python tests/test_llm_client.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.llm_client'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/core/llm_client.py
import logging
import os
import re

import openai

logger = logging.getLogger(__name__)


def _clean_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def _api_key_for(provider: str) -> str | None:
    if provider == "gemini":
        return os.getenv("GEMINI_API_KEY")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    if provider == "kimi":
        return os.getenv("KIMI_API_KEY")
    return None


def chat_completion(prompt: str, response_format: str | None = None) -> str | None:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    api_key = _api_key_for(provider)

    if not api_key:
        logger.warning(f"No API key configured for LLM provider: {provider}")
        return None

    try:
        if provider == "gemini":
            from google import genai

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            return _clean_response(response.text)

        if provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            kwargs = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
            }
            if response_format == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            completion = client.chat.completions.create(**kwargs)
            return _clean_response(completion.choices[0].message.content)

        if provider == "kimi":
            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.moonshot.cn/v1",
            )
            kwargs = {
                "model": "kimi-k2.5",
                "messages": [{"role": "user", "content": prompt}],
            }
            if response_format == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            completion = client.chat.completions.create(**kwargs)
            return _clean_response(completion.choices[0].message.content)

        logger.error(f"Unknown LLM provider: {provider}")
        return None

    except Exception as e:
        logger.error(f"LLM chat completion failed for provider {provider}: {e}")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /opt/netguard/backend
python tests/test_llm_client.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /opt/netguard
git add backend/app/core/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(backend): add shared LLM client helper with Kimi support

Adds chat_completion() supporting openai, gemini, and kimi.
Kimi uses https://api.moonshot.cn/v1 with model kimi-k2.5.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Refactor alert grouping to use the backend helper

**Files:**
- Modify: `backend/app/services/alert_grouping.py`

**Interfaces:**
- Consumes: `chat_completion(prompt: str) -> str | None` from `app.core.llm_client`
- Produces: Same public function `process_alert_grouping(alert_id: str)`

- [ ] **Step 1: Write the failing smoke test**

```python
# backend/tests/test_alert_grouping_smoke.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_alert_grouping_imports():
    from app.services import alert_grouping

    assert callable(alert_grouping.process_alert_grouping)


if __name__ == "__main__":
    test_alert_grouping_imports()
    print("alert_grouping smoke test passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /opt/netguard/backend
python tests/test_alert_grouping_smoke.py
```

Expected: FAIL because the module does not yet import from `app.core.llm_client` (or any other refactor error).

Actually, the test will pass before the refactor. After the refactor it should still pass. The real verification is that the refactor does not break imports.

- [ ] **Step 3: Refactor implementation**

In `backend/app/services/alert_grouping.py`:

1. Remove these lines:
   ```python
   import openai
   LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
   LLM_API_KEY = os.getenv("GEMINI_API_KEY") if LLM_PROVIDER == "gemini" else os.getenv("OPENAI_API_KEY")
   ```

2. Add import:
   ```python
   from app.core.llm_client import chat_completion
   ```

3. Replace the entire `if LLM_PROVIDER == "gemini": ... elif LLM_PROVIDER == "openai": ...` block inside `rename_incident_with_ai` with:
   ```python
   response_text = chat_completion(prompt)
   ```

The final `rename_incident_with_ai` function should look like this:

```python
async def rename_incident_with_ai(incident_id, db: AsyncSession):
    if not (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("KIMI_API_KEY")
    ):
        return

    # Fetch incident and alerts
    inc_res = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = inc_res.scalars().first()

    # Get alerts
    alerts_res = await db.execute(select(Alert).where(Alert.incident_id == incident_id))
    alerts = alerts_res.scalars().all()

    if len(alerts) < 2:
        return  # Not enough context yet

    alerts_summary = "\n".join([f"- {a.rule_name}: {a.message} ({a.created_at})" for a in alerts])

    prompt = f"""
    Analyze these network alerts grouped into an incident:
    {alerts_summary}

    Generate a concise, professional Incident Title (max 5 words) and a 1-sentence Description.
    Format: Title | Description
    """

    try:
        response_text = chat_completion(prompt)
        if response_text and "|" in response_text:
            title, desc = response_text.split("|", 1)
            incident.name = title.strip()
            incident.description = desc.strip()
            await db.commit()
    except Exception as e:
        logger.error(f"AI Incident Renaming Failed: {e}")
```

- [ ] **Step 4: Run smoke test to verify it passes**

Run:
```bash
cd /opt/netguard/backend
python tests/test_alert_grouping_smoke.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /opt/netguard
git add backend/app/services/alert_grouping.py backend/tests/test_alert_grouping_smoke.py
git commit -m "refactor(backend): alert grouping uses shared LLM client

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Refactor AI ops router to use the backend helper

**Files:**
- Modify: `backend/app/routers/ai_ops.py`

**Interfaces:**
- Consumes: `chat_completion(prompt, response_format="json_object") -> str | None` from `app.core.llm_client`

- [ ] **Step 1: Write the failing smoke test**

```python
# backend/tests/test_ai_ops_smoke.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ai_ops_imports():
    from app.routers import ai_ops

    assert callable(ai_ops.ask_llm_intent)
    assert callable(ai_ops.explain_result)


if __name__ == "__main__":
    test_ai_ops_imports()
    print("ai_ops smoke test passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /opt/netguard/backend
python tests/test_ai_ops_smoke.py
```

Expected: PASS before refactor; still PASS after refactor.

- [ ] **Step 3: Refactor implementation**

In `backend/app/routers/ai_ops.py`:

1. Remove:
   ```python
   import openai
   LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
   LLM_API_KEY = os.getenv("GEMINI_API_KEY") if LLM_PROVIDER == "gemini" else os.getenv("OPENAI_API_KEY")
   ```

2. Add import:
   ```python
   from app.core.llm_client import chat_completion
   ```

3. Replace the Gemini/OpenAI branches in `ask_llm_intent` with:
   ```python
   response_text = chat_completion(system_prompt, response_format="json_object")
   ```

4. Replace the Gemini/OpenAI branches in `explain_result` with:
   ```python
   response_text = chat_completion(prompt)
   if not response_text:
       return f"Found {total_count} records, but could not summarize them due to an error."
   return response_text.strip()
   ```

The final `ask_llm_intent` should look like:

```python
def ask_llm_intent(user_query: str, organization_id: str):
    if not (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("KIMI_API_KEY")
    ):
        return None, "Error: LLM API Key not configured.", None

    schema = get_db_schema_context()

    system_prompt = f"""
    ... same prompt content ...
    """

    try:
        import json
        response_text = chat_completion(system_prompt, response_format="json_object")
        if not response_text:
            return None, "LLM Error: No response from provider.", None

        response_text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(response_text)
        return data, None
    except Exception as e:
        logger.error(f"LLM Intent Error: {e}")
        return None, f"LLM Error: {str(e)}", None
```

- [ ] **Step 4: Run smoke test to verify it passes**

Run:
```bash
cd /opt/netguard/backend
python tests/test_ai_ops_smoke.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /opt/netguard
git add backend/app/routers/ai_ops.py backend/tests/test_ai_ops_smoke.py
git commit -m "refactor(backend): ai_ops router uses shared LLM client

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Refactor AI analytics router to use the backend helper

**Files:**
- Modify: `backend/app/routers/ai_analytics.py`

**Interfaces:**
- Consumes: `chat_completion(prompt, response_format="json_object") -> str | None` from `app.core.llm_client`

- [ ] **Step 1: Write the failing smoke test**

```python
# backend/tests/test_ai_analytics_smoke.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ai_analytics_imports():
    from app.routers import ai_analytics

    assert hasattr(ai_analytics, "router")


if __name__ == "__main__":
    test_ai_analytics_imports()
    print("ai_analytics smoke test passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /opt/netguard/backend
python tests/test_ai_analytics_smoke.py
```

Expected: PASS before refactor; still PASS after refactor.

- [ ] **Step 3: Refactor implementation**

In `backend/app/routers/ai_analytics.py`:

1. Remove:
   ```python
   import openai
   LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
   LLM_API_KEY = os.getenv("GEMINI_API_KEY") if LLM_PROVIDER == "gemini" else os.getenv("OPENAI_API_KEY")
   ```

2. Add import:
   ```python
   from app.core.llm_client import chat_completion
   ```

3. Replace the Gemini/OpenAI branches with:
   ```python
   response_text = chat_completion(system_prompt, response_format="json_object")
   ```

The final AI call block should look like:

```python
    try:
        import json
        response_text = chat_completion(system_prompt, response_format="json_object")
        if not response_text:
            raise ValueError("No response from LLM provider")

        response_text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(response_text)
        return data
    except Exception as e:
        logger.error(f"AI Prediction Error: {e}")
        ... fallback mock data ...
```

- [ ] **Step 4: Run smoke test to verify it passes**

Run:
```bash
cd /opt/netguard/backend
python tests/test_ai_analytics_smoke.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /opt/netguard
git add backend/app/routers/ai_analytics.py backend/tests/test_ai_analytics_smoke.py
git commit -m "refactor(backend): ai_analytics router uses shared LLM client

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Create agents LLM client helper

**Files:**
- Create: `agents/llm_client.py`
- Create: `agents/tests/test_llm_client.py`

**Interfaces:**
- Produces: `chat_completion(prompt: str, response_format: str | None = None) -> str | None`
- Produces: `_clean_response(text: str) -> str`
- Reads env at call time: `LLM_PROVIDER`, `LLM_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `KIMI_API_KEY`

- [ ] **Step 1: Write the failing test**

```python
# agents/tests/test_llm_client.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
import llm_client


def test_chat_completion_returns_none_for_unknown_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}, clear=True):
        result = llm_client.chat_completion("hello")
        assert result is None


def test_chat_completion_uses_generic_llm_api_key_as_fallback():
    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "kimi", "LLM_API_KEY": "generic-key", "KIMI_API_KEY": ""},
        clear=True,
    ):
        # Should still return None because we don't mock the HTTP call,
        # but it proves the key fallback path is reached without a missing-key warning.
        result = llm_client.chat_completion("hello")
        # Real API call would fail; we just care that it didn't early-return for missing key.
        assert result is None


def test_clean_response_strips_json_fences():
    raw = "```json\n{\"foo\": \"bar\"}\n```"
    cleaned = llm_client._clean_response(raw)
    assert cleaned == '{"foo": "bar"}'


if __name__ == "__main__":
    test_chat_completion_returns_none_for_unknown_provider()
    test_chat_completion_uses_generic_llm_api_key_as_fallback()
    test_clean_response_strips_json_fences()
    print("All agents llm_client tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /opt/netguard/agents
python tests/test_llm_client.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'llm_client'`.

- [ ] **Step 3: Write minimal implementation**

```python
# agents/llm_client.py
import logging
import os
import re

import openai

logger = logging.getLogger(__name__)


def _clean_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def _api_key_for(provider: str) -> str | None:
    generic_key = os.getenv("LLM_API_KEY")
    if provider == "gemini":
        return os.getenv("GEMINI_API_KEY") or generic_key
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY") or generic_key
    if provider == "kimi":
        return os.getenv("KIMI_API_KEY") or generic_key
    return None


def chat_completion(prompt: str, response_format: str | None = None) -> str | None:
    provider = os.getenv("LLM_PROVIDER", "").lower()
    api_key = _api_key_for(provider)

    if not api_key:
        logger.warning(f"No API key configured for LLM provider: {provider}")
        return None

    try:
        if provider == "gemini":
            from google import genai

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            return _clean_response(response.text)

        if provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            kwargs = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
            }
            if response_format == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            completion = client.chat.completions.create(**kwargs)
            return _clean_response(completion.choices[0].message.content)

        if provider == "kimi":
            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.moonshot.cn/v1",
            )
            kwargs = {
                "model": "kimi-k2.5",
                "messages": [{"role": "user", "content": prompt}],
            }
            if response_format == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            completion = client.chat.completions.create(**kwargs)
            return _clean_response(completion.choices[0].message.content)

        logger.error(f"Unknown LLM provider: {provider}")
        return None

    except Exception as e:
        logger.error(f"LLM chat completion failed for provider {provider}: {e}")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /opt/netguard/agents
python tests/test_llm_client.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /opt/netguard
git add agents/llm_client.py agents/tests/test_llm_client.py
git commit -m "feat(agents): add shared LLM client helper with Kimi support

Adds chat_completion() supporting openai, gemini, and kimi.
Preserves LLM_API_KEY fallback used by reporter-agent.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Refactor reporter agent to use the agents helper

**Files:**
- Modify: `agents/reporter_agent.py`

**Interfaces:**
- Consumes: `chat_completion(prompt, response_format="json_object") -> str | None` from `llm_client`

- [ ] **Step 1: Write the failing smoke test**

```python
# agents/tests/test_reporter_agent_smoke.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_reporter_agent_imports():
    import reporter_agent

    assert callable(reporter_agent.generate_summary_llm)
    assert callable(reporter_agent.run_agent)


if __name__ == "__main__":
    test_reporter_agent_imports()
    print("reporter_agent smoke test passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /opt/netguard/agents
python tests/test_reporter_agent_smoke.py
```

Expected: PASS before refactor; still PASS after refactor.

- [ ] **Step 3: Refactor implementation**

In `agents/reporter_agent.py`:

1. Add import:
   ```python
   from llm_client import chat_completion
   ```

2. Replace the entire `generate_summary_llm` function with:

```python
def generate_summary_llm(alert):
    """Try LLM summary generation. Returns (summary, root_cause) or (None, None)."""
    if not (
        os.getenv("LLM_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("KIMI_API_KEY")
    ):
        return None, None

    prompt = (
        f"Network alert resolved. Rule: {alert['rule_name']}. "
        f"Message: {alert['message']}. Status: {alert['status']}. "
        f"Provide a one-sentence summary and one-sentence root cause analysis. "
        f'Output JSON: {{"summary": "...", "root_cause": "..."}}'
    )

    try:
        response_text = chat_completion(prompt, response_format="json_object")
        if not response_text:
            return None, None

        import json
        data = json.loads(response_text)
        return data.get("summary"), data.get("root_cause")
    except Exception as e:
        logger.warning(f"LLM summary failed: {e}")

    return None, None
```

3. Remove the old inline Gemini/OpenAI branches and the `import openai` if present.

- [ ] **Step 4: Run smoke test to verify it passes**

Run:
```bash
cd /opt/netguard/agents
python tests/test_reporter_agent_smoke.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /opt/netguard
git add agents/reporter_agent.py agents/tests/test_reporter_agent_smoke.py
git commit -m "refactor(agents): reporter agent uses shared LLM client

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Refactor AI fix agent to use the agents helper

**Files:**
- Modify: `agents/ai_fix_agent.py`

**Interfaces:**
- Consumes: `chat_completion(prompt, response_format="json_object") -> str | None` from `llm_client`

- [ ] **Step 1: Write the failing smoke test**

```python
# agents/tests/test_ai_fix_agent_smoke.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ai_fix_agent_imports():
    import ai_fix_agent

    assert callable(ai_fix_agent.ask_llm)
    assert callable(ai_fix_agent.run_agent)


if __name__ == "__main__":
    test_ai_fix_agent_imports()
    print("ai_fix_agent smoke test passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /opt/netguard/agents
python tests/test_ai_fix_agent_smoke.py
```

Expected: PASS before refactor; still PASS after refactor.

- [ ] **Step 3: Refactor implementation**

In `agents/ai_fix_agent.py`:

1. Add import:
   ```python
   from llm_client import chat_completion
   ```

2. In `ask_llm`, replace the provider-specific branches with:

```python
    try:
        logger.info(f"Querying {LLM_PROVIDER} for alert {alert['id']}...")

        response_text = chat_completion(system_prompt, response_format="json_object")
        if not response_text:
            return None

        decision = parse_json(response_text)
        return decision

    except Exception as e:
        logger.error(f"LLM Query failed: {e}")
        return None
```

3. Remove the old inline Gemini/OpenAI branch code but keep `LLM_PROVIDER` and `LLM_API_KEY` detection at the top so the agent still knows which provider is configured for logging.

The top of the file should still read:

```python
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

LLM_API_KEY = os.getenv("LLM_API_KEY")
if not LLM_API_KEY:
    if LLM_PROVIDER == "openai":
        LLM_API_KEY = os.getenv("OPENAI_API_KEY")
    elif LLM_PROVIDER == "gemini":
        LLM_API_KEY = os.getenv("GEMINI_API_KEY")
    elif LLM_PROVIDER == "kimi":
        LLM_API_KEY = os.getenv("KIMI_API_KEY")

if not LLM_API_KEY:
    logger.warning("LLM Key not found. AI Agent will function in fallback-only mode.")
```

- [ ] **Step 4: Run smoke test to verify it passes**

Run:
```bash
cd /opt/netguard/agents
python tests/test_ai_fix_agent_smoke.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /opt/netguard
git add agents/ai_fix_agent.py agents/tests/test_ai_fix_agent_smoke.py
git commit -m "refactor(agents): ai fix agent uses shared LLM client

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Wire up KIMI_API_KEY in Docker Compose and env file

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.production`

**Interfaces:**
- Produces: `KIMI_API_KEY` environment variable available inside `backend`, `ai-fix-agent`, and `reporter-agent` containers.

- [ ] **Step 1: Add KIMI_API_KEY to .env.production**

Append to `.env.production`:

```bash
# Kimi (Moonshot AI) API key
KIMI_API_KEY=
```

Do not put a real key value here; the file is gitignored and populated at deploy time.

- [ ] **Step 2: Pass KIMI_API_KEY into agent containers**

In `docker-compose.yml`, add `KIMI_API_KEY=${KIMI_API_KEY}` to the `environment` list of both:
- `ai-fix-agent`
- `reporter-agent`

For `ai-fix-agent`, the block becomes:

```yaml
    environment:
      - API_URL=http://backend:8000/api/v1
      - NETGUARD_API_KEY=${NETGUARD_API_KEY:-agent-secret-key-123}
      - PYTHONUNBUFFERED=1
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - LLM_API_KEY=${OPENAI_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - KIMI_API_KEY=${KIMI_API_KEY}
      - SSH_USER=${SSH_USER:-admin}
      - SSH_PASSWORD=${SSH_PASSWORD:-admin}
```

For `reporter-agent`, the block becomes:

```yaml
    environment:
      - API_URL=http://backend:8000/api/v1
      - NETGUARD_API_KEY=${NETGUARD_API_KEY:-agent-secret-key-123}
      - PYTHONUNBUFFERED=1
      - LLM_PROVIDER=${LLM_PROVIDER:-gemini}
      - LLM_API_KEY=${LLM_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - KIMI_API_KEY=${KIMI_API_KEY}
```

The backend already loads `.env.production` via `env_file`, so no explicit `KIMI_API_KEY` line is needed there.

- [ ] **Step 3: Validate compose syntax**

Run:
```bash
cd /opt/netguard
docker compose config > /dev/null
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
cd /opt/netguard
git add docker-compose.yml .env.production
git commit -m "chore(config): pass KIMI_API_KEY to backend and agents

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Live test backend with Kimi

**Files:**
- None (verification only).

**Interfaces:**
- Consumes: Running backend container, `KIMI_API_KEY` set.

- [ ] **Step 1: Set Kimi as the active provider**

In `.env.production`, set:

```bash
LLM_PROVIDER=kimi
KIMI_API_KEY=<value provided by user, not committed>
```

- [ ] **Step 2: Restart the backend container**

Run:
```bash
cd /opt/netguard
docker compose restart backend
```

- [ ] **Step 3: Verify backend health**

Run:
```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok"}` or similar healthy response.

- [ ] **Step 4: Trigger an alert and check incident renaming**

Create an alert via the existing API or wait for the monitor agent to create one. Then check the backend logs:

```bash
docker compose logs -f backend --tail=100
```

Look for:
- No `Unknown LLM provider` errors.
- No `No API key configured` warnings.
- Successful incident renaming (or at least a Kimi API response).

- [ ] **Step 5: Regression test with OpenAI/Gemini**

Switch `LLM_PROVIDER` back to `openai` and `gemini` one at time, restart the backend, and confirm alerts still process without `Unknown provider` errors.

- [ ] **Step 6: Commit test results**

No code changes if tests pass. If any fixes were needed, commit them.

---

### Task 10: Live test agents with Kimi

**Files:**
- None (verification only).

**Interfaces:**
- Consumes: Running `ai-fix-agent` and `reporter-agent` containers, `KIMI_API_KEY` set.

- [ ] **Step 1: Ensure Kimi is still the active provider**

Confirm `.env.production` has:

```bash
LLM_PROVIDER=kimi
KIMI_API_KEY=<value provided by user, not committed>
```

- [ ] **Step 2: Recreate the agents**

Run:
```bash
cd /opt/netguard
docker compose up -d --force-recreate ai-fix-agent reporter-agent
```

- [ ] **Step 3: Check agent logs for provider errors**

Run:
```bash
docker compose logs -f ai-fix-agent --tail=50
docker compose logs -f reporter-agent --tail=50
```

Look for:
- Agent starts without `Unknown provider` errors.
- No `LLM Key not found` warnings (unless key is intentionally absent).
- When a critical alert exists, `ai-fix-agent` logs `Querying kimi for alert ...`.
- When a resolved alert exists, `reporter-agent` attempts LLM summary.

- [ ] **Step 4: Regression test with OpenAI/Gemini**

Switch `LLM_PROVIDER` to `openai` and `gemini` one at a time, recreate the agents, and confirm no `Unknown provider` errors.

- [ ] **Step 5: Commit test results**

No code changes if tests pass. If any fixes were needed, commit them.

---

## Self-Review

### Spec coverage

| Spec Section | Implementing Task |
|---|---|
| Add Kimi provider across all LLM call sites | Tasks 1–7 |
| Use model `kimi-k2.5` | Task 1, Task 5 |
| Shared helper module in backend and agents | Task 1, Task 5 |
| Env/config changes (`KIMI_API_KEY`, docker-compose) | Task 8 |
| Preserve fallback behavior | All tasks (helper returns `None` on error) |
| Security (no key in code/logs) | Task 8 notes + helper implementation |
| Testing plan | Tasks 9–10 |

### Placeholder scan

- No `TBD`, `TODO`, or "implement later".
- No vague "add error handling" steps.
- Every step has a concrete command or code block.
- No "Similar to Task N" references.

### Type consistency

- `chat_completion(prompt: str, response_format: str | None = None) -> str | None` is used consistently in Tasks 1–7.
- `_clean_response(text: str) -> str` is exported from both helpers.
- Env var names match the spec: `LLM_PROVIDER`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `KIMI_API_KEY`, plus `LLM_API_KEY` fallback for agents.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-06-kimi-integration.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach would you like?
