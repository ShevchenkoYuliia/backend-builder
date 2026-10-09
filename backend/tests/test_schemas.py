import sys
import os
from datetime import datetime

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas import (
    AIProvider,
    AISettingsUpdateRequest,
    AssistantDraftRequest,
    CustomEndpointSchema,
    DatabaseType,
    EntitySchema,
    FieldSchema,
    FieldType,
    LoginRequest,
    ProjectSchema,
    RegisterRequest,
    RelationSchema,
    RelationType,
)


class TestFieldSchema:
    def test_valid_field(self):
        field = FieldSchema(name="email", type=FieldType.string, required=True)
        assert field.name == "email"
        assert field.type == FieldType.string

    def test_name_whitespace_stripped(self):
        field = FieldSchema(name="  email  ", type=FieldType.string)
        assert field.name == "email"

    def test_leading_underscore_name_is_normalized(self):
        field = FieldSchema(name="_created_at", type=FieldType.datetime)
        assert field.name == "created_at"

    def test_name_too_short_raises(self):
        with pytest.raises(ValidationError):
            FieldSchema(name="", type=FieldType.string)

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            FieldSchema(name="a" * 65, type=FieldType.string)

    def test_name_max_allowed(self):
        field = FieldSchema(name="a" * 64, type=FieldType.string)
        assert len(field.name) == 64

    def test_name_min_allowed(self):
        field = FieldSchema(name="x", type=FieldType.string)
        assert field.name == "x"

    def test_all_field_types_accepted(self):
        for ftype in FieldType:
            f = FieldSchema(name="col", type=ftype)
            assert f.type == ftype

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            FieldSchema(name="col", type="uuid")

    def test_default_required_is_true(self):
        field = FieldSchema(name="col", type=FieldType.string)
        assert field.required is True

    def test_default_unique_is_false(self):
        field = FieldSchema(name="col", type=FieldType.string)
        assert field.unique is False

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            FieldSchema(name="col", type=FieldType.string, unknown_field="oops")


class TestRelationSchema:
    def test_valid_relation(self):
        rel = RelationSchema(
            name="has_orders", target_entity="Order", relation_type=RelationType.one_to_many
        )
        assert rel.name == "has_orders"

    def test_all_relation_types(self):
        for rtype in RelationType:
            r = RelationSchema(name="rel", target_entity="Target", relation_type=rtype)
            assert r.relation_type == rtype

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            RelationSchema(name="r" * 65, target_entity="T", relation_type=RelationType.one_to_many)

    def test_invalid_relation_type_raises(self):
        with pytest.raises(ValidationError):
            RelationSchema(name="rel", target_entity="T", relation_type="belongs_to")

class TestCustomEndpointSchema:
    def test_valid_endpoint(self):
        ep = CustomEndpointSchema(method="GET", path="/items/{id}/activate", description="Activate item")
        assert ep.method == "GET"

    def test_method_lowercased_to_upper(self):
        ep = CustomEndpointSchema(method="post", path="/items", description="Create item")
        assert ep.method == "POST"

    def test_path_without_leading_slash_gets_one(self):
        ep = CustomEndpointSchema(method="GET", path="items", description="List items")
        assert ep.path.startswith("/")

    def test_path_too_long_raises(self):
        with pytest.raises(ValidationError):
            CustomEndpointSchema(method="GET", path="/" + "a" * 120, description="Too long")

    def test_invalid_method_raises(self):
        with pytest.raises(ValidationError):
            CustomEndpointSchema(method="CONNECT", path="/items", description="x")

    def test_empty_description_is_allowed(self):
        ep = CustomEndpointSchema(method="GET", path="/items", description="")
        assert ep.description == ""

class TestProjectSchema:
    def test_valid_project(self):
        p = ProjectSchema(name="My API", description="Test", db_type=DatabaseType.postgresql)
        assert p.name == "My API"

    def test_name_min_length(self):
        p = ProjectSchema(name="A")
        assert p.name == "A"

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            ProjectSchema(name="A" * 121)

    def test_description_max_length(self):
        ProjectSchema(name="Test", description="A" * 400)

    def test_description_too_long_raises(self):
        with pytest.raises(ValidationError):
            ProjectSchema(name="Test", description="A" * 401)

    def test_default_db_type_is_postgresql(self):
        p = ProjectSchema(name="Test")
        assert p.db_type == DatabaseType.postgresql

    def test_all_db_types_accepted(self):
        for db in DatabaseType:
            p = ProjectSchema(name="Test", db_type=db)
            assert p.db_type == db

    def test_invalid_db_type_raises(self):
        with pytest.raises(ValidationError):
            ProjectSchema(name="Test", db_type="sqlite")

