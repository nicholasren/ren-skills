# AccessDenied Triage — Diagnosing with Partial Visibility

The typical developer can read their **IAM identity policy** and the **resource policy**, and
knows whether the call is **same- or cross-account**. They usually **cannot** read the SCP,
RCP, permission boundary document, session policy, or VPC endpoint policy. This runbook turns
a denial into a diagnosis anyway: the hidden gates leak information through the error message
and through cheap experiments.

Run forward evaluation (`decision-rules.md`) on the gates you *can* see first; this runbook is
for when the visible gates all pass and the request is still denied — or when you want to know
*which* hidden gate to blame before opening a ticket.

## Step 0 — Read the error message. It names the gate.

Modern AccessDenied messages follow a fixed grammar:

- **Implicit deny:** `... because no <type> policy allows the <action> action`
- **Explicit deny:** `... with an explicit deny in a <type> policy`
- **Explicit deny + ARN** (rolling out since Jan 2026): `... with an explicit deny in a
  <type> policy: <policy ARN>` — the exact policy is named even if you can't read it.
  Source: [AWS, additional policy details in access denied errors (Jan 2026)](https://aws.amazon.com/about-aws/whats-new/2026/01/additional-policy-details-access-denied-error/).

| Phrase contains | Gate | What it means for you |
|---|---|---|
| `service control policy` | **SCP** (caller's org) | Org guardrail on *your* account. Not fixable from your side — escalate with the ARN if present. |
| `resource control policy` | **RCP** (resource owner's org) | Org guardrail on the *resource's* account. Escalate to the resource owner's platform team. |
| `permissions boundary` | **Boundary** on your principal | Implicit (`no permissions boundary allows`) vs explicit deny matters: same-account, a resource-policy grant can bypass an *implicit* boundary deny (see gotchas.md §1). |
| `session policy` | **Session policy** | Your credentials were vended with a cap (SSO permission set, broker, `AssumeRole` with `--policy`). Re-assume without the cap or fix the vendor. |
| `VPC endpoint policy` | **VPC endpoint** | Network-path gate, invisible in any IAM console. Try the same call from a different network path to confirm. |
| `resource-based policy` | **Resource policy** | You can read this one — re-check Principal / Action / Resource / Condition. Cross-account, `no resource-based policy allows` = the missing other half. |
| `identity-based policy` | **IAM identity policy** | You can read this one. `no identity-based policy allows` = nothing grants; re-check action spelling and resource ARN match. |
| `role trust policy` | **Trust policy** | The `sts:AssumeRole` itself failed — a different gate than the action you were after. |
| `Encoded authorization failure message` | — | Run `aws sts decode-authorization-message --encoded-message <msg>` (needs `sts:DecodeAuthorizationMessage`); the decoded JSON identifies the failing policy type. |

Caveats: not every service emits this grammar (S3 added richer context only in recent years —
older SDK paths may return a bare `Access Denied`); if *multiple* policy types deny, AWS names
only **one** of them, so fixing the named gate can reveal a second denial behind it.

## Step 1 — Verify the gates you CAN see (most denials live here)

Hidden gates are exotic; these four are common. Check them before suspecting an SCP.

1. **Are you who you think you are?** `aws sts get-caller-identity` — wrong profile, wrong
   assumed role, expired/cached credentials, or wrong region is the #1 root cause.
2. **Exact ARN match.** `arn:aws:s3:::bucket` vs `arn:aws:s3:::bucket/*` (bucket-level vs
   object-level actions need different Resource lines); region/account typos; action prefix
   (`s3:GetObject` ≠ `s3:GetObjectVersion`).
3. **Conditions on the policies you can read.** `aws:SourceVpce`, `aws:SourceIp`,
   `aws:PrincipalTag`, `aws:RequestTag`, TLS version, KMS `EncryptionContext`. A visible
   policy with an unmet condition behaves exactly like an invisible deny.
4. **Is a boundary even attached?** You may not be able to read its document, but
   `aws iam get-role --role-name <r>` reveals the `PermissionsBoundary` ARN if one exists.
   No boundary attached → strike it off the suspect list entirely.

## Step 2 — Differential tests (when the message doesn't name the gate)

Change one variable per experiment; each split halves the suspect space.

| Experiment | Outcome → conclusion |
|---|---|
| **Same call from a privileged role in the same account** | Also denied → account-level gate (SCP, RCP, VPC endpoint). Succeeds → principal-level (identity, boundary, session policy). |
| **Same principal, different resource of the same type** | Succeeds → resource-side gate (resource policy, RCP on that resource's account, KMS). Denied → caller-side. |
| **Same call from a different network path** (e.g. not through the VPC endpoint) | Succeeds → VPC endpoint policy. |
| **Cross-account: a principal *inside* the resource's account tries locally** | Succeeds → caller side is missing (IAM/SCP). Denied → resource side (resource policy, RCP, KMS key policy). |
| **KMS-encrypted resource: same call on an unencrypted/SSE-S3 equivalent** | Succeeds → the KMS gate (key policy doesn't enumerate you, or missing `kms:Decrypt`). |
| **Policy Simulator:** `aws iam simulate-principal-policy --policy-source-arn <principal> --action-names <action> [--resource-arns <arn>]` | Factors in the boundary — and, for org member accounts, SCPs — *even though you can't read them*. Needs only `iam:SimulatePrincipalPolicy`. |

CloudTrail (if readable) shows `errorCode`/`errorMessage` for the denied event with the same
policy-type grammar — useful when the SDK swallowed the message.

## Step 3 — Escalate with a precise ask

When the suspect is a gate you can't fix, hand the platform/security team a closed question,
not a mystery:

```
Principal:  arn:aws:iam::111122223333:role/etl-runner
Action:     s3:PutObject
Resource:   arn:aws:s3:::analytics-prod/staging/*
Error:      <full message, incl. "with an explicit deny in a service control policy: arn:...">
Checked:    identity policy allows; bucket policy allows; no boundary attached;
            simulate-principal-policy → implicitDeny at organizations level
Ask:        which SCP denies s3:PutObject for account 111122223333, and what
            condition would let this role through?
```

The request ID + timestamp lets them find the CloudTrail event; the policy ARN (if the error
included one) lets them jump straight to the document.

## Suspect ranking when everything visible passes

No policy type named, visible gates pass, still denied — work this list top-down:

1. **Unmet condition** on a policy you *can* read (looks identical to a hidden deny).
2. **SCP** — confirm via the privileged-role test or the simulator.
3. **Permission boundary** — confirm attachment via `get-role` first.
4. **Session policy** — were your credentials vended by SSO/a broker? Compare with a directly
   assumed role.
5. **VPC endpoint policy** — only if the call traverses one.
6. **RCP** — newest and rarest; resource-side; escalate to the resource owner's org.
7. **KMS key policy** — only when the caller touches a CMK directly (see kms.md); fails
   *closed* and often surfaces as the *service's* AccessDenied, not a KMS error.

## Read-only diagnostic commands

All safe — none mutate anything:

```bash
aws sts get-caller-identity                                  # who am I really
aws iam get-role --role-name <r>                             # boundary attached? trust policy
aws iam list-attached-role-policies --role-name <r>          # what grants exist
aws iam simulate-principal-policy --policy-source-arn <arn> \
    --action-names <action> --resource-arns <arn>            # verdict incl. boundary/SCP effects
aws sts decode-authorization-message --encoded-message <m>   # EC2-style encoded denials
aws s3api get-bucket-policy --bucket <b>                     # the resource side (per service)
```
