# ren-skills — Claude plugin marketplace

A small marketplace of Claude skills, installable in Claude Code and Cowork.

## Plugins

### aws-permission-evaluator
Explains whether an AWS action on a resource is **allowed or denied, and why** — from a prose
description, no AWS credentials needed. Works for any service with a resource-based policy
(S3, DynamoDB, Lambda, SQS, SNS, Secrets Manager, KMS, ECR, API Gateway, EventBridge, …) and
reasons through IAM identity policies, permission boundaries, resource policies, SCPs, RCPs,
and KMS key policies. Returns a structured verdict, the deciding rule, and a fix — built to
catch the corners engineers get wrong (implicit vs. explicit deny, cross-account needing both
sides, `aws/s3` cross-account being impossible, CMK key enumeration, the SCP `FullAWSAccess`
subtlety).

## Install
```
/plugin marketplace add <your-github-username>/ren-skills
/plugin install aws-permission-evaluator@ren-skills
```
Run as slash commands in a Claude Code / Cowork session. A local path also works:
`/plugin marketplace add /Users/nicholasren/projects/ren-skills`.

## License
MIT — see [LICENSE](./LICENSE).
