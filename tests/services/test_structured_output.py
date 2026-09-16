from src.application.contracts.providers import StructuredSchema
from src.services.llm.structured import parse_structured_text


def test_repairs_escaped_whitespace_outside_strings_only() -> None:
    schema = StructuredSchema(name="fixture", validator=lambda payload: payload)
    text = r'{"message":"line\nbreak",\n"items":[1,\t2]}'

    result = parse_structured_text(text, schema, provider="fixture")

    assert result == {"message": "line\nbreak", "items": [1, 2]}
