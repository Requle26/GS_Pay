def test_admin_page_requires_login(client):
    response = client.get(
        "/admin",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"