// FirstLight authorization policies, written in AWS Cedar (open source).
// Source of truth for what each actor may do. Mirrored in auth/roles.py for
// the Build It runtime; validated with `cedar authorize` in CI (see
// scripts/gate.ps1) and re-asserted on AWS by the Ship It template.

// A parent may read and ask for any school.
permit (
  principal in FirstLight::Role::"parent",
  action in [FirstLight::Action::"school:read",
             FirstLight::Action::"agent:talk",
             FirstLight::Action::"agent:ask"],
  resource in FirstLight::School::"*"
);

// A principal may do all parent actions, and send/recall alerts.
permit (
  principal in FirstLight::Role::"principal",
  action in [FirstLight::Action::"school:read",
             FirstLight::Action::"agent:talk",
             FirstLight::Action::"agent:ask",
             FirstLight::Action::"alert:send",
             FirstLight::Action::"alert:recall"],
  resource in FirstLight::School::"*"
);

// A ward officer may additionally run the morning, read the ledger,
// and verify certificates.
permit (
  principal in FirstLight::Role::"officer",
  action in [FirstLight::Action::"school:read",
             FirstLight::Action::"agent:talk",
             FirstLight::Action::"agent:ask",
             FirstLight::Action::"alert:send",
             FirstLight::Action::"alert:recall",
             FirstLight::Action::"run:morning",
             FirstLight::Action::"ledger:read",
             FirstLight::Action::"cert:verify"],
  resource in FirstLight::Journal::"*"
);

// No one may mutate a decision retroactively. Deny-by-default handles
// everything else; this is explicit so it reads loudly.
forbid (
  principal,
  action in [FirstLight::Action::"decision:rewrite"],
  resource
);