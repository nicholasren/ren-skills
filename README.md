# ren-skills

A collection of agent-agnostic skills — self-contained Markdown directories that any agent
which reads a skills folder (e.g. via `~/.agents/skills` or `~/.cursor/skills`) can use.

## Install

One command, from a clone:
```bash
git clone https://github.com/<you>/ren-skills.git && cd ren-skills && ./install.sh
```

Or remotely:
```bash
curl -fsSL https://raw.githubusercontent.com/<you>/ren-skills/main/install.sh | bash
```

By default the installer picks `~/.cursor/skills` if `~/.cursor` exists, otherwise
`~/.agents/skills`. Override with `SKILLS_DIR`:
```bash
SKILLS_DIR=~/.agents/skills ./install.sh
```
Install a single skill by name: `./install.sh aws-permission-evaluator`.

## Skills

- **aws-permission-evaluator** — explains whether an AWS action on a resource is allowed or
  denied, and why, for any service with a resource-based policy (S3, DynamoDB, Lambda, SQS,
  SNS, Secrets Manager, KMS, ECR, API Gateway, EventBridge, …). Reasons through IAM, permission
  boundaries, resource policies, SCPs, RCPs, and KMS key policies.

## License

MIT — see [LICENSE](./LICENSE).
