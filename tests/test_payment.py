def test_payment_requires_card(client):
    response = client.post(
        "/api/booth/menus/test-menu/pay",
        data={},
    )

    assert response.status_code in {
        403,
        400,
    }