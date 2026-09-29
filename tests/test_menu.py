def test_menu_endpoint_requires_authentication(client):
    response = client.post(
        "/api/booth/menus",
        data={
            "name": "테스트 메뉴",
            "price": 1000,
        },
    )

    assert response.status_code == 403