# Test Results

Method: trace each prompt through the SKILL.md intake + ordered decision walk, then compare
the verdict and deciding rule to the expected outcome in `test-prompts.md`. (Manual trace, not
an automated harness — see "Gaps" below.)

| Case | Expected | Skill produces | Deciding rule matches? | Pass |
|---|---|---|---|---|
| T1 triggering (clear) | trigger + intake | description matches "why can't role X write"; intake asks for accounts/encryption/known policies | — | ✅ |
| T2 triggering (indirect) | trigger + intake | description matches "AccessDenied … reason through it" | — | ✅ |
| T3 same-acct IAM+boundary allow | Allowed | Allowed (step 4 same-acct: IAM Allow enough; step 5 boundary in allow set) | yes | ✅ |
| T4 boundary implicit-deny, RP grants | Allowed | Allowed (resource-policy bypasses implicit deny, same-acct) | yes | ✅ |
| T5 boundary explicit-deny | Denied | Denied (step 1 explicit deny wins) | yes | ✅ |
| T6 cross-acct, only IAM | Denied | Denied (cross-acct needs both sides) | yes | ✅ |
| T7 cross-acct aws/s3 | Denied (impossible) | Denied (aws/s3 cannot grant cross-acct → use CMK) | yes | ✅ |
| T8 cross-acct CMK, key silent | Denied | Denied (CMK deny-by-default; principal not enumerated) | yes | ✅ |
| T9 SCP blocks vs RP grant | Denied | Denied (SCP block not bypassable) | yes | ✅ |
| T10 incomplete inputs | Cannot determine | Cannot determine + lists missing (accounts, encryption, known policies) | yes | ✅ |

**10/10 pass on manual trace.** Every expected verdict is directly derivable from the ordered
decision walk in SKILL.md, and the tricky corners (implicit vs explicit deny, aws/s3
cross-account, cross-account both-sides, CMK enumeration, SCP FullAWSAccess) each have a
dedicated rule and a worked example.

## Gaps / future work

- These are manual traces. For regression safety, run the prompts through
  claude-with-the-skill (or any agent that loaded the skill) and score automatically.
- No negative-trigger tests yet (prompts that should NOT fire the skill, e.g. "write an IAM
  policy that grants s3:GetObject" — a generation task, not an evaluation task).
- Session-policy and `sts:AssumeRole` chaining cases are described in reference but not yet
  exercised by a test.
