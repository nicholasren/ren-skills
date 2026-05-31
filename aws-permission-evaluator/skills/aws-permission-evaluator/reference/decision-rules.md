# AWS Permission Decision Rules

Generic model for deciding whether a principal may perform an action on a resource. Applies
to any AWS resource that supports a resource-based policy — S3 buckets/objects, DynamoDB
tables, SQS queues, Secrets Manager secrets, KMS keys, Lambda functions, etc.

## The players

| Term | What it is | Where it lives |
|---|---|---|
| **Principal** | The IAM role (or user) making the request. | An AWS account. |
| **Action** | A service API call — `s3:GetObject`, `dynamodb:DeleteTable`, `kms:Decrypt`. | — |
| **Resource** | The thing acted on — bucket, object, table, index, key. | An AWS account — same as, or different from, the principal's. |

The pivotal question: **is the principal in the same AWS account as the resource?** The
answer changes the rules.

## The six policy types

- **SCP (Service Control Policy)** — at the org/OU/account level. Governs **principals** in
  those accounts. Can only restrict, never grant. Does not affect external callers.
- **RCP (Resource Control Policy)** — at the org/OU/account level. Governs **resources** in
  those accounts; applies to *every* call hitting them, including external callers. Can only
  restrict. The resource-side counterpart to SCP. (Newer; verify which services support it.)
- **Identity policy (IAM)** — attached to the role. **Grants** permissions to the principal.
- **Permission boundary** — attached to the role. A **ceiling**: effective permissions are
  the *intersection* of identity policy and boundary. Never grants; only caps.
- **Resource policy** — attached to the resource (bucket policy, table resource policy, KMS
  key policy). **Grants** access to specified principals.
- **Session policy** — an inline policy passed at `sts:AssumeRole`; further caps the session
  by the same intersection rule.

### SCP allow semantics (the FullAWSAccess subtlety)

A common misconception is "SCPs can only deny." Mechanically that's not quite right — SCPs are
an **allowlist filter**: an action is permitted only if `Allow`ed by an SCP at every level of
the hierarchy. The reason SCPs *feel* deny-only is the default `FullAWSAccess` policy AWS
attaches to every root, OU, and account, which `Allow`s `"*"`.

- **Default in place (`FullAWSAccess` attached):** everything is implicitly allowed at the SCP
  layer; the only way an SCP restricts is via an explicit `"Effect": "Deny"`. ← most orgs
- **`FullAWSAccess` removed / restrictive allow-list SCP:** any action not in the SCP's allow
  set is denied **by absence** — no explicit `Deny` required.

So when evaluating: if you don't know the org's SCP setup, assume the default (absence ≠ deny)
unless told otherwise, but flag that a removed `FullAWSAccess` would change the answer. RCPs
behave identically with their own default `RCPFullAWSAccess`.

### SCP vs RCP symmetry

| | Attached to | Constrains | Affects |
|---|---|---|---|
| **SCP** | Caller's org/OU/account | Identities in that scope | What *your* principals can call |
| **RCP** | Resource owner's org/OU/account | Resources in that scope | What *anyone* (incl. external) can do *to your resources* |

## The core decision rule (ordered)

1. **Explicit `Deny` anywhere wins.** A single `"Effect": "Deny"` in any policy — SCP, RCP,
   IAM, boundary, resource policy, KMS policy — kills the request.
2. **Caller's SCP must not block** the action. SCPs use allowlist semantics — an action must
   be `Allow`ed by an SCP at *every* level of the org hierarchy (root → OU → account). **But**
   AWS attaches a default `FullAWSAccess` SCP (`Allow "*"`) everywhere, so in the common case
   absence does **not** deny — only an explicit `Deny` restricts. The allowlist (absence =
   implicit deny) only bites if `FullAWSAccess` has been *removed* and replaced with a
   restrictive allow-list SCP. See "SCP allow semantics" below.
3. **Resource owner's RCP must not block** the action (if RCP applies to that service). RCPs
   follow the same model: a default `RCPFullAWSAccess` allows everything, so normally only an
   explicit `Deny` restricts unless that default has been removed.
4. **Same account vs cross account:**
   - **Same account:** an IAM Allow on the role is sufficient for the resource itself — the
     resource policy need not mention the principal. (Resource policies still useful to
     *restrict*, e.g. `aws:SourceVpce`.)
   - **Cross account:** the role's account must allow (IAM) **and** the resource's account
     must allow the principal (resource policy). Both sides must say yes.
5. **Permission boundary** (if attached): the action must be in its allowed set — unless a
   resource-policy grant bypasses an *implicit* deny (same-account only; see gotchas.md).

### Five things to burn in

1. Explicit deny wins, everywhere — including in a boundary, SCP, or RCP.
2. Same-account is generous: an IAM Allow on the role is enough.
3. Resource-policy grants bypass permission boundaries (same-account only) — but only an
   *implicit* deny, never an explicit one.
4. Cross-account requires both sides to say yes (IAM **and** resource policy).
5. SCP guards your principals; RCP guards your resources. Neither is bypassable by a
   resource-policy grant. Nothing overrides an explicit deny.

## What's required, by scenario

The rows below use S3 and DynamoDB as the concrete examples, but the pattern is **the same for
every service with a resource-based policy** (Lambda, SQS, SNS, Secrets Manager, ECR, …) — see
`services.md`. Read "resource policy" as that service's policy (queue policy, function policy,
secret policy, …) and apply the KMS column only when the caller touches a CMK directly.

"Must allow" = the policy must not produce a deny (explicit or implicit) for the action.

| Scenario | IAM allow | Resource policy allow | KMS key policy allow | Caller SCP | Resource-acct RCP | Perm. boundary |
|---|---|---|---|---|---|---|
| **S3 SSE-S3, same account** | required | not required | n/a | must allow | must allow | must not deny |
| **S3 SSE-S3, cross account** | required | **required** | n/a | must allow | must allow | must not deny |
| **S3 SSE-KMS `aws/s3`, same account** | required | not required | implicit (AWS-managed) | must allow | must allow | must not deny |
| **S3 SSE-KMS `aws/s3`, cross account** | — | — | — | — | — | **not supported — use a CMK** |
| **S3 SSE-KMS CMK, same account** | required (s3 + kms) | not required | **required — key policy must name principal** | must allow | must allow | must not deny |
| **S3 SSE-KMS CMK, cross account** | required (s3 + kms) | **required** | **required — key policy must name principal** | must allow | must allow | must not deny |
| **DynamoDB, same account** | required | not required | n/a (DDB-managed) | must allow | must allow | must not deny |
| **DynamoDB, cross account** | required | **required** (table resource policy) | n/a (DDB-managed) | must allow | must allow | must not deny |

Notes:
- "Caller SCP" = SCP at the principal's org/OU/account. "Resource-acct RCP" = RCP at the
  resource's org/OU/account; if RCP isn't supported for the service, treat as "n/a".
- "Permission boundary must not deny" assumes a boundary is attached; if none, the column is moot.

## Why RCP exists

SCPs only constrain *your* principals, not external ones. Before RCPs, someone in your org
could attach a permissive resource policy granting an external account, and the SCP couldn't
see those external callers. RCPs gate *every* call to in-scope resources regardless of caller.

Typical RCP patterns: deny unless `aws:PrincipalOrgID` matches; deny unless
`aws:PrincipalAccount == aws:ResourceAccount`; lock tagged resources to approved roles only.
