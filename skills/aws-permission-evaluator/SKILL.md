---
name: aws-permission-evaluator
description: Explain whether an AWS action on a resource is allowed or denied, and why — or diagnose an observed AccessDenied when the engineer can only see some of the policies. Works for any AWS resource that supports a resource-based policy — S3 buckets, DynamoDB tables, Lambda functions, SQS queues, SNS topics, Secrets Manager secrets, KMS keys, ECR repos, API Gateway, EventBridge, and more. Use when an engineer asks "why can't role X access/invoke/delete Y", "will this principal be allowed to do Z", "explain this AWS access denial / AccessDenied", pastes an AccessDenied error message, or says they can't see the SCP / RCP / permission boundary and need to figure out which policy is blocking them. Works from a prose description of the scenario — no AWS credentials needed.
---

# AWS Permission Evaluator

This skill walks the AWS authorization decision procedure from a prose description of a
scenario and returns a clear verdict (Allowed / Denied), the **deciding rule**, and a fix.
It does not call AWS — it reasons about the policies the engineer describes or pastes in.

It has two modes:

- **Evaluate (forward):** all gate states described → verdict. The flow below.
- **Diagnose (reverse):** the engineer *observed* an AccessDenied and can only see some of
  the gates — typically their IAM identity policy and the resource policy, but **not** the
  SCP, RCP, or permission boundary. Use `reference/triage.md`: decode the error message
  (it names the denying policy type, and since Jan 2026 often the policy ARN), verify the
  visible gates, then run discriminating experiments to corner the hidden gate. Enter this
  mode whenever the engineer pastes an error message or says they can't see a policy.

It applies to **any AWS resource with a resource-based policy** — S3, DynamoDB, Lambda, SQS,
SNS, Secrets Manager, KMS, ECR, API Gateway, EventBridge, OpenSearch, Glue, etc. The decision
procedure is identical across services; only the *name* of the resource policy, the action
prefix, and a couple of KMS/cross-account caveats differ. See `reference/services.md` for the
per-service mapping.

## How to use it

1. **Pin down the five variables** before reasoning. If any are missing from the engineer's
   description, ask — do not guess.

   - **Principal** — the IAM role/user making the call, *and which account it lives in*.
   - **Action** — the API call (`s3:GetObject`, `dynamodb:DeleteTable`, `kms:Decrypt`, …).
   - **Resource** — the bucket/object/table/key/etc., *and which account it lives in*.
   - **Same account or cross account?** — i.e. principal account == resource account.
     This is the single most important branch; the rules differ.
   - **Service** — which AWS service the resource belongs to (S3, DynamoDB, Lambda, SQS,
     Secrets Manager, …). Look it up in `reference/services.md` to get the resource-policy
     name, action prefix, and whether a separate KMS gate applies.
   - **A separate KMS gate?** — only when the service hands KMS to the *caller* (chiefly S3
     with a customer CMK, and Secrets Manager with a CMK). For S3, also determine the
     encryption flavour (SSE-S3, SSE-KMS `aws/s3`, or SSE-KMS CMK). For DynamoDB and most
     other services, the service uses the CMK on your behalf and the caller needs no direct
     `kms:Decrypt` — so there's no separate KMS gate. Ask only if relevant.

   Also note which policy types are known vs. unknown (IAM identity policy, permission
   boundary, resource policy, SCP, RCP, KMS key policy). You can only conclude "Allowed" if
   nothing in the unknown set could deny — say so explicitly.

