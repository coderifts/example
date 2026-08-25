"""
Shared contract fixtures for the variants.

A CodeRifts gate answers a question about *contract drift*: the agent was built
against `OLD_SPEC`, the API now serves `NEW_SPEC` — is it still safe to act?

UNSAFE_* removes an endpoint the agent depends on (a breaking change).
SAFE_*   adds an optional field (additive, non-breaking).
"""

OLD_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Orders API", "version": "1.0.0"},
    "paths": {
        "/orders/{id}": {
            "get": {
                "summary": "Get an order",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}

# Breaking: the endpoint the agent calls is gone.
UNSAFE_NEW_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Orders API", "version": "2.0.0"},
    "paths": {},
}

# Non-breaking: same endpoint, one added optional response field.
SAFE_NEW_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Orders API", "version": "1.1.0"},
    "paths": {
        "/orders/{id}": {
            "get": {
                "summary": "Get an order",
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "status": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        }
    },
}
