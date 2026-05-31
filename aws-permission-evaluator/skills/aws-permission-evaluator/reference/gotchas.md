# Commonly Misunderstood Corners

These are what engineers get wrong. Run through them whenever the simple decision walk seems
to contradict observed behavior.

## 1. Implicit vs. explicit deny in a permission boundary

A permission boundary is a **ceiling** on identity-based grants — it caps what the role's own
IAM policy can authorize. It does **not** cap what a resource-based policy can authorize.
From AWS's evaluation reference:

> If a resource-based policy grants permission to the principal of the request, then the
> implicit deny that comes from no allow in the identity-based policy or permissions boundary
> is overruled.

The trap is the word **implicit**. The bypass only works against an *implicit* deny (the
action simply isn't in the boundary's allow set). An **explicit** `"Effect": "Deny"` in the
boundary still wins.

| Scenario (same account) | IAM identity | Permission boundary | Resource policy | Result |
|---|---|---|---|---|
| Boundary silent, resource policy allows | doesn't allow | not in allow set (implicit deny) | explicitly allows role | **Allowed** — resource policy bypasses boundary |
| Boundary explicit-denies, resource policy allows | doesn't allow | `Effect: Deny` on action | explicitly allows role | **Denied** — explicit deny wins |
| Boundary silent, resource policy silent | doesn't allow | not in allow set | silent | **Denied** — nothing grants |
| IAM allows, boundary silent, resource policy silent | allows | not in allow set | silent | **Denied** — boundary caps IAM |
| IAM allows, boundary allows, resource policy silent | allows | allows | silent | **Allowed** — IAM path |

**Example.** A role's IAM + boundary only allow writes to buckets named `*-restore` (neither
allows nor explicitly denies others). A *different* bucket's policy explicitly grants the role
`s3:PutObject` → same-account write **succeeds** (bypasses the implicit deny). If the boundary
instead had `"Effect": "Deny"` for `s3:PutObject` on those buckets → **denied**.

## 2. SCPs and RCPs are NOT bypassable by resource-policy grants

| Constraint | Implicit deny? | Bypassable by resource policy? |
|---|---|---|
| Permission boundary | implicit (action not in allow set) | **yes**, same-account |
| Permission boundary | explicit `Deny` | no — explicit deny wins |
| **SCP (caller side)** | explicit `Deny` always; implicit only if `FullAWSAccess` removed | **no** — a resource-policy grant can't bypass an SCP block |
| **RCP (resource side)** | explicit `Deny` always; implicit only if `RCPFullAWSAccess` removed | **no** — a resource-policy grant can't bypass an RCP block |
| Any explicit `Deny` (anywhere) | n/a | no |

So:
- SCP doesn't allow + resource policy allows → **Denied** (SCP wins, even same-account).
- SCP explicit Deny + resource policy allows → **Denied**.
- RCP doesn't allow + resource policy allows → **Denied**.
- RCP explicit Deny + resource policy allows → **Denied**.

Resource-policy grants can paper over an *implicit* deny from a permission boundary, but never
from an SCP or RCP.

## 3. `aws/s3` (AWS-managed KMS key) + cross-account = impossible

SSE-KMS with the AWS-managed `aws/s3` key auto-grants only the bucket's own account. You
**cannot** grant cross-account access with `aws/s3` — there's no way to add an external
principal to a managed key's policy. Switch to a customer-managed CMK.

## 4. Cross-account needs BOTH sides to say yes

Same-account is generous (IAM Allow on the role suffices). Cross-account is not: you need an
IAM Allow on the role's side **and** a resource-policy Allow naming the principal on the
resource's side. A grant on only one side fails.

## 5. KMS is deny-by-default — "same account" buys nothing

Unlike S3 and DynamoDB, KMS gives you nothing for free in the same account. The key policy is
the gate, full stop. See `kms.md`.