2. **Walk the decision procedure in this order** (see `reference/decision-rules.md` for the
   full rules and the scenario table):

   1. **Any explicit `Deny` anywhere?** (SCP, RCP, IAM, boundary, resource policy, KMS
      policy) → Denied. Explicit deny beats everything.
   2. **Caller's SCP** allows the action? → if it blocks, Denied. SCPs only constrain; never
      grant. (Note the `FullAWSAccess` subtlety — see decision-rules.md.)
   3. **Resource owner's RCP** allows the action (if RCP applies to that service)? → if it
      blocks, Denied.
   4. **Same account or cross account?**
      - **Same account:** an IAM Allow on the role is enough for the resource itself; the
        resource policy need not name the principal. A resource-policy grant can also bypass
        an *implicit* deny in the permission boundary (not an explicit one).
      - **Cross account:** need *both* an IAM Allow on the role *and* a resource-policy Allow
        naming the principal. Both sides must say yes.
   5. **Permission boundary** (if attached) — the action must be within its allowed set
      (intersection with IAM), unless a resource-policy grant bypasses an implicit deny.
   6. **KMS (only when the caller touches a CMK directly — e.g. S3 with a CMK, Secrets
      Manager with a CMK)** — the key policy must enumerate the principal (by ARN,
      `aws:PrincipalArn`, `aws:PrincipalTag`, or `aws:PrincipalOrgPaths`). KMS is
      deny-by-default; same-account gives nothing for free. See `reference/kms.md`.

3. **Check the common culprits** in `reference/gotchas.md` — these are what engineers get
   wrong (implicit vs. explicit deny, `aws/s3` cross-account being impossible, cross-account
   needing both sides, CMK enumeration, the SCP `FullAWSAccess` subtlety).

## Output format

Always return a **structured verdict**, not free-form prose. Forcing every gate keeps the
reasoning honest:

```
Verdict: Allowed | Denied | Cannot determine (need: <missing inputs>)

Scenario:
  Principal:  <role> (account <A>)
  Action:     <action>
  Resource:   <resource> (account <B>)
  Topology:   same-account | cross-account
  Encryption: <if S3>

Gate-by-gate:
  Explicit deny anywhere ...... pass | FAIL (where)
  Caller SCP allows ........... pass | FAIL | unknown
  Resource RCP allows ......... pass | FAIL | unknown | n/a
  IAM identity allows ......... pass | FAIL | unknown
  Resource policy allows ...... pass | FAIL | unknown | not-required (same-acct)
  Permission boundary ......... pass | FAIL | unknown | none
  KMS key policy enumerates ... pass | FAIL | unknown | n/a

Deciding rule: <the one statement/rule that determines the outcome>
Fix: <concrete change, e.g. "add s3:PutObject to the bucket policy for role X">
```

When inputs are incomplete, set the verdict to "Cannot determine" and list exactly what you
need, rather than assuming the silent policies are permissive or restrictive.

## Diagnose-mode output format

When working backward from an observed denial with hidden gates, return a **ranked
differential**, not a single verdict:

```
Observed:   AccessDenied on <action> / <resource>
Error says: <policy type + ARN if the message names one, else "no policy type named">

Visible gates checked:
  IAM identity allows ......... pass | FAIL (why)
  Resource policy allows ...... pass | FAIL | not-required (same-acct)
  Conditions met .............. pass | SUSPECT (<which condition>)
  Boundary attached? .......... yes (<arn>) | no (ruled out) | unknown

Suspects (ranked):
  1. <gate> — <why suspected>
     Test: <one discriminating experiment from triage.md, cheapest first>
  2. ...

Escalation: <if the top suspect is org-controlled, the precise ask per triage.md step 3>
```

Always extract everything the error message offers before proposing experiments — if it
names a policy type, the differential usually collapses to one suspect.

## Reference files

- `reference/services.md` — per-service mapping: resource-policy name, action prefix,
  cross-account and KMS caveats for S3, DynamoDB, Lambda, SQS, SNS, Secrets Manager, KMS,
  ECR, API Gateway, EventBridge, and more.
- `reference/decision-rules.md` — the full policy model, core decision rule, and the
  "what's required by scenario" table.
- `reference/gotchas.md` — the commonly misunderstood corners.
- `reference/triage.md` — Diagnose mode: error-message grammar (which policy type denied),
  differential tests for hidden SCP/RCP/boundary, read-only CLI runbook, escalation template.
- `reference/kms.md` — KMS CMK key-policy evaluation in depth.
- `examples/generic-scenarios.md` — worked examples to anchor the reasoning.
