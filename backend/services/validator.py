import re
from collections import defaultdict

from schemas import FieldSchema, FieldType, ProjectSchema, ValidationIssue, ValidationReport


IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def build_validation_report(project: ProjectSchema) -> ValidationReport:
    issues: list[ValidationIssue] = []
    entity_name_to_index: dict[str, int] = {}
    relation_graph: dict[str, list[str]] = defaultdict(list)

    if not project.entities:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="project.empty",
                message="Create at least one entity to generate a meaningful backend.",
                location=["entities"],
            )
        )

    for entity_index, entity in enumerate(project.entities):
        entity_location = ["entities", str(entity_index)]
        _check_identifier(
            issues,
            entity.name,
            "entity.name",
            "Entity names must start with a letter and use only letters, numbers, or underscores.",
            entity_location + ["name"],
        )

        if entity.name in entity_name_to_index:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="entity.duplicate",
                    message=f"Entity '{entity.name}' is duplicated.",
                    location=entity_location + ["name"],
                )
            )
        else:
            entity_name_to_index[entity.name] = entity_index

        if not entity.fields:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="entity.no_fields",
                    message=f"Entity '{entity.name}' has no fields yet.",
                    location=entity_location + ["fields"],
                )
            )

        _check_fields(issues, entity.fields, entity.name, entity_location)
        _check_relations(issues, entity, entity_location)
        _check_custom_endpoints(issues, entity, entity_location)

        for relation in entity.relations:
            relation_graph[entity.name].append(relation.target_entity)

    _check_relation_targets(issues, project, entity_name_to_index)
    _check_cycles(issues, relation_graph)

    return ValidationReport(
        valid=not any(issue.severity == "error" for issue in issues),
        issues=issues,
    )


def _check_fields(
    issues: list[ValidationIssue],
    fields: list[FieldSchema],
    entity_name: str,
    entity_location: list[str],
) -> None:
    seen_names: set[str] = set()
    for field_index, field in enumerate(fields):
        field_location = entity_location + ["fields", str(field_index)]
        _check_identifier(
            issues,
            field.name,
            "field.name",
            "Field names must start with a letter and use only letters, numbers, or underscores.",
            field_location + ["name"],
        )

        if field.name in seen_names:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="field.duplicate",
                    message=f"Entity '{entity_name}' has duplicate field '{field.name}'.",
                    location=field_location + ["name"],
                )
            )
        else:
            seen_names.add(field.name)

        if field.name.lower() == "id":
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="field.reserved_name",
                    message="Field 'id' is automatically managed by the system as the primary key. Your custom 'id' field will be ignored.",
                    location=field_location + ["name"],
                )
            )

        default_issue = _validate_default_value(field)
        if default_issue:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="field.default_type",
                    message=(
                        f"Field '{entity_name}.{field.name}' has a default value "
                        f"that does not match type '{field.type.value}'."
                    ),
                    location=field_location + ["default"],
                )
            )


def _check_relations(
    issues: list[ValidationIssue],
    entity,
    entity_location: list[str],
) -> None:
    seen_names: set[str] = set()
    for relation_index, relation in enumerate(entity.relations):
        relation_location = entity_location + ["relations", str(relation_index)]
        _check_identifier(
            issues,
            relation.name,
            "relation.name",
            "Relation names must use only letters, numbers, or underscores.",
            relation_location + ["name"],
        )

        if relation.name in seen_names:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="relation.duplicate",
                    message=(
                        f"Entity '{entity.name}' has duplicate relation '{relation.name}'."
                    ),
                    location=relation_location + ["name"],
                )
            )
        else:
            seen_names.add(relation.name)

        if relation.target_entity == entity.name:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="relation.self_reference",
                    message=(
                        f"Relation '{entity.name}.{relation.name}' references the same entity. "
                        "Double-check that this self-reference is intentional."
                    ),
                    location=relation_location + ["target_entity"],
                )
            )


def _check_custom_endpoints(
    issues: list[ValidationIssue],
    entity,
    entity_location: list[str],
) -> None:
    seen_paths: set[tuple[str, str]] = set()
    for endpoint_index, endpoint in enumerate(entity.custom_endpoints):
        endpoint_location = entity_location + ["custom_endpoints", str(endpoint_index)]
        signature = (endpoint.method, endpoint.path)
        if signature in seen_paths:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="endpoint.duplicate",
                    message=(
                        f"Entity '{entity.name}' has duplicate custom endpoint "
                        f"'{endpoint.method} {endpoint.path}'."
                    ),
                    location=endpoint_location,
                )
            )
        else:
            seen_paths.add(signature)


def _check_relation_targets(
    issues: list[ValidationIssue],
    project: ProjectSchema,
    entity_name_to_index: dict[str, int],
) -> None:
    for entity_index, entity in enumerate(project.entities):
        for relation_index, relation in enumerate(entity.relations):
            if relation.target_entity not in entity_name_to_index:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="relation.target_missing",
                        message=(
                            f"Relation '{entity.name}.{relation.name}' points to missing "
                            f"entity '{relation.target_entity}'."
                        ),
                        location=[
                            "entities",
                            str(entity_index),
                            "relations",
                            str(relation_index),
                            "target_entity",
                        ],
                    )
                )


def _check_cycles(
    issues: list[ValidationIssue],
    graph: dict[str, list[str]],
) -> None:
    visited: set[str] = set()
    stack: list[str] = []
    active: set[str] = set()
    recorded_cycles: set[str] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        active.add(node)
        stack.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
                continue
            if neighbor in active:
                cycle_nodes = stack[stack.index(neighbor) :] + [neighbor]
                cycle_label = " -> ".join(cycle_nodes)
                if cycle_label not in recorded_cycles:
                    recorded_cycles.add(cycle_label)
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="relation.circular",
                            message=f"Circular dependency detected: {cycle_label}.",
                            location=["entities"],
                        )
                    )
        stack.pop()
        active.discard(node)

    for node in graph:
        if node not in visited:
            dfs(node)


def _check_identifier(
    issues: list[ValidationIssue],
    value: str,
    code: str,
    message: str,
    location: list[str],
) -> None:
    if not IDENTIFIER_RE.match(value):
        issues.append(
            ValidationIssue(
                severity="error",
                code=code,
                message=message,
                location=location,
            )
        )


def _validate_default_value(field: FieldSchema) -> bool:
    if field.default is None:
        return False
    if field.type in {FieldType.string, FieldType.text}:
        return not isinstance(field.default, str)
    if field.type == FieldType.integer:
        return isinstance(field.default, bool) or not isinstance(field.default, int)
    if field.type == FieldType.float_:
        return isinstance(field.default, bool) or not isinstance(
            field.default, (int, float)
        )
    if field.type == FieldType.boolean:
        return not isinstance(field.default, bool)
    if field.type == FieldType.datetime:
        return not isinstance(field.default, str)
    return False
