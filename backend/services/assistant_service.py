import asyncio
import json
import os
import re
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from typing import Awaitable, Callable

from fastapi import HTTPException, status

from schemas import (
    AIProvider,
    AssistantDraftResponse,
    CustomEndpointSchema,
    EntitySchema,
    FieldSchema,
    ProjectSchema,
    RelationSchema,
)


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_CHAT_COMPLETIONS_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
)
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
OLLAMA_CHAT_COMPLETIONS_URL = "http://host.docker.internal:11434/v1/chat/completions"
IDENTIFIER_CLEANUP_RE = re.compile(r"[^A-Za-z0-9_]+")
PATH_CLEANUP_RE = re.compile(r"[^A-Za-z0-9_/{}-]+")

OVERVIEW_SYSTEM_PROMPT = """You are a senior backend product architect.
Turn the user's product idea into a realistic backend project plan.
This is step 1 of a multi-step generation pipeline.
Return only valid JSON.
Generate exactly as many entities as the idea genuinely requires — no more, no less.
For a simple idea 1-3 entities may be enough; only add more when the domain truly demands it.
Naming rules (STRICT — never violate):
  - Entity names MUST use snake_case or PascalCase: e.g. booking_reserve or BookingReserve.
  - Entity names MUST NOT contain spaces. "booking reserve" is INVALID.
  - Entity names must start with a letter and contain only letters, digits, or underscores.
  - The "project_description" field MUST contain a short, high-level summary of the backend system in exactly one sentence. Do not write a paragraph, just a single concise sentence.
Do not generate fields or relations in this step.
"""

ENTITY_SYSTEM_PROMPT = """You are a senior backend product architect.
This is step 2 of a multi-step generation pipeline.
Generate one entity definition for a backend builder project.
Return only valid JSON.
Focus on practical fields and a few useful custom endpoints.
Naming rules (STRICT — never violate):
  - Field names MUST use snake_case: e.g. first_name, booking_date. NO spaces allowed.
  - Endpoint paths MUST use snake_case segments: e.g. /booking_reserve/{id}/confirm. NO spaces in paths.
  - All identifiers (names, paths) must start with a letter and contain only letters, digits, underscores, or slashes/braces for paths.
"""

RELATIONS_SYSTEM_PROMPT = """You are a senior backend product architect.
This is step 3 of a multi-step generation pipeline.
Generate realistic relationships between existing entities.
Return only valid JSON.
Important constraints:
- Use only the provided entity names exactly as given.
- Do not create self-references unless absolutely necessary.
- The relation graph must stay acyclic.
- Prefer one directional relationship per logical pair to avoid cycles.
Naming rules (STRICT — never violate):
  - Relation names MUST use snake_case: e.g. has_bookings, belongs_to_user. NO spaces allowed.
  - Relation names must start with a letter and contain only letters, digits, or underscores.
"""


