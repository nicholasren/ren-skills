# Test Prompts

Each case: a prose prompt an engineer might type, the expected verdict, and the deciding rule
the skill must identify. Cases T1–T2 check *triggering*; T3–T10 check *reasoning* (including
the tricky corners). Use these to spot-check the skill after edits.

---

### T1 — Triggering (clear)
**Prompt:** "Why can't my role `etl-runner` write to the S3 bucket `analytics-prod`?"
**Expect:** skill triggers; asks for the missing variables (accounts, encryption, which
policies are known) before concluding.

### T2 — Triggering (indirect)
**Prompt:** "I'm getting AccessDenied calling dynamodb:DeleteTable from a Lambda. Help me reason through it."
**Expect:** skill triggers; runs intake.

---

### T3 — Same-account, IAM allows, boundary allows
**Prompt:** "Role `r` and bucket `b` both in acct 1111. IAM allows s3:GetObject, boundary
allows it, no SCP/RCP issues, SSE-S3, bucket policy silent."
**Expect:** **Allowed.** Deciding rule: same-account IAM Allow within boundary is sufficient.

### T4 — Same-account, boundary implicit-denies, resource policy grants
**Prompt:** "Acct 1111. Role `r` IAM doesn't allow s3:PutObject and the boundary doesn't list
it (no explicit deny). Bucket `b` (acct 1111) policy explicitly grants `r` s3:PutObject. SSE-S3."
**Expect:** **Allowed.** Deciding rule: same-account resource-policy grant overrules the
*implicit* deny in the boundary.

### T5 — Same-account, boundary EXPLICIT-denies, resource policy grants
**Prompt:** same as T4 but the boundary has `"Effect":"Deny"` for s3:PutObject.
**Expect:** **Denied.** Deciding rule: explicit deny beats the resource-policy grant.

### T6 — Cross-account, only IAM granted
**Prompt:** "Role `cleaner` (acct 2222) has IAM dynamodb:DeleteTable. Table `orders`
(acct 3333) resource policy doesn't mention it."
**Expect:** **Denied.** Deciding rule: cross-account needs BOTH IAM allow and resource-policy allow.

### T7 — Cross-account S3 read with `aws/s3`
**Prompt:** "Bucket `shared` (acct 4444) uses aws/s3 encryption. Role `reader` (acct 5555),
bucket policy grants acct 5555 s3:GetObject. IAM allows it."
**Expect:** **Denied (impossible as configured).** Deciding rule: aws/s3 cannot grant
cross-account; must use a CMK.

### T8 — Cross-account CMK, key policy silent
**Prompt:** "Bucket `vault` (acct 6666), CMK-encrypted. Role `reader` (acct 7777) has IAM
s3:GetObject + kms:Decrypt, bucket policy grants it. CMK key policy uses root-delegation for
acct 6666 only and doesn't name `reader`."
**Expect:** **Denied.** Deciding rule: CMK deny-by-default; cross-account principal must be
enumerated in the key policy.

### T9 — SCP blocks despite same-account resource grant
**Prompt:** "Role `svc` (acct 8888) same-account bucket `logs` grants s3:DeleteObject in the
bucket policy, but the account has an explicit Deny SCP on s3:DeleteObject."
**Expect:** **Denied.** Deciding rule: an SCP block is not bypassable by a resource-policy grant.

### T10 — Incomplete inputs
**Prompt:** "Will role `worker` be able to read from bucket `data`?"
**Expect:** **Cannot determine.** Skill lists the missing inputs (accounts, encryption, which
policies are known) rather than guessing.
