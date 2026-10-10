"""Role matrix: what each actor may do.

Roles model the actual stakeholders of a school morning:
  parent     - read decisions, ask the agent for their own school(s)
  principal  - everything a parent does + initiate/recall alerts
  officer    - run the morning, read the ledger, audit tamper state

Enforcement lives in the API layer (deps.require) and in Cedar policies
(the declarative source of truth in auth/cedar/policies.cedar).
"""

from __future__ import annotations

from typing import Literal

Role = Literal["parent", "principal", "officer"]

# role -> set of actions. Machine-authoritative mirror of policies.cedar.
PERMS: dict[str, set[str]] = {
    "parent": {"school:read", "agent:talk", "agent:ask"},
    "principal": {"school:read", "agent:talk", "agent:ask", "alert:send", "alert:recall"},
    "officer": {"school:read", "agent:talk", "agent:ask", "alert:send", "alert:recall", "run:morning", "ledger:read", "cert:verify"},
}

ALLOWED = ("GREEN", "PROTECTED", "CLOSED")


def allowed(role: str, action: str) -> bool:
    return action in PERMS.get(role, set())


def roles() -> list[str]:
    return list(PERMS)
