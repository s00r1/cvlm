import io
import json
import os

# Ensure a dummy wkhtmltopdf exists so app import succeeds
os.makedirs('/tmp/bin', exist_ok=True)
dummy_wkhtml = '/tmp/bin/wkhtmltopdf'
with open(dummy_wkhtml, 'w') as f:
    f.write('#!/bin/sh\nexit 0')
os.chmod(dummy_wkhtml, 0o755)
os.environ['PATH'] = '/tmp/bin:' + os.environ['PATH']

from app import app as flask_app  # noqa: E402
import app  # noqa: E402


def minimal_json(prompt):
    """Return simple valid JSON for ask_groq calls."""
    keywords = ['Fiche de poste', 'fiche de poste']
    if any(k in prompt for k in keywords):
        return json.dumps({"titre": "Poste"})
    return json.dumps({"lettre_motivation": "LM", "cv_adapte": {}})


def setup_basic_patches(monkeypatch, captured_html):
    monkeypatch.setattr(app, 'ask_groq', minimal_json)
    monkeypatch.setattr(app, 'is_valid_offer_text', lambda text: True)
    monkeypatch.setattr(app, 'check_lm_paragraphs', lambda text: True)
    monkeypatch.setattr(app, 'extract_text_from_pdf', lambda path: 'cv')
    monkeypatch.setattr(app, 'extract_text_from_docx', lambda path: 'cv')
    monkeypatch.setattr(
        app.pdfkit,
        'from_string',
        lambda html, path, configuration=None, options=None: captured_html.append(html),
    )
    monkeypatch.setattr(app, 'render_cv_docx', lambda *a, **k: None)
    monkeypatch.setattr(app, 'render_lm_docx', lambda *a, **k: None)
    monkeypatch.setattr(app, 'render_fiche_docx', lambda *a, **k: None)


def test_premium_with_photo(monkeypatch):
    captured = []
    setup_basic_patches(monkeypatch, captured)
    client = flask_app.test_client()

    data = {
        'template': 'premium',
        'xp_poste': 'dev',
        'dip_titre': 'diploma',
        'offer_text': 'offer',
    }
    photo = (io.BytesIO(b'img'), 'photo.jpg')
    cv_file = (io.BytesIO(b'%PDF-1.4'), 'cv.pdf')
    resp = client.post(
        '/',
        data={**data, 'photo': photo, 'cv_file': cv_file},
        content_type='multipart/form-data',
    )

    assert resp.status_code == 200
    assert captured, 'pdfkit.from_string not called'
    html = captured[0]
    assert 'cv-photo' in html
    assert 'file://' in html


def test_premium_missing_photo(monkeypatch):
    monkeypatch.setattr(app, 'PREMIUM_PHOTO_REQUIRED', True)
    client = flask_app.test_client()

    data = {
        'template': 'premium',
        'xp_poste': 'dev',
        'dip_titre': 'diploma',
        'offer_text': 'offer',
    }
    resp = client.post('/', data=data)
    assert resp.status_code == 200
    assert 'Une photo est requise pour le modèle premium.' in resp.data.decode()
