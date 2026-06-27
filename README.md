# ren-skills

A collection of agent-agnostic skills — self-contained Markdown directories that any agent
which reads `~/.agents/skills` can use.

## Install

```bash
git clone https://github.com/<you>/ren-skills.git && cd ren-skills && ./install.sh
```

This copies every skill into `~/.agents/skills`. Install a single skill by name:
```bash
./install.sh aws-permission-evaluator
```

## Skills

- **aws-permission-evaluator** — explains whether an AWS action on a resource is allowed or
  denied, and why, for any service with a resource-based policy (S3, DynamoDB, Lambda, SQS,
  SNS, Secrets Manager, KMS, ECR, API Gateway, EventBridge, …). Reasons through IAM, permission
  boundaries, resource policies, SCPs, RCPs, and KMS key policies.
- **obsidian-todos** — captures your work as todos in an Obsidian vault and manages them over
  time, via the official Obsidian CLI's native task commands. Append a todo to today's daily
  note, mark it done/in-progress, list outstanding todos, and refresh a most-recent-first task
  dashboard. Includes a `doctor` command to verify setup on a new machine.

## License

MIT — see [LICENSE](./LICENSE).
