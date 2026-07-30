from app import app
with app.test_client() as client:
    resp = client.post('/api/garment-discovery/chat', json={"user_id": "test_kw", "message": "under $50"})
    print(resp.get_json())
