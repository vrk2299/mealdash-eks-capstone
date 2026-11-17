# MealDash EKS Capstone: Beginner Launch Guide

This guide takes you from a clean terminal to the MealDash food ordering demo running on Amazon EKS, deployed by GitHub Actions, with a private MySQL database on RDS. It is written for the instructor-provided Linux mainserver used in class.

The AWS setup commands must run in Bash on Linux. Do not paste them into Windows PowerShell. Students should use an instructor-approved AWS sandbox or role. Do not share permanent AWS administrator keys with students.

## First, know what you are creating

Terraform creates a separate MealDash network and classroom stack in `ap-south-1`:

- VPC `10.30.0.0/16` with public and private subnets and one NAT Gateway
- EKS cluster `mealdash` running Kubernetes `1.36`, with one `t3.small` worker to start
- A private, single-AZ MySQL RDS database (`db.t3.micro`)
- ECR image repository `mealdash`
- A narrowly scoped IAM role that GitHub Actions assumes through OIDC
- An encrypted, versioned S3 bucket for remote Terraform state and state locking
- A public Application Load Balancer after the Kubernetes Ingress is created

These resources cost money while running. RDS has no retained backup in this disposable lab. `destroy-lab.sh` permanently deletes its database and orders. Use sample data only.

## Repeatability: what must remain after a destroy

Use `bash scripts/destroy-lab.sh` to clean up after class. It keeps two account-level items so the same account can be used again:

1. The S3 Terraform state bucket named `mealdash-terraform-state-<account-id>-ap-south-1`.
2. The GitHub OIDC identity provider `token.actions.githubusercontent.com`.

Do not delete either item when cleaning up the lab. The state bucket is how a later launch continues managing the same Terraform stack. The OIDC provider is shared at the AWS account level; Terraform reads it and does not create it.

If someone manually deletes resources in the AWS console or deletes the state bucket, Terraform may no longer know what exists. Use the guarded destroy script and keep its output until cleanup completes.

## Before you begin

### 1. Open the instructor Linux mainserver

Use the EC2 Instance Connect tab your instructor provides. The tested host is Amazon Linux 2023 with the required tools and an AWS identity already configured.

Check that the required commands are available:

```bash
for tool in aws terraform kubectl helm eksctl curl python3 openssl git; do
  command -v "$tool" >/dev/null && echo "OK: $tool" || echo "MISSING: $tool"
done
```

If a tool is missing, stop and ask the instructor to install it from the official vendor instructions before continuing.

### 2. Confirm the AWS account

Run:

```bash
aws sts get-caller-identity
aws configure list
```

Confirm the returned account is the classroom account. Never continue if you are unsure which account or role is active. Do not paste AWS secret keys, passwords, or credentials into chat or GitHub.

### 3. Confirm GitHub OIDC exists in this AWS account

The stack needs one IAM identity provider for GitHub Actions. It is normally left in place by the previous lab cleanup. Check:

```bash
aws iam list-open-id-connect-providers --output table
```

Look for an ARN ending in `oidc-provider/token.actions.githubusercontent.com`. If it is missing, an AWS account administrator must create it once in **IAM > Identity providers > Add provider** with:

- Provider type: OpenID Connect
- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

Do not create a second provider if one already exists. See the [AWS IAM OIDC setup guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html).

## Phase A: prepare the repository

### 4. Clone the public repo or update the existing checkout

For a first launch:

```bash
cd ~
git clone https://github.com/vrk2299/mealdash-eks-capstone.git
cd mealdash-eks-capstone
```

If the repo is already on the mainserver:

```bash
cd ~/mealdash-eks-capstone
git pull --ff-only
```

Check that you are on the latest `main` branch:

```bash
git status --short --branch
```

The branch should show `main`. Terraform inputs and local runtime files must not be committed.

### 5. Create the private Terraform settings file

Copy the example file:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Get the immutable GitHub IDs:

```bash
bash scripts/get-github-ids.sh vrk2299 mealdash-eks-capstone
```

The helper prints two lines: `github_owner_id` and `github_repository_id`. Open the private settings file:

```bash
nano terraform/terraform.tfvars
```

Replace the two `REPLACE_WITH...` values with the IDs the helper printed. Save and exit. If `nano` is unavailable, ask the instructor for an editor.

This matters because this repository was created after July 15, 2026. GitHub's OIDC subject for newer repositories includes owner and repository IDs, and Terraform uses those IDs to restrict which repository and environment can assume the AWS deploy role. See [GitHub's OIDC subject claim reference](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims).

Keep `terraform/terraform.tfvars` private. It is ignored by Git. The numeric GitHub IDs are identifiers, not credentials; AWS keys, database passwords, staff passwords, and secret keys must never be placed there or in GitHub.

## Phase B: create the AWS infrastructure

### 6. Start the guarded Terraform setup

From the repository root, run:

