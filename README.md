# Studio Agent Use Cases

This repository hosts the skill files used by Studio Agent use cases. The `stage` branch supplies the use cases displayed on the Aura home page in the staging environment, while the `prod` branch contains the production-ready versions.

## Environment branches

| Branch | Environment | Purpose |
| --- | --- | --- |
| `main` | Development | Source of truth for new and updated use cases. |
| `stage` | Staging | Use cases being validated on the Aura home page before release. |
| `prod` | Production | Approved use cases available in production. |

## Promotion strategy

Changes must move through the environments in this order:

```text
main -> stage -> prod
```

1. Develop and review every change against `main`.
2. When the change is ready for staging, open a pull request from `main` into `stage`.
3. Validate the use cases on the Aura home page in the staging environment.
4. After staging approval, open a pull request from `stage` into `prod`.
5. Merge the production pull request after the required checks and approvals pass.

Do not make changes directly on `stage` or `prod`. If a problem is found in either environment, apply the fix to `main` and promote it through the same sequence. This keeps all three branches traceable and prevents environment-specific drift.

Add these links to the README:
- [Promote main to stage](https://github.com/neo4j/studio-agent-use-cases/compare/stage...main?expand=1)
- [Promote stage to prod](https://github.com/neo4j/studio-agent-use-cases/compare/prod...stage?expand=1)

For each promotion:
1) Open the relevant link.
2) Confirm the base and compare branches.
3) Create the pull request.
4) Complete validation and approvals.
5) Select Create a merge commit.

Use merge commits for promotion PRs. Squash or rebase merges can break the ancestry between these long-lived branches and cause later promotions to show previously promoted changes again.

## Contributing

All contributions must be based on `main` and must land in `main` before they can be promoted.

1. Update your local `main` branch:

   ```bash
   git switch main
   git pull origin main
   ```

2. Create a short-lived branch for your change:

   ```bash
   git switch -c feature/<short-description>
   ```

3. Add or update the required skill files and test the use case locally.
4. Commit and push your branch:

   ```bash
   git add .
   git commit -m "Describe the use case change"
   git push -u origin feature/<short-description>
   ```

5. Open a pull request targeting `main` and request review.
6. Once the pull request has passed its checks and been approved, merge it into `main`.

Contributors should not push changes directly to `stage` or `prod`, and promotion pull requests should not contain new development work.

## Downloading a skill by environment

UPX can select an environment by using the corresponding branch in the raw GitHub URL:

```text
https://raw.githubusercontent.com/neo4j/studio-agent-use-cases/<branch>/<path-to-skill-file>
```

Replace `<branch>` with `main`, `stage`, or `prod`. For production deployments that must be reproducible, resolve the branch to a commit SHA and record that SHA with the deployment.

## Promotion workflow

