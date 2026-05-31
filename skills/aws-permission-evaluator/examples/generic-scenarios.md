# Worked Examples

Generic scenarios showing the structured-verdict output. Use these as reasoning anchors.

---

## Example 1 — Same-account S3 write, boundary silent, bucket policy grants

**Prose:** "Role `app-writer` (acct 1111) can't write to bucket `data-1111` (acct 1111). Its
permission boundary only lists writes to `*-restore` buckets, but the bucket policy explicitly
grants `app-writer` `s3:PutObject`. SSE-S3."

```
Verdict: Allowed

Scenario:
  Principal:  app-writer (account 1111)
  Action:     s3:PutObject
  Resource:   data-1111 (account 1111)
  Topology:   same-account
  Encryption: SSE-S3

Gate-by-gate:
  Explicit deny anywhere ...... pass
  Caller SCP allows ........... unknown (assume allows; confirm)
  Resource RCP allows ......... n/a
  IAM identity allows ......... FAIL (not in allow set — implicit deny)
  Resource policy allows ...... pass (bucket policy names app-writer)
  Permission boundary ......... implicit deny — bypassed by resource policy grant
  KMS key policy enumerates ... n/a (SSE-S3)

Deciding rule: same-account resource-policy grant overrules the implicit deny from the boundary.
Fix: none needed — the write should succeed. If it doesn't, look for an EXPLICIT Deny.
```

---

## Example 2 — Same-account, boundary explicit-denies

**Prose:** same as above, but the boundary has `"Effect": "Deny"` for `s3:PutObject` on
non-`*-restore` buckets.

```
Verdict: Denied

Deciding rule: explicit Deny in the permission boundary beats the bucket-policy grant.
Fix: remove/narrow the explicit Deny, or rename the bucket to match `*-restore`.
```

---

## Example 3 — Cross-account DynamoDB delete, only IAM granted

**Prose:** "Role `cleaner` (acct 2222) has IAM `dynamodb:DeleteTable`. Table `orders`
(acct 3333) has no resource policy mentioning `cleaner`."

```
Verdict: Denied

Scenario:
  Principal:  cleaner (account 2222)
  Action:     dynamodb:DeleteTable
  Resource:   orders (account 3333)
  Topology:   cross-account

Gate-by-gate:
  IAM identity allows ......... pass
  Resource policy allows ...... FAIL (table resource policy does not name cleaner)

Deciding rule: cross-account requires BOTH IAM allow and a resource-policy allow.
Fix: add a statement to the `orders` table resource policy granting acct 2222 / role cleaner
     dynamodb:DeleteTable.
```

---

## Example 4 — Cross-account S3 read with `aws/s3`

**Prose:** "Bucket `shared` (acct 4444) encrypted with `aws/s3`. Role `reader` (acct 5555)
needs `s3:GetObject`. Bucket policy grants acct 5555."

```
Verdict: Denied (architecturally impossible as configured)

Deciding rule: SSE-KMS with the AWS-managed aws/s3 key cannot grant cross-account access.
Fix: re-encrypt with a customer-managed CMK, then grant `reader` in BOTH the bucket policy
     and the CMK key policy.
```

---

## Example 5 — Cross-account S3 read with CMK, key policy silent

**Prose:** "Bucket `vault` (acct 6666), CMK-encrypted. Role `reader` (acct 7777) has IAM for
`s3:GetObject` + `kms:Decrypt`. Bucket policy grants `reader`. The CMK key policy uses
root-delegation only for acct 6666 and does not name `reader`."

```
Verdict: Denied

Gate-by-gate:
  IAM identity allows ......... pass (s3 + kms)
  Resource policy allows ...... pass (bucket policy)
  KMS key policy enumerates ... FAIL (reader not named; root-delegation is for acct 6666 only)

Deciding rule: CMK is deny-by-default; cross-account principal must be enumerated in the key
               policy. IAM alone never unlocks a CMK.
Fix: add `reader` (acct 7777) to the CMK key policy for kms:Decrypt (and Encrypt/GenerateDataKey
     if writing).
```

---

## Example 6 — Cross-account Lambda invoke, function policy silent

**Prose:** "Account 9999's EventBridge bus needs to invoke Lambda `processor` (acct 1234).
The EventBridge target is configured, but `processor`'s resource policy has no statement for
the rule/account."

```
Verdict: Denied

Scenario:
  Principal:  EventBridge rule (account 9999)
  Action:     lambda:InvokeFunction
  Resource:   processor (account 1234)
  Topology:   cross-account

Gate-by-gate:
  Resource policy allows ...... FAIL (function policy doesn't grant the caller)

Deciding rule: cross-account invoke needs a lambda:InvokeFunction grant in the function's
               resource policy (typically with aws:SourceArn = the rule ARN).
Fix: add a permission to `processor` allowing the EventBridge principal / source ARN to invoke.
```

---

## Example 7 — Same-account SQS send, IAM allows

**Prose:** "Service role `producer` (acct 5555) sends to queue `jobs` (acct 5555). IAM allows
`sqs:SendMessage`, no boundary, queue policy is silent. SSE-SQS (not a CMK)."

```
Verdict: Allowed

Scenario:
  Principal:  producer (account 5555)
  Action:     sqs:SendMessage
  Resource:   jobs (account 5555)
  Topology:   same-account

Gate-by-gate:
  IAM identity allows ......... pass
  Resource policy allows ...... not-required (same-account)
  KMS key policy enumerates ... n/a (SSE-SQS, no CMK)

Deciding rule: same-account IAM Allow is sufficient; queue policy need not name the principal.
Fix: none. (If it were a CMK and the producer encrypts, also need kms:GenerateDataKey + key policy.)
```

---

## Example 8 — SCP blocks despite resource-policy grant

**Prose:** "Role `svc` (acct 8888) needs `s3:DeleteObject` on same-account bucket `logs`,
which grants it in the bucket policy. But the account has an explicit Deny SCP on
`s3:DeleteObject`."

```
Verdict: Denied

Deciding rule: an SCP block (explicit Deny, or absence when FullAWSAccess is removed) cannot be
               bypassed by a resource-policy grant.
Fix: remove the Deny / add s3:DeleteObject to the applicable SCP for acct 8888's OU.
```
