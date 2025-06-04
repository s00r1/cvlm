import pytest
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial
import socket

from extract_offer import extract_text_from_url


def test_public_url():
    text = extract_text_from_url('https://example.com')
    assert not text.startswith('[Erreur')
    assert 'Example Domain' in text

@pytest.mark.parametrize('url', [
    'http://127.0.0.1',
    'http://10.0.0.1',
    'http://localhost',
    'http://192.168.1.1',
    'http://172.16.0.1',
    'http://[::1]',
])
def test_private_url_blocked(url):
    text = extract_text_from_url(url)
    assert text.startswith('[Erreur')


def _run_test_server(directory):
    handler = partial(SimpleHTTPRequestHandler, directory=directory)
    server = HTTPServer(('localhost', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_local_html_extraction(tmp_path, monkeypatch):
    html = '<html><body><p>' + ('Hello ' * 40) + '</p></body></html>'
    (tmp_path / 'index.html').write_text(html)

    server = _run_test_server(tmp_path)
    url = f'http://localhost:{server.server_address[1]}/index.html'

    monkeypatch.setattr(socket, 'gethostbyname', lambda host: '93.184.216.34')
    try:
        text = extract_text_from_url(url)
    finally:
        server.shutdown()

    assert not text.startswith('[Erreur')
    assert 'Hello' in text


@pytest.mark.parametrize('url', [
    'notaurl',
    'ftp://example.com',
    'file:///tmp/test.html',
])
def test_invalid_url(url):
    text = extract_text_from_url(url)
    assert text == "[Erreur : L’URL fournie n’est pas valide.]"
