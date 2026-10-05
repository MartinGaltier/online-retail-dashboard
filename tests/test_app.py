"""Exécution de l'application avec le simulateur de Streamlit (données réelles préparées)."""

from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from retail import config

pytestmark = pytest.mark.skipif(
    not config.PROCESSED_FILE.exists(), reason="données préparées absentes"
)

ENTRYPOINT = str(config.ROOT_DIR / "streamlit_app.py")
PAGES = ["app_pages/overview.py", "app_pages/breakdown.py", "app_pages/methodology.py"]


def new_app() -> AppTest:
    app = AppTest.from_file(ENTRYPOINT, default_timeout=60)
    app.run()
    return app


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_without_error(page):
    app = new_app()
    app.switch_page(page).run()
    assert not app.exception
    assert not app.error
    assert app.title


def test_overview_metrics():
    app = new_app()
    labels = [metric.label for metric in app.metric]
    assert "CA des ventes" in labels and "Panier moyen" in labels
    values = {metric.label: metric.value for metric in app.metric}
    assert values["Commandes de vente"] == "19 770"


def test_country_filter_changes_metrics():
    app = new_app()
    before = {metric.label: metric.value for metric in app.metric}
    app.radio(key="f_zone").set_value("Royaume-Uni").run()
    after = {metric.label: metric.value for metric in app.metric}
    assert not app.exception
    assert after["CA des ventes"] != before["CA des ventes"]
    selection = next(b.value for b in app.markdown if b.value.startswith("**Sélection"))
    assert "Royaume-Uni" in selection


def test_empty_selection_shows_message():
    app = new_app()
    # Aucune facture entre le 24 décembre 2010 et le 3 janvier 2011.
    app.date_input(key="f_period").set_value((date(2010, 12, 25), date(2010, 12, 31))).run()
    assert not app.exception
    assert any("Aucune vente ni annulation" in warning.value for warning in app.warning)
    assert not app.metric


def test_empty_selection_on_breakdown_page():
    app = new_app()
    app.switch_page("app_pages/breakdown.py").run()
    app.date_input(key="f_period").set_value((date(2010, 12, 25), date(2010, 12, 31))).run()
    assert not app.exception
    assert any("Aucune vente ni annulation" in warning.value for warning in app.warning)


def test_no_customer_identifier_displayed():
    app = new_app()
    app.switch_page("app_pages/breakdown.py").run()
    for frame in app.dataframe:
        assert "customer_id" not in frame.value.columns
