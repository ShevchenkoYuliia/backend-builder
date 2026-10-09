import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas import (
    DatabaseType,
    EntitySchema,
    FieldSchema,
    FieldType,
    ProjectSchema,
    RelationSchema,
    RelationType,
)
from services.validator import build_validation_report



def _field(name: str = "title", ftype: str = "string", *, required: bool = True) -> FieldSchema:
    return FieldSchema(name=name, type=FieldType(ftype), required=required)


def _entity(name: str, fields: list | None = None, relations: list | None = None) -> EntitySchema:
    return EntitySchema(
        name=name,
        fields=fields or [_field()],
        relations=relations or [],
        custom_endpoints=[],
    )


def _project(*entities: EntitySchema, db: str = "postgresql") -> ProjectSchema:
    return ProjectSchema(
        name="Test Project",
        description="A test project",
        db_type=DatabaseType(db),
        entities=list(entities),
    )


def _relation(name: str, target: str, rtype: str = "one_to_many") -> RelationSchema:
    return RelationSchema(name=name, target_entity=target, relation_type=RelationType(rtype))


class TestValidProject:
    def test_single_entity_is_valid(self):
        project = _project(_entity("User"))
        report = build_validation_report(project)
        assert report.valid is True
        assert not any(i.severity == "error" for i in report.issues)

    def test_multiple_entities_no_relations(self):
        project = _project(_entity("User"), _entity("Product"), _entity("Order"))
        report = build_validation_report(project)
        assert report.valid is True

    def test_valid_one_to_many_relation(self):
        user = _entity("User", relations=[_relation("has_orders", "Order")])
        order = _entity("Order")
        project = _project(user, order)
        report = build_validation_report(project)
        assert report.valid is True

    def test_postgresql_db_type(self):
        report = build_validation_report(_project(_entity("User"), db="postgresql"))
        assert report.valid is True

    def test_mysql_db_type(self):
        report = build_validation_report(_project(_entity("User"), db="mysql"))
        assert report.valid is True

    def test_mongodb_db_type(self):
        report = build_validation_report(_project(_entity("User"), db="mongodb"))
        assert report.valid is True


class TestEmptyProject:
    def test_no_entities_gives_warning(self):
        project = ProjectSchema(
            name="Empty", description="", db_type=DatabaseType.postgresql, entities=[]
        )
        report = build_validation_report(project)
        codes = [i.code for i in report.issues]
        assert "project.empty" in codes

    def test_no_entities_is_still_valid(self):
        project = ProjectSchema(
            name="Empty", description="", db_type=DatabaseType.postgresql, entities=[]
        )
        report = build_validation_report(project)
        assert report.valid is True

    def test_entity_without_fields_gives_warning(self):
        entity = EntitySchema(name="EmptyEntity", fields=[], relations=[], custom_endpoints=[])
        report = build_validation_report(_project(entity))
        codes = [i.code for i in report.issues]
        assert "entity.no_fields" in codes

    def test_entity_without_fields_is_valid(self):
        entity = EntitySchema(name="EmptyEntity", fields=[], relations=[], custom_endpoints=[])
        report = build_validation_report(_project(entity))
        assert report.valid is True

