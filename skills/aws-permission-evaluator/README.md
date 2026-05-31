# aws-permission-evaluator

An agent skill that explains whether an AWS action on a resource is **allowed or denied, and
why** — from a prose description of the scenario. No AWS credentials required; it reasons about
the policies you describe or paste in.

Works for any AWS resource that supports a resource-based policy: S3, DynamoDB, Lambda, SQS,
SNS, Secrets Manager, KMS, ECR, API Gateway, EventBridge, and more.

## What it does

Given a principal, action, resource, and account topology, it walks the AWS authorization
decision procedure (explicit deny → SCP → RCP → same/cross-account → permission boundary →
KMS) and returns a structured verdict: **Allowed / Denied / Cannot determine**, the single
**deciding rule**, and a concrete fix.

It's built to catch the corners engineers get wrong — implicit vs. explicit deny in a
boundary, cross-account needing both sides, `aws/s3` cross-account being impossible, CMK key
enumeration, and the SCP `FullAWSAccess` subtlety.

## Files

- `SKILL.md` — intake checklist, ordered decision walk, output format.
- `reference/decision-rules.md` — policy model, core rule, by-scenario table.
- `reference/services.md` — per-service mapping (policy name, action prefix, caveats).
- `reference/gotchas.md` — commonly misunderstood corners.
- `reference/kms.md` — KMS CMK key-policy evaluation in depth.
- `examples/generic-scenarios.md` — worked examples.
- `tests/` — test prompts and a results trace.

## Triggers

Reach for it on questions like "why can't role X access/invoke/delete Y", "will this principal
be allowed to do Z", or "explain this AccessDenied".

## Install

This skill is a self-contained directory of Markdown — no runtime, no dependencies. Install it
into your agent's skills directory (`~/.agents/skills`) with the repository's `install.sh`, or
just copy the folder there manually.
