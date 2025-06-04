import pytest

from ai_groq import extract_first_json


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Some text ```json\n{\"a\": 1}\n``` end", {"a": 1}),
        ("```{\"b\": 2}```", {"b": 2}),
        ("random {\"c\": 3} text", {"c": 3}),
        ("no json here", None),
    ],
)
def test_extract_first_json(text, expected):
    assert extract_first_json(text) == expected
