"""Smoke tests of the Streamlit dashboard: every page runs without error."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent


def test_app_runs_for_both_models() -> None:
    app = AppTest.from_file(str(ROOT / "Investment_project_NPV.py"), default_timeout=120).run()
    assert not app.exception
    app.sidebar.radio[0].set_value("Three independent normals").run()
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Deterministic NPV"] == "€33,973"


def test_asml_page_runs() -> None:
    app = AppTest.from_file(str(ROOT / "pages" / "ASML_valuation.py"), default_timeout=120).run()
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Share price"] == "€1,653"
    assert metrics["Value, central scenario"] == "€1,068"