async def build_project_from_prompt(
    *,
    prompt: str,
    api_key: str,
    model: str,
    provider: str = "openai",
    base_url: str | None = None,
    progress_callback: Callable[[str], Awaitable[None] | None] | None = None,
) -> tuple[str, ProjectSchema, int, float, int]:
    total_tokens = 0
    failed_attempts = 0
    llm_start = asyncio.get_event_loop().time()

    try:
        overview, tokens_used = await _request_json_stage(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            system_prompt=OVERVIEW_SYSTEM_PROMPT,
            user_prompt=_build_overview_prompt(prompt),
            response_schema=_overview_response_schema(),
            timeout=_timeout_for(provider, "overview"),
            stage_name="project overview",
        )
    except Exception:
        failed_attempts += 1
        raise
    total_tokens += tokens_used
    await _notify_progress(
        progress_callback,
        (
            f"Скелет проєкту створено. Знайдено сутностей: "
            f"{len(overview['entities'])}. Переходимо до деталей сутностей."
        ),
    )

    entity_plan = overview["entities"]
    entity_names = [item["name"] for item in entity_plan]
    async def build_entity_definition(index: int, item: dict) -> tuple[int, dict, int]:
        try:
            definition, tokens_used = await _request_json_stage(
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
                system_prompt=ENTITY_SYSTEM_PROMPT,
                user_prompt=_build_entity_prompt(
                    prompt=prompt,
                    overview=overview,
                    entity_plan=item,
                    all_entity_names=entity_names,
                ),
                response_schema=_entity_response_schema(),
                timeout=_timeout_for(provider, "entity"),
                stage_name=f"entity {item['name']}",
            )
        except Exception:
            raise
        definition["name"] = item["name"]
        await _notify_progress(
            progress_callback,
            (
                f"Сутність {item['name']} створена "
                f"({index}/{len(entity_plan)}). Переходимо до наступного кроку."
            ),
        )
        return index, definition, tokens_used

    entity_results = await asyncio.gather(
        *[
            build_entity_definition(index, item)
            for index, item in enumerate(entity_plan, start=1)
        ],
        return_exceptions=True,
    )
    entity_definitions: list[dict] = []
    entity_errors = [result for result in entity_results if isinstance(result, Exception)]
    if entity_errors:
        failed_attempts += len(entity_errors)
        raise entity_errors[0]
    for result in entity_results:
        _, definition, tokens_used = result
        total_tokens += tokens_used
        entity_definitions.append(definition)

    await _notify_progress(
        progress_callback,
        "Всі сутності готові. Генеруємо зв'язки між ними.",
    )

    try:
        relations_payload, tokens_used = await _request_json_stage(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            system_prompt=RELATIONS_SYSTEM_PROMPT,
            user_prompt=_build_relations_prompt(
                prompt=prompt,
                overview=overview,
                entity_definitions=entity_definitions,
            ),
            response_schema=_relations_response_schema(),
            timeout=_timeout_for(provider, "relations"),
            stage_name="project relations",
        )
    except Exception:
        failed_attempts += 1
        raise
    total_tokens += tokens_used

    project, skipped_cycles = _assemble_project(
        overview=overview,
        entity_plan=entity_plan,
        entity_definitions=entity_definitions,
        relations_payload=relations_payload,
    )
    if skipped_cycles:
        await _notify_progress(
            progress_callback,
            (
                f"Виявлено та пропущено циклічні зв'язки: {skipped_cycles}. "
                "Будуємо фінальний результат."
            ),
        )
    else:
        await _notify_progress(
            progress_callback,
            "Зв'язки створено. Будуємо фінальний результат.",
        )

    assistant_message = _final_assistant_message(overview, project)
    llm_time = round(asyncio.get_event_loop().time() - llm_start, 2)
    return assistant_message, project, total_tokens, llm_time, failed_attempts


def build_draft_response(
    *,
    chat_id: str,
    prompt: str,
    assistant_message: str,
    project: ProjectSchema,
    provider: AIProvider,
    model: str,
    created_at: datetime,
    tokens_used: int,
    llm_time: float | None = None,
) -> AssistantDraftResponse:
    return AssistantDraftResponse(
        chat_id=chat_id,
        prompt=prompt,
        assistant_message=assistant_message,
        project=project,
        provider=provider,
        model=model,
        created_at=created_at.astimezone(UTC).replace(tzinfo=None)
        if created_at.tzinfo
        else created_at,
        tokens_used=tokens_used,
        llm_time=llm_time,
    )


async def _request_json_stage(
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None,
    system_prompt: str,
    user_prompt: str,
    response_schema: dict,
    timeout: int,
    stage_name: str,
) -> tuple[dict, int]:
    body = await asyncio.to_thread(
        _perform_llm_request,
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema=response_schema,
        timeout=timeout,
        stage_name=stage_name,
    )

    try:
        content = _extract_content(body)
        parsed = json.loads(content)
    except Exception as exc:
        print(f"\nPARSE ERROR during {stage_name}", flush=True)
        print(f"Exception: {exc}", flush=True)
        if "content" in locals():
            print(f"Raw content was:\n{content}", flush=True)
        print("", flush=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider returned invalid JSON during {stage_name}.",
        ) from exc

    return parsed, _extract_token_usage(body)