class TestIdentifierValidation:
    def test_entity_name_with_space_is_error(self):
        entity = EntitySchema(
            name="booking reserve",
            fields=[_field()],
            relations=[],
            custom_endpoints=[],
        )
        report = build_validation_report(_project(entity))
        error_codes = [i.code for i in report.issues if i.severity == "error"]
        assert "entity.name" in error_codes

    def test_entity_name_starts_with_digit_is_error(self):
        entity = EntitySchema(name="1user", fields=[_field()], relations=[], custom_endpoints=[])
        report = build_validation_report(_project(entity))
        error_codes = [i.code for i in report.issues if i.severity == "error"]
        assert "entity.name" in error_codes

    def test_field_name_with_space_is_error(self):
        field = FieldSchema(name="first name", type=FieldType.string, required=True)
        entity = _entity("User", fields=[field])
        report = build_validation_report(_project(entity))
        error_codes = [i.code for i in report.issues if i.severity == "error"]
        assert "field.name" in error_codes

    def test_field_name_starts_with_digit(self):
        field = FieldSchema(name="9score", type=FieldType.integer, required=True)
        entity = _entity("User", fields=[field])
        report = build_validation_report(_project(entity))
        error_codes = [i.code for i in report.issues if i.severity == "error"]
        assert "field.name" in error_codes

    def test_valid_snake_case_identifiers(self):
        fields = [
            _field("first_name"),
            _field("created_at"),
            _field("user_id2"),
            _field("isActive", "boolean"),
        ]
        entity = _entity("UserProfile", fields=fields)
        report = build_validation_report(_project(entity))
        assert report.valid is True

    def test_entity_name_underscore_start_is_error(self):
        entity = EntitySchema(name="_private", fields=[_field()], relations=[], custom_endpoints=[])
        report = build_validation_report(_project(entity))
        error_codes = [i.code for i in report.issues if i.severity == "error"]
        assert "entity.name" in error_codes

    def test_entity_name_with_hyphen_is_error(self):
        entity = EntitySchema(
            name="my-entity", fields=[_field()], relations=[], custom_endpoints=[]
        )
        report = build_validation_report(_project(entity))
        error_codes = [i.code for i in report.issues if i.severity == "error"]
        assert "entity.name" in error_codes

    def test_relation_name_with_space_is_error(self):
        relation = RelationSchema(
            name="has orders",
            target_entity="Order",
            relation_type=RelationType.one_to_many,
        )
        user = EntitySchema(name="User", fields=[_field()], relations=[relation], custom_endpoints=[])
        order = _entity("Order")
        report = build_validation_report(_project(user, order))
        error_codes = [i.code for i in report.issues if i.severity == "error"]
        assert "relation.name" in error_codes

class TestDuplicates:
    def test_duplicate_entity_names(self):
        e1 = _entity("User")
        e2 = _entity("User")
        report = build_validation_report(_project(e1, e2))
        codes = [i.code for i in report.issues if i.severity == "error"]
        assert "entity.duplicate" in codes

    def test_duplicate_field_names_in_entity(self):
        fields = [_field("email"), _field("email")]
        entity = _entity("User", fields=fields)
        report = build_validation_report(_project(entity))
        codes = [i.code for i in report.issues if i.severity == "error"]
        assert "field.duplicate" in codes

    def test_duplicate_relation_names(self):
        relations = [
            _relation("has_items", "Product"),
            _relation("has_items", "Product"),
        ]
        user = _entity("User", relations=relations)
        product = _entity("Product")
        report = build_validation_report(_project(user, product))
        codes = [i.code for i in report.issues if i.severity == "error"]
        assert "relation.duplicate" in codes

    def test_three_entities_two_have_same_name(self):
        report = build_validation_report(
            _project(_entity("A"), _entity("B"), _entity("A"))
        )
        errors = [i for i in report.issues if i.code == "entity.duplicate"]
        assert len(errors) == 1

class TestRelationValidation:
    def test_relation_to_missing_entity_is_error(self):
        user = _entity("User", relations=[_relation("has_orders", "NonExistent")])
        report = build_validation_report(_project(user))
        codes = [i.code for i in report.issues if i.severity == "error"]
        assert "relation.target_missing" in codes

    def test_self_reference_is_warning(self):
        user = _entity("User", relations=[_relation("sub_users", "User")])
        report = build_validation_report(_project(user))
        codes = [i.code for i in report.issues if i.severity == "warning"]
        assert "relation.self_reference" in codes

    def test_self_reference_is_still_valid(self):
        user = _entity("User", relations=[_relation("sub_users", "User")])
        report = build_validation_report(_project(user))
        assert report.valid is False
        warning_codes = [i.code for i in report.issues if i.severity == "warning"]
        assert "relation.self_reference" in warning_codes

    def test_all_relation_types_accepted(self):
        for rtype in ["one_to_many", "many_to_one", "one_to_one", "many_to_many"]:
            a = _entity("Alpha", relations=[_relation(f"rel_{rtype}", "Beta", rtype)])
            b = _entity("Beta")
            report = build_validation_report(_project(a, b))
            assert report.valid is True, f"Failed for relation type: {rtype}"

