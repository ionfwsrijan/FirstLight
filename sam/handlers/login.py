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


def _roles_for(username: str) -> str:
    # Login accepts the Cognito username (meera/rao/kapoor) OR the demo email,
    # so mis-typing "officer@firstlight.demo" still lands on the kapoor account.
    _EMAIL_TO_USER = {
        "parent@firstlight.demo": "meera",
        "principal@firstlight.demo": "rao",
        "officer@firstlight.demo": "kapoor",
    }
    return _EMAIL_TO_USER.get((username or "").strip().lower())


def handler(event: dict, _context) -> dict:
    body = parse_body(event)
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    if not username or not password:
        return respond(400, {"error": "username and password are required"})

    client = boto3.client("cognito-idp", region_name=os.environ["AWS_REGION"])
    token = None
    uname_used = username
    attempts = [username] + ([_roles_for(username)] if _roles_for(username) else [])
    for uname in attempts:
        try:
            result = client.admin_initiate_auth(
                UserPoolId=os.environ["USER_POOL_ID"],
                ClientId=os.environ["USER_POOL_CLIENT_ID"],
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": uname, "PASSWORD": password},
            )
            token = (result.get("AuthenticationResult") or {}).get("IdToken", "")
            if token:
                uname_used = uname
                break
        except Exception as exc:  # boto3 exceptions vary by SDK version
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code not in ("NotAuthorizedException", "UserNotFoundException", "InvalidParameterException"):
                return respond(500, {"error": "login unavailable", "detail": code})

    if not token:
        return respond(401, {"error": "invalid credentials"})

    # The JWT payload is what the API authorizer validates; re-decode cheaply here.
    claims = token.split(".")[1]
    claims += "=" * (-len(claims) % 4)
    try:
        import base64

        user = json.loads(base64.urlsafe_b64decode(claims))
    except Exception:
        user = {}

    return respond(
        200,
        {"token": token, "role": _role(user), "user": uname_used,
         "sub": uname_used, "displayName": user.get("email") or uname_used},
    )
