from fastapi import Request
from starlette.datastructures import FormData


async def form_data(request: Request) -> FormData:
    """Lets sync routes read forms with dynamic or repeated field names."""
    return await request.form()
