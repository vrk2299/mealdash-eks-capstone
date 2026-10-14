# MealDash EKS Capstone

MealDash is the Project 3 food ordering and delivery demo. Customers browse seeded kitchens, add menu items to a one-restaurant cart, submit a simulated order without payment, and follow the order status. Kitchen staff use a protected board to accept, prepare, dispatch, and complete orders.

## Separate Project 3 environment

This repository creates a separate AWS VPC (`10.30.0.0/16`), EKS cluster (`mealdash`), worker group, private MySQL RDS database, ECR repository, IAM deploy role, Kubernetes namespace (`mealdash`), load balancer, and Terraform state. Project 2 uses `10.20.0.0/16`, cluster `eventpass`, and namespace `eventpass`. The names, network CIDRs, state, and billable application resources are distinct so both classroom demos can run side by side.

One AWS account-level identity resource is shared: GitHub's OIDC provider. AWS allows one provider for the GitHub Actions issuer per account. This stack reads the existing provider and creates its own repository-scoped role and EKS access entry. Do not destroy the Project 2 Terraform foundation while MealDash relies on that provider. If the projects need fully independent teardown, first move the shared provider into a small, separately managed IAM bootstrap stack and make both projects reference it.

This lab is deliberately small and disposable, not production food-commerce software. The ALB uses HTTP, MySQL is single-AZ with no retained backups, and the worker group starts at one small node. Use sample names/addresses only. Demo checkout records an order but never collects payment.

## What the class can demonstrate

- Search three seeded restaurants and menus.
- Add dishes from one kitchen to a session cart, review the total, and place a no-payment demo order.
- Follow the public tracking link through `PLACED`, `ACCEPTED`, `PREPARING`, `OUT_FOR_DELIVERY`, and `DELIVERED`.
- Sign in to the kitchen order board and advance a customer's order one state at a time.
- Trace a code change through GitHub Actions, immutable ECR image publishing, and an EKS rolling update.

## Run locally first

Requirements: Docker Desktop with Docker Compose.

1. Copy `.env.example` to `.env` and replace the local demo values.
2. Start the app and MySQL:

   ```bash
   docker compose up --build
   ```

3. Open `http://localhost:8080`. Browse kitchens, add food, place a demo order, and open `/staff` to move it through the delivery stages. Staff username is `staff`; password is `STAFF_PASSWORD` from `.env`.
4. Stop with Ctrl+C. `docker compose down` keeps the local database volume. `docker compose down --volumes` resets the local database.

## AWS resources and setup

Terraform targets `ap-south-1`, EKS Kubernetes `1.36`, one `t3.small` managed worker (maximum two), and a private single-AZ `db.t3.micro` MySQL database. The two-AZ VPC uses one NAT Gateway to keep the classroom footprint lower. ECR scans images on push and uses immutable tags. EKS control plane logs are retained for seven days.

AWS resources are not created until the launch script is run. EKS, RDS, NAT Gateway, ECR storage, and ALB incur charges while present. Review the plan and current AWS pricing before proceeding.

### Prerequisites

On the instructor host install AWS CLI v2, Terraform 1.5.7+, `kubectl`, Helm 3, `eksctl`, `curl`, `openssl`, Python 3, Docker, and Git. Configure an AWS identity authorized to create the listed resources and pass the EKS roles. Do not give students permanent administrator access.

Create a **separate public repository** named `mealdash-eks-capstone` under `vrk2299` and push its `main` branch. Retrieve immutable GitHub owner and repository IDs after creation. Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`, fill the numeric IDs, and keep that file private (it is ignored by Git).

```bash
git clone https://github.com/vrk2299/mealdash-eks-capstone.git
cd mealdash-eks-capstone
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
bash scripts/get-github-ids.sh vrk2299 mealdash-eks-capstone
```

Fill `github_owner_id` and `github_repository_id` in `terraform/terraform.tfvars`. Then run the guarded setup script. It shows a Terraform plan and requires the phrase `CREATE MEALDASH` before applying.

Get the numeric IDs with `bash scripts/get-github-ids.sh vrk2299 mealdash-eks-capstone` and copy the two values it prints into the tfvars file.

```bash
bash scripts/start-lab.sh
```

The script provisions the isolated network, cluster, RDS, ECR and IAM deploy role; waits for worker nodes; installs a MealDash-specific AWS Load Balancer Controller; creates the namespace and narrow deployer RoleBinding; and bootstraps runtime secrets. The RDS master password is retrieved from Secrets Manager on the instructor host and written into a Kubernetes Secret without printing it. The instructor enters a demo staff password privately.

### GitHub Actions setup

In the repository, create a GitHub Actions environment named `classroom`. Add these **repository variables** under Settings > Secrets and variables > Actions. Do not put AWS keys, the database password, or app secrets in GitHub.

| Variable | Value |
| --- | --- |
| `AWS_REGION` | `ap-south-1` |
| `AWS_DEPLOY_ROLE_ARN` | Terraform output `github_deployer_role_arn` |
| `EKS_CLUSTER_NAME` | `mealdash` |
| `ECR_REPOSITORY` | `mealdash` |
| `DB_HOST` | Terraform output `rds_endpoint` |
| `DB_NAME` | `mealdash` |
| `DB_USER` | `mealdash_admin` |

Pull requests build the container only. A push to `main` or `workflow_dispatch` can deploy when variables are present. GitHub Actions assumes a repository/environment-restricted AWS role via OIDC, pushes a unique immutable tag, applies a ConfigMap and the Kustomize workload, then waits for rollout. The workflow does not read runtime Kubernetes Secrets.

After the first successful deployment, get the temporary application URL:

```bash
kubectl get ingress mealdash -n mealdash
kubectl get pods,services,ingress -n mealdash
```

If you recreate RDS, update the GitHub `DB_HOST` variable from the new Terraform output. If you recreate EKS, run `start-lab.sh` and seed runtime secrets again before deploying.

## Cleanup after class

Run this from the repository root. It names the AWS identity and requires typing `DESTROY MEALDASH` before it deletes resources.

```bash
bash scripts/destroy-lab.sh
```

RDS is configured without a final snapshot, so destruction permanently deletes its data. Keep Terraform state until cleanup is confirmed. Verify no `mealdash` load balancers, NAT gateways, EBS volumes, database, ECR images, or tagged resources remain. The script does not delete the shared GitHub OIDC provider or the Project 2 stack.

## Repository map

| Path | Purpose |
| --- | --- |
| `app/` | Flask web app, customer flows, staff order board and styles |
| `terraform/` | Isolated MealDash VPC, EKS, RDS, ECR and GitHub deployment role |
| `k8s/` | Namespace bootstrap, namespaced RBAC, Deployment, Service and ALB Ingress |
| `.github/workflows/pipeline.yml` | Container validation and automated ECR/EKS deployment |
| `scripts/` | Launch, ALB controller, runtime secrets and destroy steps |
| `docker-compose.yml` | Local preview with MySQL 8.4 |

## Current classroom security tradeoffs

- Public ALB uses HTTP; add ACM TLS and managed DNS before public real use.
- EKS API public access is enabled without a source-CIDR restriction; narrow it to an instructor/admin address or use private connectivity for durable environments.
- Runtime Kubernetes Secret data is not encrypted by base64; enable EKS KMS envelope encryption and strict access controls for production.
- MySQL is private and allows port 3306 only from the EKS node security group, but is single-AZ and has no retained backups in this disposable setup.
- Use a throwaway staff password and synthetic order data. No real customer personal data or payments belong in this classroom app.
