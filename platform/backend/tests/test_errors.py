from fastapi import HTTPException, Query

from app.core.errors import AppError


async def test_app_error_is_returned_in_the_error_envelope(app, client):
    @app.get("/api/boom")
    async def boom():
        raise AppError(409, "conflict_here", "Something conflicts")

    response = await client.get("/api/boom")

    assert response.status_code == 409
    assert response.json() == {"error": {"code": "conflict_here", "message": "Something conflicts"}}


async def test_unknown_route_answers_not_found_envelope(client):
    response = await client.get("/api/nope")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}


async def test_wrong_method_answers_method_not_allowed_envelope(client):
    response = await client.post("/api/health")

    assert response.status_code == 405
    assert response.json() == {
        "error": {"code": "method_not_allowed", "message": "Method Not Allowed"}
    }


async def test_unmapped_http_status_uses_the_generic_code(app, client):
    @app.get("/api/teapot")
    async def teapot():
        raise HTTPException(status_code=418, detail="I'm a teapot")

    response = await client.get("/api/teapot")

    assert response.status_code == 418
    assert response.json() == {"error": {"code": "http_error", "message": "I'm a teapot"}}


async def test_validation_error_lists_each_invalid_field(app, client):
    @app.get("/api/square")
    async def square(n: int = Query()):
        return {"n": n * n}

    response = await client.get("/api/square", params={"n": "x"})

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"][0]["loc"] == ["query", "n"]
