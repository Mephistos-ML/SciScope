"""HTTP client address extraction for the deployed proxy contract."""

from fastapi import Request


def read_explore_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None

    fly_client_ip = request.headers.get("fly-client-ip")
    if fly_client_ip:
        return fly_client_ip.strip() or None

    if request.client is not None:
        return request.client.host
    return None
