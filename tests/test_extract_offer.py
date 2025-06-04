import pytest
from extract_offer import extract_text_from_url


def test_public_url():
    text = extract_text_from_url('https://example.com')
    assert not text.startswith('[Erreur')
    assert 'Example Domain' in text

@pytest.mark.parametrize('url', [
    'http://127.0.0.1',
    'http://10.0.0.1',
    'http://localhost',
])
def test_private_url_blocked(url):
    text = extract_text_from_url(url)
    assert text.startswith('[Erreur')