class TestCycleDetection:
    def test_direct_cycle_a_to_b_b_to_a(self):
        a = _entity("Alpha", relations=[_relation("to_beta", "Beta")])
        b = _entity("Beta", relations=[_relation("to_alpha", "Alpha")])
        report = build_validation_report(_project(a, b))
        codes = [i.code for i in report.issues if i.severity == "error"]
        assert "relation.circular" in codes
        assert report.valid is False

    def test_three_node_cycle(self):
        a = _entity("A", relations=[_relation("to_b", "B")])
        b = _entity("B", relations=[_relation("to_c", "C")])
        c = _entity("C", relations=[_relation("to_a", "A")])
        report = build_validation_report(_project(a, b, c))
        codes = [i.code for i in report.issues if i.severity == "error"]
        assert "relation.circular" in codes

    def test_acyclic_chain_is_valid(self):
        a = _entity("A", relations=[_relation("to_b", "B")])
        b = _entity("B", relations=[_relation("to_c", "C")])
        c = _entity("C")
        report = build_validation_report(_project(a, b, c))
        assert report.valid is True

    def test_diamond_dependency_is_valid(self):
        a = _entity("A", relations=[_relation("r1", "B"), _relation("r2", "C")])
        b = _entity("B", relations=[_relation("r3", "D")])
        c = _entity("C", relations=[_relation("r4", "D")])
        d = _entity("D")
        report = build_validation_report(_project(a, b, c, d))
        assert report.valid is True

class TestReservedIdField:
    def test_field_named_id_gives_warning(self):
        field = FieldSchema(name="id", type=FieldType.integer, required=True)
        entity = _entity("User", fields=[field])
        report = build_validation_report(_project(entity))
        codes = [i.code for i in report.issues if i.severity == "warning"]
        assert "field.reserved_name" in codes

    def test_field_named_ID_uppercase_gives_warning(self):
        field = FieldSchema(name="ID", type=FieldType.integer, required=True)
        entity = _entity("User", fields=[field])
        report = build_validation_report(_project(entity))
        codes = [i.code for i in report.issues if i.severity == "warning"]
        assert "field.reserved_name" in codes

class TestDefaultValueValidation:
    def test_string_field_with_string_default_is_ok(self):
        field = FieldSchema(name="status", type=FieldType.string, default="active")
        entity = _entity("Order", fields=[field])
        report = build_validation_report(_project(entity))
        assert report.valid is True

    def test_integer_field_with_string_default_is_warning(self):
        field = FieldSchema(name="score", type=FieldType.integer, default="not_a_number")
        entity = _entity("User", fields=[field])
        report = build_validation_report(_project(entity))
        codes = [i.code for i in report.issues if i.severity == "warning"]
        assert "field.default_type" in codes

    def test_boolean_field_with_integer_default_is_warning(self):
        field = FieldSchema(name="is_active", type=FieldType.boolean, default=42)
        entity = _entity("User", fields=[field])
        report = build_validation_report(_project(entity))
        codes = [i.code for i in report.issues if i.severity == "warning"]
        assert "field.default_type" in codes

    def test_none_default_is_always_ok(self):
        field = FieldSchema(name="deleted_at", type=FieldType.datetime, default=None)
        entity = _entity("Post", fields=[field])
        report = build_validation_report(_project(entity))
        assert report.valid is True