```bash
bash scripts/start-lab.sh
```

The script will:

1. Confirm the AWS identity and region.
2. Create or reuse the protected S3 Terraform state bucket and initialize remote state.
3. Recover a tagged MealDash deploy role into Terraform state if a previous apply was interrupted.
4. Validate Terraform and show a plan.
5. Ask you to type `CREATE MEALDASH` before applying.
6. Create the VPC, EKS cluster, worker node, RDS database, ECR repository, IAM role and related resources.
7. Connect `kubectl` to the cluster, wait for a Ready node, and install the AWS Load Balancer Controller.
8. Create the namespace and restricted Kubernetes deployment permissions.
9. Retrieve the RDS-managed password without printing it and write runtime credentials into Kubernetes Secrets.

Read the plan before approving. It should describe MealDash resources in `ap-south-1`. If it proposes destroying unrelated resources or you cannot identify the AWS account, do not type the approval phrase; stop and ask the instructor.

When the script asks, type this exact phrase:

```text
CREATE MEALDASH
```

Provisioning commonly takes 20 to 40 minutes. Keep the terminal connected until the script finishes. Do not run `terraform apply` in another directory or delete resources manually while it is working.

### 7. Set the demo kitchen staff password

Near the end, the script asks you to choose a staff password. Use at least 12 characters. It is entered without echo and stored only as a Kubernetes Secret. Save it securely for the demo; it is not printed again.

- Staff username: `staff`
- Staff password: the one entered during setup

Never put this password or the RDS password in GitHub. The workflow deploys the app but does not read Kubernetes runtime Secrets.

### 8. Save the deployment values printed by setup

At the end, `start-lab.sh` prints the values needed by GitHub Actions. Keep the non-secret values handy:

- `AWS_REGION` (normally `ap-south-1`)
- `AWS_DEPLOY_ROLE_ARN` (Terraform output `github_deployer_role_arn`)
- `EKS_CLUSTER_NAME` (normally `mealdash`)
- `ECR_REPOSITORY` (`mealdash`)
- `DB_HOST` (Terraform output `rds_endpoint`)
- `DB_NAME` (`mealdash`)
- `DB_USER` (`mealdash_admin`)

The RDS endpoint changes if RDS is recreated. Do not save or share the RDS password.

## Phase C: connect GitHub Actions and deploy

### 9. Set the GitHub `classroom` environment variables

Open the repo in GitHub and go to **Settings > Environments > classroom**. If the environment does not exist, create it with the exact name `classroom`. Under **Environment variables** (not repository variables), add these seven values:

| Variable | Value |
| --- | --- |
| `AWS_REGION` | `ap-south-1` |
| `AWS_DEPLOY_ROLE_ARN` | Value printed as `github_deployer_role_arn` |
| `EKS_CLUSTER_NAME` | `mealdash` |
| `ECR_REPOSITORY` | `mealdash` (repository name, not the full ECR URL) |
| `DB_HOST` | Value printed as `rds_endpoint` |
| `DB_NAME` | `mealdash` |
| `DB_USER` | `mealdash_admin` |

Do not add AWS access keys, RDS passwords, staff passwords, or Flask secret keys to GitHub. The workflow uses GitHub OIDC to get short-lived AWS credentials.

### 10. Run the first deployment

In GitHub:

1. Open the **Actions** tab.
2. Select **MealDash CI and deploy**.
3. Choose **Run workflow**.
4. Select branch `main` and click **Run workflow**.

Wait for both jobs to finish. A successful run shows `build-check` and `deploy` as green. The deploy job validates the environment values, assumes the scoped AWS role, pushes a unique image to ECR, configures `kubectl`, applies the database connection ConfigMap and Kubernetes workload, then waits for rollout.

Normal pushes to `main` trigger another deployment automatically. Pull requests only run the image build check; they do not deploy.

## Phase D: verify the app and use it in class

### 11. Confirm nodes, pods, and Ingress

Back on the Linux mainserver, run:

```bash
kubectl get nodes -o wide
kubectl get pods,services,ingress -n mealdash -o wide
```

Expected signs:

- At least one EKS node is `Ready`.
- The two `mealdash` app pods show `1/1 Running`.
- The `mealdash` Ingress has an AWS load balancer hostname in its `ADDRESS` column.

Print the URL and check the database-aware health endpoint:

```bash
endpoint="$(kubectl get ingress mealdash -n mealdash -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
printf 'MealDash URL: http://%s/\n' "$endpoint"
curl -fsS "http://$endpoint/healthz"
```

Healthy output is:

```json
{"database":"reachable","status":"ok"}
```

Open the printed URL in a browser. Students can search restaurants, add food, place a simulated order (no payment is collected), and follow delivery status. Kitchen staff sign in at `/staff` with username `staff` and the password chosen in setup.

## After a full destroy: launch it again

Use this sequence after `destroy-lab.sh` finishes:

1. Keep using the same AWS account and region, and keep the S3 state bucket and GitHub OIDC provider.
2. On the mainserver, run `cd ~/mealdash-eks-capstone && git pull --ff-only`.
3. If `terraform/terraform.tfvars` still exists on that host, keep it. If using a new host, repeat Steps 4 and 5 to clone the repo and create the private tfvars file with GitHub IDs.
4. Run `bash scripts/start-lab.sh` and review the plan. Type `CREATE MEALDASH` only after confirming the correct account and resources.
5. Enter a staff password when prompted. The recreated RDS database starts empty and receives the sample restaurants at app startup.
6. Replace the GitHub environment `DB_HOST` with the newly printed RDS endpoint. Compare and refresh the other six variables from the script output as well. The role ARN usually stays the same when the account and role name stay the same, but use the value printed by Terraform.
7. Trigger **Actions > MealDash CI and deploy > Run workflow** on `main`.
8. Repeat the checks in Steps 11.

The application hostname may change after recreation. Always read the current Ingress hostname; do not reuse an old URL.

## Cleanup after class

Run this from the repository root:

```bash
bash scripts/destroy-lab.sh
```

Review the AWS identity shown by the script. Type the exact phrase `DESTROY MEALDASH` only when you intend to remove the MealDash VPC, EKS cluster, RDS database and its data, ECR repository, load balancer, and project IAM role/policy. The script waits for the ALB to disappear before removing the cluster.

When complete, keep the S3 state bucket and shared GitHub OIDC provider. Do not delete them from the console if you plan to relaunch this lab in the same account.

## Troubleshooting

| What you see | What to check |
| --- | --- |
| Terraform says it cannot find the GitHub OIDC provider | Check Step 3. Create the provider once in IAM if this account has never used GitHub OIDC. |
| Terraform asks for GitHub IDs or rejects `REPLACE_WITH` | Repeat Step 5 and update both ID values in `terraform/terraform.tfvars`. |
| `deploy` is skipped | Use `main` and `workflow_dispatch`, and check that the seven values are Environment variables in the `classroom` environment. |
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | Check the OIDC provider, repo IDs in tfvars, exact repo name/owner, and exact environment name `classroom`; then rerun setup/plan/apply and the workflow. |
| ECR image push returns 403 | Confirm the latest repo code is on `main` and the Terraform deploy role includes the `ecr:BatchGetImage` action; apply the Terraform update before retrying. |
| Kustomize says a base file is outside the overlay | Pull latest `main`. The workflow renders the classroom overlay with `kubectl kustomize` and applies the rendered manifests. |
| Pods show MySQL `Access denied` | Confirm you are on latest `main`. If the database was recreated or its credential changed, an instructor should refresh the Kubernetes Secrets from the current RDS-managed secret (commands below). Never print the password. |
| Pods remain unavailable | Run `kubectl describe pods -n mealdash -l app.kubernetes.io/name=mealdash` and `kubectl logs deployment/mealdash -n mealdash --all-pods=true --tail=100`. The workflow also prints these diagnostics if rollout fails. |
| No Ingress address appears | Check the AWS Load Balancer Controller pods: `kubectl get pods -n kube-system | grep aws-load-balancer-controller`. Ask the instructor to inspect controller logs and Ingress events. |
| Terraform plan includes unrelated resources or deletes | Do not approve. Confirm the AWS account, region, current branch, and S3 backend before continuing. |

### Instructor fix: refresh database and app credentials

Use this only if the database credential changed or pods report MySQL `Access denied`. Run from the repo root on the instructor mainserver. The script fetches the password from Secrets Manager without displaying it and prompts for the kitchen staff password again. Enter the same staff password if you want existing demo logins to keep working.

```bash
secret_arn="$(terraform -chdir=terraform output -raw rds_secret_arn)"
bash scripts/bootstrap-runtime-secrets.sh "$secret_arn"
kubectl rollout restart deployment/mealdash -n mealdash
kubectl rollout status deployment/mealdash -n mealdash --timeout=5m
```

## What this guide has and has not verified

The current repository has completed a live GitHub Actions deployment: both app replicas became Ready and the public `/healthz` endpoint returned `database: reachable`. The guide follows the current `start-lab.sh`, `destroy-lab.sh`, Terraform, and workflow code.

A fresh destroy-and-recreate cycle was not run while preparing this guide because it would delete the active classroom database and application. The repeat launch relies on retaining the remote S3 state bucket and shared GitHub OIDC provider as described above. AWS service availability, account quotas, permissions, and regional capacity can still affect a future run.

## Official references

- [GitHub Actions OIDC subject claims](https://docs.github.com/en/actions/reference/security/oidc)
- [AWS IAM OIDC identity providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [Amazon EKS access entries](https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html)
- [Terraform CLI documentation](https://developer.hashicorp.com/terraform/cli)
