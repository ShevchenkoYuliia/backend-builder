import os
import re
import subprocess
import tempfile
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from schemas import DatabaseType, EntitySchema, FieldSchema, ProjectSchema, RelationSchema
from services.llm_service import generate_custom_endpoint


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    return value.strip("_").lower() or "item"


def pluralize(value: str) -> str:
    if value.endswith("s") and not value.endswith(("ss", "xs", "zs")):
        return value
    if value.endswith(("ss", "x", "z", "ch", "sh")):
        return f"{value}es"
    if value.endswith("y") and len(value) > 1 and value[-2] not in "aeiou":
        return f"{value[:-1]}ies"
    return f"{value}s"


def python_type(field_type: str) -> str:
    return {
        "string": "str",
        "text": "str",
        "integer": "int",
        "float": "float",
        "boolean": "bool",
        "datetime": "datetime",
    }[field_type]


def sqlalchemy_type(field_type: str) -> str:
    return {
        "string": "String(255)",
        "text": "Text",
        "integer": "Integer",
        "float": "Float",
        "boolean": "Boolean",
        "datetime": "DateTime",
    }[field_type]


def python_literal(value) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    return repr(value)


async def generate_project(
    project: ProjectSchema,
    ai_settings: dict | None = None,
) -> tuple[dict[str, str], bool]:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    project_slug = snake_case(project.name)
    entity_contexts = {
        entity.name: _init_entity_context(entity) for entity in project.entities
    }

    if project.db_type == DatabaseType.mongodb:
        _apply_mongo_relations(project, entity_contexts)
    else:
        _apply_sql_relations(project, entity_contexts)

    ordered_contexts = [
        await _finalize_entity_context(
            project,
            entity_contexts[entity.name],
            entity,
            ai_settings,
        )
        for entity in project.entities
    ]

    context = {
        "project": project,
        "project_slug": project_slug,
        "project_name": project.name,
        "db_is_mongo": project.db_type == DatabaseType.mongodb,
        "db_is_sql": project.db_type != DatabaseType.mongodb,
        "entity_contexts": ordered_contexts,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

    files: dict[str, str] = {
        "app/__init__.py": "",
        "app/models/__init__.py": "",
        "app/routers/__init__.py": "",
        "app/schemas/__init__.py": "",
        "app/main.py": _render(env, "app_main.py.j2", **context),
        "app/database.py": _render(env, "app_database.py.j2", **context),
        "requirements.txt": _render(env, "requirements.txt.j2", **context),
        "Dockerfile": _render(env, "Dockerfile.j2", **context),
        "docker-compose.yml": _render(env, "docker-compose.yml.j2", **context),
        ".env.example": _render(env, "env.example.j2", **context),
        "README.md": _render(env, "README.md.j2", **context),
        "tests/__init__.py": "",
        "tests/test_main.py": _render(env, "test_main.py.j2", **context),
    }

    if project.include_auth:
        files["app/security.py"] = _render(env, "app_security.py.j2", **context)
        files["app/routers/auth.py"] = _render(env, "app_auth.py.j2", **context)

    for entity_context in ordered_contexts:
        slug = entity_context["slug"]
        files[f"app/models/{slug}.py"] = _render(
            env,
            "app_model.py.j2",
            **context,
            entity=entity_context,
        )
        files[f"app/schemas/{slug}.py"] = _render(
            env,
            "app_schema.py.j2",
            **context,
            entity=entity_context,
        )
        files[f"app/routers/{slug}.py"] = _render(
            env,
            "app_router.py.j2",
            **context,
            entity=entity_context,
        )

    return _format_python_files(files)


def _init_entity_context(entity: EntitySchema) -> dict[str, object]:
    slug = snake_case(entity.name)
    collection_name = pluralize(slug)
    
    filtered_fields = [f for f in entity.fields if f.name.lower() != "id"]
    scalar_fields = [_build_scalar_field_context(field) for field in filtered_fields]

    return {
        "name": entity.name,
        "slug": slug,
        "collection_name": collection_name,
        "route_prefix": f"/{collection_name}",
        "table_name": collection_name,
        "has_datetime": any(item["uses_datetime"] for item in scalar_fields),
        "schema_base_lines": [item["schema_base_line"] for item in scalar_fields],
        "schema_update_lines": [item["schema_update_line"] for item in scalar_fields],
        "mongo_document_lines": [item["mongo_document_line"] for item in scalar_fields],
        "relationship_summary": [],
        "sql_model_pre_lines": [],
        "sql_model_column_lines": [item["sqlalchemy_line"] for item in scalar_fields],
        "sql_model_relationship_lines": [],
        "sql_router_serialize_lines": [item["serialize_line"] for item in scalar_fields],
        "sql_router_target_imports": [],
        "sql_collection_payload_fields": [],
        "sql_collection_relation_blocks_create": [],
        "sql_collection_relation_blocks_update": [],
        "seed_assignments": [item["seed_assignment"] for item in scalar_fields],
    }


def _build_scalar_field_context(field: FieldSchema) -> dict[str, object]:
    py_type = python_type(field.type.value)
    default_literal = python_literal(field.default)
    optional_annotation = f"{py_type} | None"
    schema_base_line = f"    {field.name}: {py_type}"
    if field.default is not None:
        schema_base_line += f" = {default_literal}"
    elif not field.required:
        schema_base_line += " | None = None"

    schema_update_line = f"    {field.name}: {optional_annotation} = None"
    sqlalchemy_line = (
        f"    {field.name} = Column("
        f"{sqlalchemy_type(field.type.value)}, "
        f"nullable={not field.required}, "
        f"unique={field.unique}"
    )
    if field.default is not None:
        sqlalchemy_line += f", default={default_literal}"
    sqlalchemy_line += ")"

    seed_literal = '""'
    if field.type.value == "string":
        seed_literal = f'"Sample {field.name}"'
    elif field.type.value == "text":
        seed_literal = f'"Sample text for {field.name}"'
    elif field.type.value == "integer":
        seed_literal = "1"
    elif field.type.value == "float":
        seed_literal = "1.0"
    elif field.type.value == "boolean":
        seed_literal = "True"
    elif field.type.value == "datetime":
        seed_literal = "datetime.utcnow()"

    return {
        "uses_datetime": field.type.value == "datetime",
        "schema_base_line": schema_base_line,
        "schema_update_line": schema_update_line,
        "sqlalchemy_line": sqlalchemy_line,
        "mongo_document_line": f'        "{field.name}": payload.{field.name},',
        "serialize_line": f'        "{field.name}": item.{field.name},',
        "seed_assignment": f"{field.name}={seed_literal}",
    }


def _apply_mongo_relations(
    project: ProjectSchema,
    entity_contexts: dict[str, dict[str, object]],
) -> None:
    for entity in project.entities:
        context = entity_contexts[entity.name]
        for relation in entity.relations:
            relation_slug = snake_case(relation.name)
            if relation.relation_type.value in {"one_to_many", "many_to_many"}:
                field_name = f"{relation_slug}_ids"
                context["schema_base_lines"].append(
                    '    ' + f"{field_name}: list[str] = Field(default_factory=list)"
                )
                context["schema_update_lines"].append(
                    '    ' + f"{field_name}: list[str] | None = None"
                )
                context["mongo_document_lines"].append(
                    f'        "{field_name}": payload.{field_name},'
                )
                context["relationship_summary"].append(
                    f"- {relation.name}: {relation.relation_type.value} -> "
                    f"{relation.target_entity} (stored as a list of ids)"
                )
            else:
                field_name = f"{relation_slug}_id"
                context["schema_base_lines"].append(f"    {field_name}: str | None = None")
                context["schema_update_lines"].append(f"    {field_name}: str | None = None")
                context["mongo_document_lines"].append(
                    f'        "{field_name}": payload.{field_name},'
                )
                context["relationship_summary"].append(
                    f"- {relation.name}: {relation.relation_type.value} -> "
                    f"{relation.target_entity} (stored as {field_name})"
                )


def _apply_sql_relations(
    project: ProjectSchema,
    entity_contexts: dict[str, dict[str, object]],
) -> None:
    for entity in project.entities:
        owner_context = entity_contexts[entity.name]
        for relation in entity.relations:
            target_context = entity_contexts[relation.target_entity]
            relation_slug = snake_case(relation.name)

            if relation.relation_type.value == "many_to_one":
                fk_name = f"{relation_slug}_id"
                _add_sql_singular_relation(
                    owner_context,
                    target_context,
                    relation,
                    fk_name,
                    unique=False,
                    uselist=False,
                )
                continue

            if relation.relation_type.value == "one_to_one":
                fk_name = f"{relation_slug}_id"
                _add_sql_singular_relation(
                    owner_context,
                    target_context,
                    relation,
                    fk_name,
                    unique=True,
                    uselist=False,
                )
                continue

            if relation.relation_type.value == "many_to_many":
                association_name = (
                    f"{owner_context['slug']}_{relation_slug}_{target_context['slug']}_link"
                )
                payload_name = f"{relation_slug}_ids"
                owner_context["sql_model_pre_lines"].append(
                    _build_association_table_block(
                        association_name,
                        owner_context,
                        target_context,
                    )
                )
                owner_context["sql_model_relationship_lines"].append(
                    f'    {relation_slug} = relationship("{target_context["name"]}", '
                    f"secondary={association_name})"
                )
                _add_sql_collection_payload_field(owner_context, payload_name, relation_slug)
                _add_sql_target_import(owner_context, target_context)
                _add_sql_collection_block(
                    owner_context,
                    relation,
                    target_context,
                    relation_slug,
                    payload_name,
                )
                owner_context["relationship_summary"].append(
                    f"- {relation.name}: many_to_many -> {target_context['name']} "
                    f"(association table `{association_name}`)"
                )
                continue

            if relation.relation_type.value == "one_to_many":
                payload_name = f"{relation_slug}_ids"
                child_fk_name = f"{owner_context['slug']}_{relation_slug}_id"
                owner_context["sql_model_relationship_lines"].append(
                    f'    {relation_slug} = relationship("{target_context["name"]}", '
                    f'foreign_keys="[{target_context["name"]}.{child_fk_name}]")'
                )
                target_context["sql_model_column_lines"].append(
                    f'    {child_fk_name} = Column('
                    f'Integer, ForeignKey("{owner_context["table_name"]}.id"), nullable=True)'
                )
                _add_sql_singular_payload_field(target_context, child_fk_name)
                target_context["seed_assignments"].append(f"{child_fk_name}=1")
                _add_sql_collection_payload_field(owner_context, payload_name, relation_slug)
                _add_sql_target_import(owner_context, target_context)
                _add_sql_collection_block(
                    owner_context,
                    relation,
                    target_context,
                    relation_slug,
                    payload_name,
                )
                owner_context["relationship_summary"].append(
                    f"- {relation.name}: one_to_many -> {target_context['name']} "
                    f"(child ForeignKey `{child_fk_name}`)"
                )


def _add_sql_singular_relation(
    owner_context: dict[str, object],
    target_context: dict[str, object],
    relation: RelationSchema,
    fk_name: str,
    *,
    unique: bool,
    uselist: bool,
) -> None:
    owner_context["sql_model_column_lines"].append(
        f'    {fk_name} = Column('
        f'Integer, ForeignKey("{target_context["table_name"]}.id"), '
        f"nullable=True, unique={unique})"
    )
    relationship_parts = [f'"{target_context["name"]}"']
    relationship_parts.append(f'foreign_keys="[{owner_context["name"]}.{fk_name}]"')
    if not uselist and unique:
        relationship_parts.append("uselist=False")
    owner_context["sql_model_relationship_lines"].append(
        f'    {snake_case(relation.name)} = relationship({", ".join(relationship_parts)})'
    )
    _add_sql_singular_payload_field(owner_context, fk_name)
    owner_context["relationship_summary"].append(
        f"- {relation.name}: {relation.relation_type.value} -> {target_context['name']} "
        f"(ForeignKey `{fk_name}`)"
    )
    owner_context["seed_assignments"].append(f"{fk_name}=1")


def _add_sql_singular_payload_field(context: dict[str, object], field_name: str) -> None:
    if f"    {field_name}: int | None = None" not in context["schema_base_lines"]:
        context["schema_base_lines"].append(f"    {field_name}: int | None = None")
    if f"    {field_name}: int | None = None" not in context["schema_update_lines"]:
        context["schema_update_lines"].append(f"    {field_name}: int | None = None")
    serialize_line = f'        "{field_name}": item.{field_name},'
    if serialize_line not in context["sql_router_serialize_lines"]:
        context["sql_router_serialize_lines"].append(serialize_line)


def _add_sql_collection_payload_field(
    context: dict[str, object],
    payload_name: str,
    relation_attribute: str,
) -> None:
    base_line = f"    {payload_name}: list[int] = Field(default_factory=list)"
    update_line = f"    {payload_name}: list[int] | None = None"
    serialize_line = (
        f'        "{payload_name}": [related.id for related in item.{relation_attribute}],'
    )

    if base_line not in context["schema_base_lines"]:
        context["schema_base_lines"].append(base_line)
    if update_line not in context["schema_update_lines"]:
        context["schema_update_lines"].append(update_line)
    if serialize_line not in context["sql_router_serialize_lines"]:
        context["sql_router_serialize_lines"].append(serialize_line)
    if payload_name not in context["sql_collection_payload_fields"]:
        context["sql_collection_payload_fields"].append(payload_name)


def _add_sql_target_import(
    owner_context: dict[str, object],
    target_context: dict[str, object],
) -> None:
    pair = (target_context["slug"], target_context["name"])
    if pair not in owner_context["sql_router_target_imports"]:
        owner_context["sql_router_target_imports"].append(pair)


def _add_sql_collection_block(
    owner_context: dict[str, object],
    relation: RelationSchema,
    target_context: dict[str, object],
    relation_attribute: str,
    payload_name: str,
) -> None:
    label = f"{relation.method if hasattr(relation, 'method') else relation.relation_type.value}"
    del label
    block = _build_sql_collection_assignment_block(
        target_context["name"],
        payload_name,
        relation_attribute,
        relation.name,
        conditional=False,
    )
    update_block = _build_sql_collection_assignment_block(
        target_context["name"],
        payload_name,
        relation_attribute,
        relation.name,
        conditional=True,
    )
    owner_context["sql_collection_relation_blocks_create"].append(block)
    owner_context["sql_collection_relation_blocks_update"].append(update_block)


def _build_association_table_block(
    association_name: str,
    owner_context: dict[str, object],
    target_context: dict[str, object],
) -> str:
    return (
        f"{association_name} = Table(\n"
        f'    "{association_name}",\n'
        "    Base.metadata,\n"
        f'    Column("{owner_context["slug"]}_id", Integer, '
        f'ForeignKey("{owner_context["table_name"]}.id"), primary_key=True),\n'
        f'    Column("{target_context["slug"]}_id", Integer, '
        f'ForeignKey("{target_context["table_name"]}.id"), primary_key=True),\n'
        ")\n"
    )


def _build_sql_collection_assignment_block(
    target_name: str,
    payload_name: str,
    relation_attribute: str,
    relation_label: str,
    *,
    conditional: bool,
) -> str:
    prefix = f"if payload.{payload_name} is not None:\n" if conditional else ""
    inner_indent = "    " if conditional else ""
    return (
        f"{prefix}{inner_indent}requested_ids = list(dict.fromkeys(payload.{payload_name}))\n"
        f"{inner_indent}related_items = (\n"
        f"{inner_indent}    db.query({target_name}).filter({target_name}.id.in_(requested_ids)).all()\n"
        f"{inner_indent}    if requested_ids\n"
        f"{inner_indent}    else []\n"
        f"{inner_indent})\n"
        f"{inner_indent}if len(related_items) != len(requested_ids):\n"
        f"{inner_indent}    raise HTTPException(\n"
        f"{inner_indent}        status_code=422,\n"
        f'{inner_indent}        detail="Some ids for relation \'{relation_label}\' do not exist.",\n'
        f"{inner_indent}    )\n"
        f"{inner_indent}item.{relation_attribute} = related_items"
    )


async def _finalize_entity_context(
    project: ProjectSchema,
    context: dict[str, object],
    entity: EntitySchema,
    ai_settings: dict | None = None,
) -> dict[str, object]:
    finalized = dict(context)
    finalized["custom_endpoints_code"] = await _build_custom_endpoints(
        project,
        entity,
        context["slug"],
        ai_settings,
    )
    return finalized


async def _build_custom_endpoints(
    project: ProjectSchema,
    entity: EntitySchema,
    slug: str,
    ai_settings: dict | None = None,
) -> str:
    snippets: list[str] = []
    for endpoint in entity.custom_endpoints:
        if endpoint.code:
            snippets.append(endpoint.code.rstrip())
        else:
            code, _ = await generate_custom_endpoint(
                entity_name=entity.name,
                method=endpoint.method,
                path=endpoint.path,
                description=endpoint.description,
                db_type=project.db_type.value,
                entity_slug=slug,
                provider=(ai_settings or {}).get("provider", "ollama"),
                model=(ai_settings or {}).get("model", "llama3.1"),
                api_key=(ai_settings or {}).get("api_key", ""),
                base_url=(ai_settings or {}).get("base_url"),
            )
            snippets.append(code.rstrip())
    return "\n\n".join(snippets)


def _render(env: Environment, template_name: str, **context) -> str:
    template = env.get_template(template_name)
    return template.render(**context).rstrip() + "\n"


def _format_python_files(files: dict[str, str]) -> tuple[dict[str, str], bool]:
    formatted: dict[str, str] = {}
    compile_success = True
    for path, content in files.items():
        if not path.endswith(".py"):
            formatted[path] = content
            continue

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            try:
                subprocess.run(["python", "-m", "py_compile", temp_path], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                compile_success = False

            subprocess.run(
                ["black", "--quiet", temp_path],
                check=False,
                timeout=10,
            )
            with open(temp_path, encoding="utf-8") as handle:
                formatted[path] = handle.read()
            os.unlink(temp_path)
        except Exception:
            formatted[path] = content
            compile_success = False
    return formatted, compile_success
