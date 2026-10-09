import json
import os
import re
import urllib.request


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_CHAT_COMPLETIONS_URL = ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
OLLAMA_CHAT_COMPLETIONS_URL = "http://host.docker.internal:11434/v1/chat/completions"


def _storage_hint(db_type: str) -> str:
    if db_type == "mongodb":
        return "Available names in scope: router, collection, ObjectId, schemas (module containing the entity's standard schemas: e.g. schemas.FlowerCatalogRead, schemas.FlowerCatalogCreate, schemas.FlowerCatalogUpdate)."
    return "Available names in scope: router, db, SessionDep, model class (e.g. FlowerCatalog), schemas (module containing the entity's standard schemas: e.g. schemas.FlowerCatalogRead, schemas.FlowerCatalogCreate, schemas.FlowerCatalogUpdate)."


SYSTEM_PROMPT = """You are an expert Python developer.
Write clean, production-ready FastAPI route handlers.
Return only Python code with decorators and functions.
Do not include imports, markdown fences, or explanations.
If you need any custom Pydantic response models or schemas (like custom status or payload structures), you must define the Pydantic BaseModel class within your code block itself (e.g., class CatalogStatus(BaseModel): ...). Do not assume or reference a 'schemas' module or namespace for custom/new classes.
"""


async def generate_custom_endpoint(
    entity_name: str,
    method: str,
    path: str,
    description: str,
    db_type: str,
    entity_slug: str,
    provider: str = "ollama",
    model: str = "llama3.1",
    api_key: str = "",
    base_url: str | None = None,
) -> tuple[str, int]:
    user_prompt = (
        f"Entity: {entity_name}\n"
        f"HTTP method: {method}\n"
        f"Route path: {path}\n"
        f"Task: {description}\n"
        f"Storage mode: {db_type}\n"
        f"{_storage_hint(db_type)}\n"
        "Keep the function short and safe."
    )

    if provider != "ollama" and not api_key:
        api_key = _env_api_key_for(provider)
    if provider != "ollama" and not api_key:
        return _stub_endpoint(method, path, description, entity_slug), 0

    try:
        return _request_code(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            user_prompt=user_prompt,
        )
    except Exception as exc:
        print(f"Custom endpoint LLM failed, using scaffold: {exc}", flush=True)
        return _stub_endpoint(method, path, description, entity_slug), 0


def _request_code(
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None,
    user_prompt: str,
) -> tuple[str, int]:
    url, headers, payload = _build_request(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        user_prompt=user_prompt,
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        body = json.loads(response.read().decode("utf-8"))
    result_text = _extract_content(body)
    
    usage = body.get("usage", {})
    if "total_tokens" in usage:
        tokens = usage["total_tokens"]
    else:
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        
    return _strip_code_fence(result_text), tokens


def _build_request(
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None,
    user_prompt: str,
) -> tuple[str, dict[str, str], dict]:
    if provider == "claude":
        return (
            ANTHROPIC_MESSAGES_URL,
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            {
                "model": model,
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )

    url = OPENAI_CHAT_COMPLETIONS_URL
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "ollama":
        url = OLLAMA_CHAT_COMPLETIONS_URL
        headers["Authorization"] = "Bearer ollama"
    elif provider == "gemini":
        url = GEMINI_CHAT_COMPLETIONS_URL
    elif provider == "custom":
        url = _custom_chat_completions_url(base_url or "")

    return (
        url,
        headers,
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        },
    )


def _custom_chat_completions_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return f"{cleaned}/chat/completions"


def _env_api_key_for(provider: str) -> str:
    return {
        "openai": os.getenv("OPENAI_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", ""),
        "claude": os.getenv("ANTHROPIC_API_KEY", ""),
        "custom": os.getenv("CUSTOM_AI_API_KEY", ""),
    }.get(provider, "")


def _extract_content(body: dict) -> str:
    if "content" in body and isinstance(body["content"], list):
        return "".join(
            item.get("text", "") for item in body["content"] if isinstance(item, dict)
        )
    content = body["choices"][0]["message"]["content"]
    if isinstance(content, list):
        return "".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    return str(content)


def _strip_code_fence(content: str) -> str:
    content = content.strip()
    match = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    if content.startswith("```python"):
        content = content[9:].strip()
    elif content.startswith("```"):
        content = content[3:].strip()
    if content.endswith("```"):
        content = content[:-3].strip()
    return content


def _stub_endpoint(method: str, path: str, description: str, entity_slug: str) -> str:
    function_name = re.sub(r"[^a-z0-9]+", "_", f"{method}_{entity_slug}_{path}".lower())
    function_name = function_name.strip("_") or f"{entity_slug}_custom_endpoint"
    decorator = f'@router.{method.lower()}("{path}")'
    return (
        f"{decorator}\n"
        f"async def {function_name}():\n"
        f'    """{description}"""\n'
        f"    return {{\n"
        f'        "message": "Custom endpoint scaffold generated. Fill in business logic here.",\n'
        f'        "entity": "{entity_slug}",\n'
        f'        "method": "{method}",\n'
        f'        "path": "{path}",\n'
        f"    }}\n"
    )
