import pytest
from pydantic import ValidationError

from models.characters import CharacterDescription, CharacterList
from services.fireworks import _flatten_schema


def test_flatten_schema_preserves_literal_enums():
    """Literal-derived enums must survive _flatten_schema for Fireworks."""
    schema = CharacterList.model_json_schema()
    _flatten_schema(schema)

    # Navigate to the CharacterDescription schema
    char_desc_ref = schema["properties"]["characters"]["items"]["$ref"]
    # ref looks like "#/$defs/CharacterDescription"
    defs_key = char_desc_ref.split("/")[-1]
    char_schema = schema["$defs"][defs_key]

    type_enum = char_schema["properties"]["type"]["enum"]
    importance_enum = char_schema["properties"]["importance"]["enum"]

    assert set(type_enum) == {"speaking", "creature", "npc_entity"}
    assert set(importance_enum) == {"major", "minor"}


def test_character_description_literal_validation():
    """Invalid Literal values must raise ValidationError."""
    with pytest.raises(ValidationError):
        CharacterDescription(
            name="Alice",
            type="protagonist",  # invalid
            importance="major",
            description="Main character",
        )
