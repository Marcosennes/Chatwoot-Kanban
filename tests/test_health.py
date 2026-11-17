def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_kanban(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/kanban"


def test_sidebar_script_is_served(client):
    response = client.get("/chatwoot-sidebar.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert "data-kanban-sidebar-item" in response.text
