"""Public console login: turns a username/password into a Cognito IdToken.

All accounts live in the FirstLight user pool (created by seed-users.ps1, same
personas/roles as the local build). This is the same USER_PASSWORD flow the
local console uses, served server-side so the browser never holds more than the
id token it already carries when calling the protected routes.
"""

from __future__ import annotations

import json
import os

import boto3

try:
    from .shared import parse_body, respond
except ImportError:  # Lambda treats handlers/ as the code root (no package parent)
    from shared import parse_body, respond

_ROLES = {
    "parent": "parent",
    "principal": "principal",
    "officer": "officer",
}


def _role(token: dict) -> str:
    sub = token.get("sub", "")
    for localpart, role in _ROLES.items():
        if localpart in sub:
            return role
    email = (token.get("email") or "").split("@")[0]
    return _ROLES.get(email, "viewer")


def handler(event: dict, _context) -> dict:
    body = parse_body(event)
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    if not username or not password:
        return respond(400, {"error": "username and password are required"})

    try:
        result = boto3.client("cognito-idp", region_name=os.environ["AWS_REGION"]).admin_initiate_auth(
            UserPoolId=os.environ["USER_POOL_ID"],
            ClientId=os.environ["USER_POOL_CLIENT_ID"],
            AuthFlow="ADMIN_USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
    except Exception as exc:  # boto3 exceptions vary by SDK version
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("NotAuthorizedException", "UserNotFoundException", "InvalidParameterException"):
            return respond(401, {"error": "invalid credentials"})
        return respond(500, {"error": "login unavailable", "detail": code})

    tokens = result.get("AuthenticationResult", {})
    id_token = tokens.get("IdToken", "")
    if not id_token:
        return respond(401, {"error": "no id token issued"})

    # The JWT payload is what the API authorizer validates; re-decode cheaply here.
    claims = id_token.split(".")[1]
    claims += "=" * (-len(claims) % 4)
    try:
        import base64

        user = json.loads(base64.urlsafe_b64decode(claims))
    except Exception:
        user = {}

    return respond(
        200,
        {"token": id_token, "role": _role(user), "user": user.get("cognito:username", username)},
    )