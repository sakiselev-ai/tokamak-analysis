import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_unauthorized(auth_client: AsyncClient):
    """Researcher should not access admin endpoints (TC-011)."""
    res = await auth_client.get("/api/v1/admin/users")
    assert res.status_code == 403
