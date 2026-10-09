import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.generator import pluralize, python_type, python_literal, snake_case, sqlalchemy_type

class TestSnakeCase:
    def test_already_snake_case(self):
        assert snake_case("booking_reserve") == "booking_reserve"

    def test_pascal_case(self):
        assert snake_case("BookingReserve") == "booking_reserve"

    def test_camel_case(self):
        assert snake_case("bookingReserve") == "booking_reserve"

    def test_all_caps(self):
        assert snake_case("URL") == "url"

    def test_with_spaces(self):
        assert snake_case("user profile") == "user_profile"

    def test_with_hyphens(self):
        assert snake_case("my-entity-name") == "my_entity_name"

    def test_with_mixed_separators(self):
        assert snake_case("My Entity-Name") == "my_entity_name"

    def test_leading_trailing_underscores_stripped(self):
        result = snake_case("__hidden__")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_empty_string_returns_item(self):
        assert snake_case("") == "item"

    def test_only_special_chars_returns_item(self):
        assert snake_case("---") == "item"

    def test_digits_preserved(self):
        assert snake_case("user2profile") == "user2profile"

    def test_single_letter(self):
        assert snake_case("A") == "a"

    def test_long_pascal_case(self):
        result = snake_case("UserProfileSettingsRecord")
        assert result == "user_profile_settings_record"

    def test_consecutive_caps(self):
        result = snake_case("MyURLParser")
        assert result == result.lower()
        assert "_" in result


class TestPluralize:
    def test_regular_word(self):
        assert pluralize("user") == "users"

    def test_already_plural_no_double_s(self):
        assert pluralize("orders") == "orders"

    def test_word_ending_in_ss(self):
        assert pluralize("class") == "classes"

    def test_word_ending_in_x(self):
        assert pluralize("tax") == "taxes"

    def test_word_ending_in_z(self):
        assert pluralize("quiz") == "quizes"

    def test_word_ending_in_ch(self):
        assert pluralize("branch") == "branches"

    def test_word_ending_in_sh(self):
        assert pluralize("wish") == "wishes"

    def test_word_ending_in_y_consonant(self):
        assert pluralize("category") == "categories"

    def test_word_ending_in_y_vowel(self):
        assert pluralize("day") == "days"

    def test_product_simple(self):
        assert pluralize("product") == "products"

    def test_booking(self):
        assert pluralize("booking") == "bookings"

    def test_single_letter(self):
        assert pluralize("a") == "as"

    def test_empty_string(self):
        result = pluralize("")
        assert result == "s"

    def test_already_ends_in_s_not_double(self):
        assert pluralize("news") == "news"

    def test_address_ends_in_ss(self):
        assert pluralize("address") == "addresses"


class TestPythonType:
    def test_string(self):
        assert python_type("string") == "str"

    def test_text(self):
        assert python_type("text") == "str"

    def test_integer(self):
        assert python_type("integer") == "int"

    def test_float(self):
        assert python_type("float") == "float"

    def test_boolean(self):
        assert python_type("boolean") == "bool"

    def test_datetime(self):
        assert python_type("datetime") == "datetime"

    def test_unknown_type_raises(self):
        with pytest.raises(KeyError):
            python_type("unknown_type")


class TestSQLAlchemyType:
    def test_string_maps_to_varchar(self):
        assert sqlalchemy_type("string") == "String(255)"

    def test_text(self):
        assert sqlalchemy_type("text") == "Text"

    def test_integer(self):
        assert sqlalchemy_type("integer") == "Integer"

    def test_float(self):
        assert sqlalchemy_type("float") == "Float"

    def test_boolean(self):
        assert sqlalchemy_type("boolean") == "Boolean"

    def test_datetime(self):
        assert sqlalchemy_type("datetime") == "DateTime"

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            sqlalchemy_type("uuid")

class TestPythonLiteral:
    def test_string(self):
        assert python_literal("active") == "'active'"

    def test_integer(self):
        assert python_literal(42) == "42"

    def test_float(self):
        assert python_literal(3.14) == "3.14"

    def test_true(self):
        assert python_literal(True) == "True"

    def test_false(self):
        assert python_literal(False) == "False"

    def test_none(self):
        assert python_literal(None) == "None"

    def test_empty_string(self):
        assert python_literal("") == "''"

    def test_string_with_quotes(self):
        result = python_literal("it's ok")
        assert eval(result) == "it's ok"

    def test_unicode_string(self):
        result = python_literal("привіт")
        assert eval(result) == "привіт"

    def test_zero(self):
        assert python_literal(0) == "0"

    def test_negative_integer(self):
        assert python_literal(-5) == "-5"
