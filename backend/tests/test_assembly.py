import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas import (
    CustomEndpointSchema,
    DatabaseType,
    EntitySchema,
    FieldSchema,
    FieldType,
    ProjectSchema,
    RelationSchema,
    RelationType,
)
from services.generator import _init_entity_context, generate_project, snake_case, pluralize



class TestInitEntityContext:

    def _make_entity(self, name: str, fields: list[FieldSchema]) -> EntitySchema:
        return EntitySchema(name=name, fields=fields, relations=[], custom_endpoints=[])

    def test_slug_is_snake_case(self):
        entity = self._make_entity("UserProfile", [])
        ctx = _init_entity_context(entity)
        assert ctx["slug"] == "user_profile"

    def test_collection_name_is_plural(self):
        entity = self._make_entity("Product", [])
        ctx = _init_entity_context(entity)
        assert ctx["collection_name"] == "products"

    def test_route_prefix_uses_collection_name(self):
        entity = self._make_entity("Order", [])
        ctx = _init_entity_context(entity)
        assert ctx["route_prefix"] == "/orders"

    def test_id_field_filtered_out(self):
        fields = [
            FieldSchema(name="id", type=FieldType.integer, required=True),
            FieldSchema(name="title", type=FieldType.string, required=True),
        ]
        entity = self._make_entity("Post", fields)
        ctx = _init_entity_context(entity)
        names_in_context = [line.strip() for line in ctx["schema_base_lines"]]
        assert not any("id:" in line for line in names_in_context)
        assert any("title" in line for line in names_in_context)

    def test_ID_uppercase_also_filtered(self):
        fields = [
            FieldSchema(name="ID", type=FieldType.integer, required=True),
            FieldSchema(name="name", type=FieldType.string, required=True),
        ]
        entity = self._make_entity("Category", fields)
        ctx = _init_entity_context(entity)
        names = " ".join(ctx["schema_base_lines"])
        assert "ID:" not in names

    def test_has_datetime_false_without_datetime_field(self):
        entity = self._make_entity(
            "Item", [FieldSchema(name="title", type=FieldType.string)]
        )
        ctx = _init_entity_context(entity)
        assert ctx["has_datetime"] is False

    def test_has_datetime_true_with_datetime_field(self):
        entity = self._make_entity(
            "Event",
            [
                FieldSchema(name="title", type=FieldType.string),
                FieldSchema(name="starts_at", type=FieldType.datetime),
            ],
        )
        ctx = _init_entity_context(entity)
        assert ctx["has_datetime"] is True

    def test_empty_fields_gives_empty_lines(self):
        entity = self._make_entity("Ghost", [])
        ctx = _init_entity_context(entity)
        assert ctx["schema_base_lines"] == []
        assert ctx["sql_model_column_lines"] == []

    def test_seed_assignments_count_matches_fields(self):
        fields = [
            FieldSchema(name="title", type=FieldType.string),
            FieldSchema(name="score", type=FieldType.integer),
            FieldSchema(name="active", type=FieldType.boolean),
        ]
        entity = self._make_entity("Record", fields)
        ctx = _init_entity_context(entity)
        assert len(ctx["seed_assignments"]) == 3

    def test_sqlalchemy_column_line_for_required_field(self):
        fields = [FieldSchema(name="email", type=FieldType.string, required=True)]
        entity = self._make_entity("User", fields)
        ctx = _init_entity_context(entity)
        col_line = ctx["sql_model_column_lines"][0]
        assert "nullable=False" in col_line

    def test_sqlalchemy_column_line_for_optional_field(self):
        fields = [FieldSchema(name="bio", type=FieldType.text, required=False)]
        entity = self._make_entity("Profile", fields)
        ctx = _init_entity_context(entity)
        col_line = ctx["sql_model_column_lines"][0]
        assert "nullable=True" in col_line

    def test_unique_field_reflected_in_column(self):
        fields = [FieldSchema(name="username", type=FieldType.string, unique=True)]
        entity = self._make_entity("User", fields)
        ctx = _init_entity_context(entity)
        col_line = ctx["sql_model_column_lines"][0]
        assert "unique=True" in col_line

    def test_relationships_empty_initially(self):
        entity = self._make_entity("Tag", [FieldSchema(name="name", type=FieldType.string)])
        ctx = _init_entity_context(entity)
        assert ctx["relationship_summary"] == []
        assert ctx["sql_model_relationship_lines"] == []



class TestSeedAssignments:

    def _seed_for(self, ftype: str) -> str:
        fields = [FieldSchema(name="val", type=FieldType(ftype))]
        entity = EntitySchema(name="Test", fields=fields, relations=[], custom_endpoints=[])
        ctx = _init_entity_context(entity)
        return ctx["seed_assignments"][0]

    def test_string_seed(self):
        assert '"Sample val"' in self._seed_for("string")

    def test_text_seed(self):
        assert "Sample text" in self._seed_for("text")

    def test_integer_seed(self):
        assert "=1" in self._seed_for("integer")

    def test_float_seed(self):
        assert "=1.0" in self._seed_for("float")

    def test_boolean_seed(self):
        assert "=True" in self._seed_for("boolean")

    def test_datetime_seed(self):
        assert "datetime.utcnow()" in self._seed_for("datetime")



class TestRouteGeneration:

    def _route(self, entity_name: str) -> str:
        slug = snake_case(entity_name)
        return f"/{pluralize(slug)}"

    def test_user_route(self):
        assert self._route("User") == "/users"

    def test_product_route(self):
        assert self._route("Product") == "/products"

    def test_order_item_route(self):
        assert self._route("OrderItem") == "/order_items"

    def test_booking_reserve_route(self):
        assert self._route("BookingReserve") == "/booking_reserves"

    def test_category_route(self):
        assert self._route("Category") == "/categories"

    def test_address_route(self):
        assert self._route("Address") == "/addresses"

    def test_news_route(self):
        assert self._route("News") == "/news"


class TestGeneratedCustomEndpoints:

    def test_router_imports_basemodel_for_custom_endpoint_schema(self, monkeypatch):
        monkeypatch.setattr(
            "services.generator._format_python_files",
            lambda files: (files, True),
        )
        project = ProjectSchema(
            name="Catalog",
            description="",
            db_type=DatabaseType.postgresql,
            entities=[
                EntitySchema(
                    name="Product",
                    fields=[FieldSchema(name="title", type=FieldType.string)],
                    relations=[],
                    custom_endpoints=[
                        CustomEndpointSchema(
                            method="GET",
                            path="/status",
                            description="Return status.",
                            code=(
                                "class ProductStatus(BaseModel):\n"
                                "    status: str\n\n"
                                "@router.get('/status', response_model=ProductStatus)\n"
                                "def product_status():\n"
                                "    return ProductStatus(status='ok')"
                            ),
                        )
                    ],
                )
            ],
        )

        files, compile_success = asyncio.run(generate_project(project))

        assert compile_success is True
        assert "from pydantic import BaseModel" in files["app/routers/product.py"]
