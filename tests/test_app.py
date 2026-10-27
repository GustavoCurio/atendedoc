from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_demo_question_and_source_evidence(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not app.exception
    assert app.metric[0].value == "3"
    next(button for button in app.button if button.label == "Prazo de entrega").click().run()
    next(button for button in app.button if button.label == "Consultar documentos").click().run()
    assert not app.exception
    assert any("3 a 5 dias úteis" in item.value for item in app.markdown)
    assert any("[F1]" in item.value for item in app.markdown)


def test_provider_configuration_and_empty_upload_base(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    next(radio for radio in app.radio if radio.label == "Formato da resposta").set_value("Síntese com IA").run()
    assert not app.exception
    assert next(button for button in app.button if button.label == "Consultar documentos").disabled
    next(radio for radio in app.radio if radio.label == "Documentos usados na consulta").set_value("Meus documentos").run()
    assert not app.exception
    assert any("Envie documentos" in item.value for item in app.info)
