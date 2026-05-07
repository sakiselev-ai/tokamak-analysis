from __future__ import annotations


class SecurityHeadersMiddleware:
    """Add standard security headers to every response (pure ASGI)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"strict-transport-security", b"max-age=63072000; includeSubDomains"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"content-security-policy", b"default-src 'self'"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
