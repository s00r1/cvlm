import doc_gen


def test_render_cv_docx_adds_photo(monkeypatch):
    calls = {}

    class DummyDoc:
        def add_picture(self, path, width=None):
            calls['path'] = path
        def add_heading(self, *a, **k):
            pass
        def add_paragraph(self, *a, **k):
            pass
        def save(self, *a, **k):
            pass

    monkeypatch.setattr(doc_gen, 'Document', DummyDoc)
    monkeypatch.setattr(doc_gen, 'Inches', lambda x: x)

    doc_gen.render_cv_docx({}, {'prenom': 'A', 'nom': 'B'}, 'out', photo_path='img')

    assert calls['path'] == 'img'
