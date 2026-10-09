from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FieldType(str, Enum):
    string = "string"
    integer = "integer"
    float_ = "float"
    boolean = "boolean"
    datetime = "datetime"
    text = "text"


class RelationType(str, Enum):
    one_to_many = "one_to_many"
    many_to_many = "many_to_many"
    many_to_one = "many_to_one"
    one_to_one = "one_to_one"


class DatabaseType(str, Enum):
    postgresql = "postgresql"
    mysql = "mysql"
    mongodb = "mongodb"


class AIProvider(str, Enum):
    openai = "openai"
    ollama = "ollama"
    gemini = "gemini"
    claude = "claude"
    custom = "custom"


class FieldSchema(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    type: FieldType
    required: bool = True
    unique: bool = False
    default: Any | None = None
    description: str = ""

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = str(value).strip()
        value = value.lstrip("_0123456789")
        return value


class RelationSchema(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    target_entity: str = Field(min_length=1, max_length=64)
    relation_type: RelationType


class CustomEndpointSchema(StrictModel):
    method: str = Field(default="GET", min_length=3, max_length=6)
    path: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=600)
    code: str | None = Field(default=None)

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        value = value.upper()
        if value not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            raise ValueError("Unsupported HTTP method.")
        return value

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return value if value.startswith("/") else f"/{value}"

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: str | None) -> str:
        return "" if value is None else str(value)


class EntitySchema(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    fields: list[FieldSchema] = Field(default_factory=list)
    relations: list[RelationSchema] = Field(default_factory=list)
    custom_endpoints: list[CustomEndpointSchema] = Field(default_factory=list)


class ProjectSchema(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)
    db_type: DatabaseType = DatabaseType.postgresql
    include_auth: bool = False
    entities: list[EntitySchema] = Field(default_factory=list)



class ValidationIssue(StrictModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    location: list[str] = Field(default_factory=list)


class ValidationReport(StrictModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class UserPublic(StrictModel):
    id: str
    email: str
    full_name: str
    created_at: datetime


class RegisterRequest(StrictModel):
    email: str = Field(min_length=5, max_length=160)
    full_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.lower().strip()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        return value


class LoginRequest(StrictModel):
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower().strip()


class AuthResponse(StrictModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class ProjectRecord(ProjectSchema):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime


class DeleteResponse(StrictModel):
    ok: bool = True


class AISettingsPublic(StrictModel):
    provider: AIProvider = AIProvider.openai
    model: str = "gpt-5-mini"
    base_url: str | None = None
    api_key_present: bool = False
    api_key_masked: str | None = None
    updated_at: datetime | None = None


class AISettingsUpdateRequest(StrictModel):
    provider: AIProvider = AIProvider.openai
    model: str = Field(min_length=2, max_length=80)
    base_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, min_length=10, max_length=300)


class AssistantDraftRequest(StrictModel):
    prompt: str = Field(min_length=10, max_length=2000)


class AssistantDraftResponse(StrictModel):
    chat_id: str
    prompt: str
    assistant_message: str
    project: ProjectSchema
    provider: AIProvider
    model: str
    created_at: datetime
    tokens_used: int = 0
    llm_time: float | None = None


class ChatHistoryItem(StrictModel):
    id: str
    prompt: str
    assistant_message: str
    provider: AIProvider
    model: str
    created_at: datetime
    updated_at: datetime
    status: str | None = None
    failed_attempts: int = 0
    compile_success: bool | None = None
    generation_time: float | None = None


class ChatHistoryDetail(ChatHistoryItem):
    project: ProjectSchema


class ChatListResponse(StrictModel):
    items: list[ChatHistoryItem] = Field(default_factory=list)


class AIKeyDeleteResponse(StrictModel):
    ok: bool = True
    message: str
