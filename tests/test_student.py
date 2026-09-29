def test_card_requires_serial(client):
    response = client.get(
        "/api/cards/%20"
    )

    assert response.status_code == 400