import importlib
import shutil

import pytest


def test_photo_required(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/wkhtmltopdf")
    monkeypatch.setattr("pdfkit.configuration", lambda **kw: type("Cfg", (), {"wkhtmltopdf": "/usr/bin/wkhtmltopdf"})())
    app = importlib.import_module("app")
    monkeypatch.setattr(app, "PREMIUM_PHOTO_REQUIRED", True)
    client = app.app.test_client()
    resp = client.post("/", data={"template": "premium"})
    assert resp.status_code == 200
    assert b"Veuillez ajouter une photo" in resp.data
