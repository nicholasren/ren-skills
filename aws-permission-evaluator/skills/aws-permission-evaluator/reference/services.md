# Per-Service Resource-Policy Reference

The decision rules in `decision-rules.md` apply to **any** AWS resource that supports a
resource-based policy. This table maps the generic model onto specific services: what the
resource policy is called, the action prefix, and service-specific caveats (especially around
cross-account and whether a separate KMS gate applies).

The evaluation procedure does not change per service. What changes is:
- the **name/shape** of the resource-based policy,
- whether a **separate KMS key policy** is also a gate (only when the service hands KMS to the
  caller — chiefly S3 with a CMK), and
- a few **cross-account quirks**.

| Service | Resource-based policy | Action prefix | Cross-account | Separate KMS gate for caller? | Notes |
|---|---|---|---|---|---|
| **S3** | Bucket policy (+ access points, Object Lambda) | `s3:` | needs IAM + bucket policy | **Yes if SSE-KMS CMK** — caller needs `kms:*` on the key + key-policy entry | `aws/s3` managed key can't grant cross-account; use a CMK. Object ACLs largely superseded. |
| **DynamoDB** | Table resource policy (resource-based policy, since 2024) | `dynamodb:` | needs IAM + table resource policy | No — DDB uses the CMK on your behalf; caller doesn't need direct `kms:Decrypt` | Stream/index actions scoped via resource ARNs. |
| **Lambda** | Function resource policy (a.k.a. function permissions) | `lambda:` | needs IAM (caller) + function policy `lambda:InvokeFunction` grant | No (unless the function code itself calls KMS) | Resource policy is how other accounts/services (S3, EventBridge, API GW) are allowed to invoke. Per-alias/version policies possible. |
| **SQS** | Queue policy | `sqs:` | needs IAM + queue policy | Encryption uses SSE-SQS or a CMK; CMK is enforced via key policy when a producer/consumer calls KMS | Common pattern: queue policy grants SNS/S3/EventBridge `sqs:SendMessage` with `aws:SourceArn` condition. |
| **SNS** | Topic policy | `sns:` | needs IAM + topic policy | CMK enforced via key policy for publish/subscribe when applicable | Topic policy grants cross-account publish/subscribe. |
| **Secrets Manager** | Secret resource policy | `secretsmanager:` | needs IAM + secret policy | **Yes if CMK-encrypted** — caller needs `kms:Decrypt` + key-policy entry | Cross-account read requires secret policy + key policy on the CMK. |
| **KMS** | Key policy (always required) | `kms:` | needs IAM + key policy | n/a (it *is* the key) | Deny-by-default; see `kms.md`. Root-delegation vs explicit enumeration. |
| **ECR** | Repository policy | `ecr:` | needs IAM + repo policy | No | Cross-account pull/push via repo policy. |
| **API Gateway** | Resource policy (REST APIs) | `execute-api:` | needs IAM (for IAM-auth APIs) + resource policy | No | Resource policy can allow/deny by source VPC, IP, or account. |
| **EventBridge** | Event bus resource policy | `events:` | needs bus policy to accept cross-account events | No | Cross-account/-region event delivery gated by the target bus policy. |
| **OpenSearch** | Domain access policy | `es:` | needs IAM + domain policy | No | Fine-grained access control is a separate layer on top. |
| **Glue** | Catalog resource policy | `glue:` | needs IAM + catalog policy | No | Cross-account catalog/database/table sharing (often with Lake Formation). |
| **EFS** | File system policy | `elasticfilesystem:` | needs IAM + FS policy | No | |
| **Backup** | Vault access policy | `backup:` | needs IAM + vault policy | CMK enforced via key policy | Cross-account/-region copy gated by destination vault policy. |
| **CodeArtifact** | Domain / repository policy | `codeartifact:` | needs IAM + policy | No | |
| **ECR Public / Serverless / etc.** | Resource policy | service prefix | as above | varies | When in doubt, the generic rule holds: cross-account = IAM allow + resource policy allow. |

## How to use this with the decision walk

1. Identify the service → look up its **resource-policy name** and **action prefix** here.
2. Run the standard ordered walk in `decision-rules.md`, substituting that resource policy
   for "resource policy".
3. Apply the **separate KMS gate only if** the column above says yes (effectively: S3+CMK,
   Secrets Manager+CMK, SQS/SNS/Backup when the caller touches the CMK directly). For
   DynamoDB and most others, the service uses the CMK on your behalf and the caller needs no
   direct `kms:Decrypt`.

## Cross-account: the constant rule

For **every** service in this table, cross-account access requires **both**:
- an **IAM Allow** on the calling principal (within its permission boundary, if any), **and**
- a **resource-policy Allow** naming the principal (or matching it by condition) on the
  resource's side.

The same-account "IAM alone is enough; resource policy may bypass an implicit boundary deny"
shortcut applies equally across services — but **only same-account**, never cross-account.
