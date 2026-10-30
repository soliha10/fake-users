import re

import pytest

from app.main import app


@pytest.fixture()
def client():
    app.config["TESTING"] = False
    return app.test_client()


def test_index_renders_ten_users_and_locales(client):
    response = client.get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert html.count('data-label="Name"') == 10
    assert "English (USA)" in html and "Deutsch (Deutschland)" in html


def test_same_url_returns_same_page(client):
    url = "/?locale=de_DE&seed=123&batch=4"
    assert client.get(url).data == client.get(url).data


def test_next_link_advances_and_keeps_arguments(client):
    html = client.get("/?locale=de_DE&seed=5&batch=2").get_data(as_text=True)
    assert re.search(r"locale=de_DE&amp;seed=5&amp;batch=3", html)
    assert re.search(r"locale=de_DE&amp;seed=5&amp;batch=1", html)


def test_form_does_not_carry_batch(client):
    html = client.get("/?batch=7").get_data(as_text=True)
    form = html[html.index('<form'):html.index('</form>')]
    assert 'name="batch"' not in form


@pytest.mark.parametrize("url", ["/?seed=abc", "/?batch=-1", "/?locale=xx_XX", f"/?seed={2**63}"])
def test_invalid_input_gets_friendly_page(client, url):
    response = client.get(url)
    assert response.status_code == 400
    assert "Back to the generator" in response.get_data(as_text=True)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