class TestRegisterRequest:
    def test_valid_registration(self):
        r = RegisterRequest(email="test@example.com", full_name="Test User", password="securepass123")
        assert r.email == "test@example.com"

    def test_email_normalized_to_lowercase(self):
        r = RegisterRequest(email="TEST@Example.COM", full_name="User", password="password123")
        assert r.email == "test@example.com"

    def test_email_without_at_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="notanemail", full_name="User", password="password123")

    def test_email_without_dot_in_domain_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="test@nodot", full_name="User", password="password123")

    def test_password_too_short_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", full_name="User", password="short")

    def test_password_min_length(self):
        r = RegisterRequest(email="a@b.com", full_name="User", password="12345678")
        assert r.password == "12345678"

    def test_password_max_length(self):
        RegisterRequest(email="a@b.com", full_name="User", password="A" * 128)

    def test_password_too_long_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", full_name="User", password="A" * 129)

    def test_full_name_min_length(self):
        RegisterRequest(email="a@b.com", full_name="AB", password="password123")

    def test_full_name_too_short_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", full_name="A", password="password123")

    def test_full_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", full_name="A" * 81, password="password123")


class TestLoginRequest:
    def test_valid_login(self):
        r = LoginRequest(email="user@test.com", password="mypassword")
        assert r.email == "user@test.com"

    def test_email_normalized(self):
        r = LoginRequest(email="  USER@TEST.COM  ", password="mypassword")
        assert r.email == "user@test.com"

    def test_short_password_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com", password="short")


class TestAssistantDraftRequest:
    def test_valid_prompt(self):
        r = AssistantDraftRequest(prompt="Create a booking system with users and reservations")
        assert len(r.prompt) >= 10

    def test_prompt_too_short_raises(self):
        with pytest.raises(ValidationError):
            AssistantDraftRequest(prompt="short")

    def test_prompt_min_length(self):
        AssistantDraftRequest(prompt="A" * 10)

    def test_prompt_max_length(self):
        AssistantDraftRequest(prompt="A" * 2000)

    def test_prompt_too_long_raises(self):
        with pytest.raises(ValidationError):
            AssistantDraftRequest(prompt="A" * 2001)


class TestAISettingsUpdateRequest:
    def test_valid_openai(self):
        r = AISettingsUpdateRequest(
            provider=AIProvider.openai,
            model="gpt-4o-mini",
            api_key="sk-test-key-1234567890",
        )
        assert r.provider == AIProvider.openai

    def test_valid_ollama_no_key(self):
        r = AISettingsUpdateRequest(provider=AIProvider.ollama, model="llama3.1", api_key=None)
        assert r.api_key is None

    def test_valid_gemini(self):
        r = AISettingsUpdateRequest(
            provider=AIProvider.gemini,
            model="gemini-2.5-flash",
            api_key="AIza-test-key-1234567890",
        )
        assert r.provider == AIProvider.gemini

    def test_valid_custom_with_base_url(self):
        r = AISettingsUpdateRequest(
            provider=AIProvider.custom,
            model="custom-model",
            base_url="https://llm.example.com/v1",
            api_key="custom-key-1234567890",
        )
        assert r.base_url == "https://llm.example.com/v1"

    def test_model_too_short_raises(self):
        with pytest.raises(ValidationError):
            AISettingsUpdateRequest(provider=AIProvider.openai, model="g")

    def test_model_too_long_raises(self):
        with pytest.raises(ValidationError):
            AISettingsUpdateRequest(provider=AIProvider.openai, model="m" * 81)

    def test_api_key_too_short_raises(self):
        with pytest.raises(ValidationError):
            AISettingsUpdateRequest(
                provider=AIProvider.openai, model="gpt-4o", api_key="short"
            )

    def test_invalid_provider_raises(self):
        with pytest.raises(ValidationError):
            AISettingsUpdateRequest(provider="unknown", model="gemini-pro")