def _perform_llm_request(
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None,
    system_prompt: str,
    user_prompt: str,
    response_schema: dict,
    timeout: int,
    stage_name: str,
) -> dict:
    url, headers, payload = _build_provider_request(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema=response_schema,
        stage_name=stage_name,
    )

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            print(f"RAW LLM RESPONSE [{stage_name}]")
            print(json.dumps(body, indent=2, ensure_ascii=False))
            return body
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider error during {stage_name}: {detail or exc.reason}",
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Timed out during {stage_name} after {timeout} seconds.",
        ) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", "")
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Timed out during {stage_name} after {timeout} seconds.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the AI provider. Check internet access or API key.",
        ) from exc


def _build_provider_request(
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None,
    system_prompt: str,
    user_prompt: str,
    response_schema: dict,
    stage_name: str,
) -> tuple[str, dict[str, str], dict]:
    if provider == "claude":
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": _json_schema_prompt(user_prompt, response_schema),
                }
            ],
        }
        return (
            ANTHROPIC_MESSAGES_URL,
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload,
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
        if not base_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom AI provider requires a base URL.",
            )
        url = _custom_chat_completions_url(base_url)

    payload_user_prompt = user_prompt
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": _schema_name_for_stage(stage_name),
            "schema": response_schema,
            "strict": True,
        },
    }
    if provider in {"gemini", "custom"}:
        payload_user_prompt = _json_schema_prompt(user_prompt, response_schema)
        response_format = {"type": "json_object"}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload_user_prompt},
        ],
        "response_format": response_format,
    }
    return url, headers, payload


def _custom_chat_completions_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return f"{cleaned}/chat/completions"


def _json_schema_prompt(user_prompt: str, response_schema: dict) -> str:
    return (
        f"{user_prompt}\n\n"
        "Return JSON only. The response must match this JSON Schema exactly:\n"
        f"{json.dumps(response_schema, ensure_ascii=False)}"
    )


def _extract_content(body: dict) -> str:
    if "content" in body and isinstance(body["content"], list):
        content = "".join(
            item.get("text", "") for item in body["content"] if isinstance(item, dict)
        )
    else:
        content = body["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    content = content.strip()
    
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
        
    if content.startswith("```json"):
        content = content[7:].strip()
    elif content.startswith("```"):
        content = content[3:].strip()
    if content.endswith("```"):
        content = content[:-3].strip()
    return content


def _extract_token_usage(body: dict) -> int:
    usage = body.get("usage", {})
    if "total_tokens" in usage:
        return usage["total_tokens"]
    return usage.get("input_tokens", 0) + usage.get("output_tokens", 0)


def _build_overview_prompt(prompt: str) -> str:
    return (
        "Build a backend project skeleton for the product request below.\n"
        "Return JSON only.\n"
        "Choose a suitable database from postgresql, mysql, mongodb.\n"
        "Generate only as many entities as the user's idea actually needs.\n"
        "A simple idea may only need 1-3 entities; a complex product may need more.\n"
        "Do NOT pad the list with unnecessary entities just to reach a certain count.\n"
        "CRITICAL RULES:\n"
        "  - The 'project_description' field MUST contain a short, high-level summary of the backend system in exactly one sentence. Do not write a paragraph, just a single concise sentence.\n"
        "  - Entity names MUST be snake_case or PascalCase with NO spaces.\n"
        "    VALID: booking_reserve, BookingReserve, user_profile\n"
        "    INVALID: 'booking reserve', 'user profile' (spaces are forbidden).\n"
        "  - Entity names must start with a letter and use only letters, numbers, or underscores.\n\n"
        f"User request:\n{prompt}"
    )


def _build_entity_prompt(
    *,
    prompt: str,
    overview: dict,
    entity_plan: dict,
    all_entity_names: list[str],
) -> str:
    return (
        "Generate a detailed entity definition for the backend builder.\n"
        "Return JSON only.\n"
        "Create 5-10 practical fields.\n"
        "DO NOT create an 'id' field. It is automatically managed by the system as the primary key.\n"
        "Use defaults only when they are simple JSON values.\n"
        "Add 0-3 custom endpoints only if they support meaningful business actions.\n"
        "Do not add relations in this step.\n"
        "CRITICAL NAMING RULES (violations will break the system):\n"
        "  - Field names MUST be snake_case with NO spaces: e.g. first_name, created_at.\n"
        "  - Endpoint paths MUST be snake_case with NO spaces: e.g. /booking_reserve/{id}/confirm.\n"
        "  - INVALID examples: 'first name', 'booking reserve' — spaces are strictly forbidden.\n\n"
        f"Original user request:\n{prompt}\n\n"
        f"Project name: {overview['project_name']}\n"
        f"Project description: {overview['project_description']}\n"
        f"Database: {overview['db_type']}\n"
        f"All entity names: {', '.join(all_entity_names)}\n"
        f"Current entity: {entity_plan['name']}\n"
        f"Current entity purpose: {entity_plan['purpose']}"
    )


def _build_relations_prompt(
    *,
    prompt: str,
    overview: dict,
    entity_definitions: list[dict],
) -> str:
    entity_summary = []
    for item in entity_definitions:
        field_names = [field["name"] for field in item.get("fields", [])]
        endpoint_signatures = [
            f"{endpoint['method']} {endpoint['path']}"
            for endpoint in item.get("custom_endpoints", [])
        ]
        entity_summary.append(
            {
                "name": item["name"],
                "fields": field_names,
                "custom_endpoints": endpoint_signatures,
            }
        )

    return (
        "Generate relationships for the backend builder project.\n"
        "Return JSON only.\n"
        "Use only the listed entities.\n"
        "Keep the relation graph acyclic because circular relation graphs are rejected by validation.\n"
        "Only create forward relations from earlier entities in the list to later entities in the list.\n"
        "Prefer parent-to-child direction and avoid mirrored reverse relations.\n\n"
        f"Original user request:\n{prompt}\n\n"
        f"Project name: {overview['project_name']}\n"
        f"Project description: {overview['project_description']}\n"
        f"Database: {overview['db_type']}\n"
        f"Entity summaries:\n{json.dumps(entity_summary, ensure_ascii=False)}"
    )


def _assemble_project(
    *,
    overview: dict,
    entity_plan: list[dict],
    entity_definitions: list[dict],
    relations_payload: dict,
) -> tuple[ProjectSchema, int]:
    relation_buckets: dict[str, list[RelationSchema]] = defaultdict(list)
    seen_relations: set[tuple[str, str, str, str]] = set()
    known_entities = {item["name"] for item in entity_plan}
    adjacency: dict[str, set[str]] = defaultdict(set)
    skipped_cycles = 0

    for relation in relations_payload.get("relations", []):
        source_entity = relation["source_entity"]
        target_entity = relation["target_entity"]
        if source_entity not in known_entities or target_entity not in known_entities:
            continue
        if source_entity == target_entity:
            continue

        signature = (
            source_entity,
            relation["name"],
            target_entity,
            relation["relation_type"],
        )
        if signature in seen_relations:
            continue
        if _would_create_cycle(adjacency, source_entity, target_entity):
            skipped_cycles += 1
            continue

        seen_relations.add(signature)
        adjacency[source_entity].add(target_entity)
        relation_buckets[source_entity].append(
            RelationSchema(
                name=relation["name"],
                target_entity=target_entity,
                relation_type=relation["relation_type"],
            )
        )

    definitions_by_name = {item["name"]: item for item in entity_definitions}
    entities: list[EntitySchema] = []
    for planned_entity in entity_plan:
        original_name = planned_entity["name"]
        name = _normalize_identifier(original_name, fallback="entity")
        definition = definitions_by_name.get(
            original_name,
            {"name": original_name, "fields": [], "custom_endpoints": []},
        )
        fields = [
            FieldSchema(**_sanitize_field_payload(field))
            for field in definition.get("fields", [])
        ]
        endpoints = [
            CustomEndpointSchema(**_sanitize_endpoint_payload(endpoint))
            for endpoint in definition.get("custom_endpoints", [])
        ]
        entities.append(
            EntitySchema(
                name=name,
                fields=fields,
                relations=relation_buckets.get(name, []),
                custom_endpoints=endpoints,
            )
        )

    return (
        ProjectSchema(
            name=overview["project_name"],
            description=overview["project_description"],
            db_type=overview["db_type"],
            entities=entities,
        ),
        skipped_cycles,
    )


def _normalize_identifier(value: object, fallback: str) -> str:
    cleaned = IDENTIFIER_CLEANUP_RE.sub("_", str(value or "").strip())
    cleaned = cleaned.strip("_").lstrip("0123456789_")
    return cleaned or fallback


def _sanitize_field_payload(field: dict) -> dict:
    sanitized = dict(field)
    sanitized["name"] = _normalize_identifier(sanitized.get("name"), fallback="field")
    return sanitized


def _sanitize_endpoint_payload(endpoint: dict) -> dict:
    sanitized = dict(endpoint)
    path = PATH_CLEANUP_RE.sub("_", str(sanitized.get("path") or "").strip())
    while "//" in path:
        path = path.replace("//", "/")
    sanitized["path"] = path.strip() or "/custom_action"
    sanitized["description"] = str(sanitized.get("description") or "")
    return sanitized


def _final_assistant_message(overview: dict, project: ProjectSchema) -> str:
    message = (overview.get("assistant_message") or "").strip()
    if message:
        return message

    return (
        f"Prepared a draft for {project.name} with "
        f"{len(project.entities)} entities and "
        f"{sum(len(entity.relations) for entity in project.entities)} relations."
    )


async def _notify_progress(
    callback: Callable[[str], Awaitable[None] | None] | None,
    message: str,
) -> None:
    if callback is None:
        return
    result = callback(message)
    if asyncio.iscoroutine(result):
        await result


def _would_create_cycle(
    adjacency: dict[str, set[str]],
    source_entity: str,
    target_entity: str,
) -> bool:
    stack = [target_entity]
    visited: set[str] = set()

    while stack:
        current = stack.pop()
        if current == source_entity:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(adjacency.get(current, ()))

    return False


def _schema_name_for_stage(stage_name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in stage_name.lower())
    return cleaned.strip("_") or "backend_builder_step"


def _timeout_for(provider: str, stage: str) -> int:
    env_key = f"AI_DRAFT_{stage.upper()}_TIMEOUT_SEC"
    if raw := os.getenv(env_key):
        try:
            return max(15, int(raw))
        except ValueError:
            pass

    defaults = {
        "openai": {
            "overview": 90,
            "entity": 75,
            "relations": 90,
        },
        "ollama": {
            "overview": 600,
            "entity": 600,
            "relations": 600,
        },
    }
    return defaults.get(provider, defaults["openai"]).get(stage, 90)


def _overview_response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "assistant_message": {"type": "string"},
            "project_name": {"type": "string"},
            "project_description": {"type": "string"},
            "db_type": {
                "type": "string",
                "enum": ["postgresql", "mysql", "mongodb"],
            },
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "purpose": {"type": "string"},
                    },
                    "required": ["name", "purpose"],
                    "additionalProperties": False,
                },
                "minItems": 1,
            },
        },
        "required": [
            "assistant_message",
            "project_name",
            "project_description",
            "db_type",
            "entities",
        ],
        "additionalProperties": False,
    }


def _entity_response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": [
                                "string",
                                "integer",
                                "float",
                                "boolean",
                                "datetime",
                                "text",
                            ],
                        },
                        "required": {"type": "boolean"},
                        "unique": {"type": "boolean"},
                        "default": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "number"},
                                {"type": "integer"},
                                {"type": "boolean"},
                                {"type": "null"},
                            ]
                        },
                        "description": {"type": "string"},
                    },
                    "required": [
                        "name",
                        "type",
                        "required",
                        "unique",
                        "default",
                        "description",
                    ],
                    "additionalProperties": False,
                },
            },
            "custom_endpoints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        },
                        "path": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["method", "path", "description"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["name", "fields", "custom_endpoints"],
        "additionalProperties": False,
    }


def _relations_response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_entity": {"type": "string"},
                        "name": {"type": "string"},
                        "target_entity": {"type": "string"},
                        "relation_type": {
                            "type": "string",
                            "enum": [
                                "one_to_many",
                                "many_to_many",
                                "many_to_one",
                                "one_to_one",
                            ],
                        },
                    },
                    "required": [
                        "source_entity",
                        "name",
                        "target_entity",
                        "relation_type",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["relations"],
        "additionalProperties": False,
    }
