#!/usr/bin/env bash
# Separate learning stack only. No IAM/app/backend/production mutations.
set -euo pipefail
umask 077
export AWS_PAGER=""
export AWS_CLI_AUTO_PROMPT=off
LAB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export STACK_NAME="${STACK_NAME:-clip-it-cloud-lab-seoul}"
REGION="ap-northeast-2"

usage() {
  cat <<'USAGE'
Usage: ./infra/cloud-lab/lab.sh preflight|deploy|status|verify|cleanup
  AWS_PROFILE             Named IAM profile (optional if a role supplies credentials)
  AWS_REGION              ap-northeast-2 only (AWS_DEFAULT_REGION must also match if set)
  STACK_NAME              clip-it-cloud-lab-* (default: clip-it-cloud-lab-seoul)
Deploy / preflight additionally require:
  SSH_CIDR                Learner's current public IPv4 /32
  KEY_PAIR_NAME           Existing key in Seoul; OR
  SSH_PUBLIC_KEY_FILE     Local OpenSSH RSA/ED25519 public key (private key never uploaded)
  FREE_TIER_CONFIRMED=yes  Console cost/credit check acknowledged; API checks still run
Verify additionally requires:
  SSH_PRIVATE_KEY_FILE    Local matching private key (used by ssh; never uploaded)
Raw AWS output is kept in infra/cloud-lab/.local (ignored, mode 700/600).
Read infra/cloud-lab/README.md before deploy. Deploy creates billable-capable resources.
USAGE
}
error() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || error "Missing prerequisite: $1"; }
py() { python3 "$LAB_DIR/support.py" "$@"; }

init() {
  need aws; need python3
  [[ "$STACK_NAME" =~ ^clip-it-cloud-lab-[a-z0-9][a-z0-9-]{0,42}$ ]] || error "STACK_NAME must use the clip-it-cloud-lab- prefix and lowercase letters/digits/hyphens."
  [[ "${AWS_REGION:-$REGION}" == "$REGION" ]] || error "AWS_REGION must be ap-northeast-2 (Seoul)."
  [[ "${AWS_DEFAULT_REGION:-$REGION}" == "$REGION" ]] || error "AWS_DEFAULT_REGION must be ap-northeast-2 (Seoul)."
  # When no explicit environment region is set, reject a conflicting profile default.
  local configured
  configured="$(aws configure get region 2>/dev/null || true)"
  if [[ -z "${AWS_REGION:-}" && -z "${AWS_DEFAULT_REGION:-}" && -n "$configured" && "$configured" != "$REGION" ]]; then
    error "The selected AWS profile defaults to another region. Explicitly select AWS_REGION=ap-northeast-2."
  fi
  [[ "$(aws --version 2>&1)" == aws-cli/2.* ]] || error "AWS CLI v2 is required; use a current version with freetier get-account-plan-state."
  AWS=(aws --region "$REGION" --no-cli-pager)
  BILLING_AWS=(aws --region us-east-1 --no-cli-pager)
  # Free Tier is an account-wide read API with a us-east-1 signing endpoint.
  RUN_DIR="$LAB_DIR/.local/$STACK_NAME"
  mkdir -p -- "$RUN_DIR"
  chmod 700 "$LAB_DIR/.local" "$RUN_DIR"
  "${AWS[@]}" sts get-caller-identity --output json > "$RUN_DIR/identity.json"
  ACCOUNT="$(py identity "$RUN_DIR/identity.json")"
}

read_stack() {
  "${AWS[@]}" cloudformation describe-stacks --stack-name "$STACK_NAME" --output json > "$RUN_DIR/stack.json"
  py stack "$RUN_DIR/stack.json"
}

preflight() {
  local cidr ami existing
  cidr="$(py cidr)"
  need ssh-keygen
  py key "$RUN_DIR/key-selection.json"
  existing="$(py field "$RUN_DIR/key-selection.json" existing)"
  if [[ -n "$existing" ]]; then
    "${AWS[@]}" ec2 describe-key-pairs --key-names "$existing" --output json > "$RUN_DIR/existing-key.json"
  fi
  python3 "$LAB_DIR/render-template.py" --check
  "${AWS[@]}" cloudformation validate-template --template-body "file://$LAB_DIR/cloudformation.json" --output json > "$RUN_DIR/template-validation.json"
  "${AWS[@]}" ec2 describe-instance-types --instance-types t3.micro --output json > "$RUN_DIR/instance-type.json"
  py instance-type "$RUN_DIR/instance-type.json"
  "${AWS[@]}" ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --output json > "$RUN_DIR/ami-parameter.json"
  ami="$(py field "$RUN_DIR/ami-parameter.json" Parameter.Value)"
  "${AWS[@]}" ec2 describe-images --owners amazon --image-ids "$ami" --output json > "$RUN_DIR/ami.json"
  ami="$(py image "$RUN_DIR/ami.json")"
  "${BILLING_AWS[@]}" freetier get-account-plan-state --output json > "$RUN_DIR/free-tier-plan.json" 2> "$RUN_DIR/free-tier-plan.error.txt" || error "Free Tier status could not be checked. Ask the account owner to grant read-only freetier:GetAccountPlanState or update AWS CLI. No resources were created."
  "${BILLING_AWS[@]}" freetier get-free-tier-usage --output json > "$RUN_DIR/free-tier-usage.json" 2> "$RUN_DIR/free-tier-usage.error.txt" || error "Free Tier usage could not be checked. No resources were created."
  py cost "$RUN_DIR/free-tier-plan.json" "$ACCOUNT" "$RUN_DIR/cost-check.redacted.json"
  py parameters "$RUN_DIR/parameters.json" "$RUN_DIR/key-selection.json" "$ami"
  printf 'Preflight passed: Seoul, IAM principal, public /32 SSH, one SSH key, checked AL2023/t3.micro, active credits and acknowledged cost review.\n'
}

deploy() {
  preflight
  # Only a new stack is created; this command never updates a pre-existing stack.
  if "${AWS[@]}" cloudformation describe-stacks --stack-name "$STACK_NAME" --output json > "$RUN_DIR/existing-stack.json" 2> "$RUN_DIR/existing-stack.error.txt"; then
    error "A stack with this name exists. Use status/verify/cleanup; deploy never modifies it."
  fi
  # Distinguish not-found from authorization/network failures before any mutation.
  python3 - "$RUN_DIR/existing-stack.error.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
if "ValidationError" not in text or "does not exist" not in text:
    sys.exit("ERROR: Could not establish that the lab stack is absent. No resources were created.")
PY
  py new-state "$RUN_DIR/state.json" "$ACCOUNT"
  "${AWS[@]}" cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body "file://$LAB_DIR/cloudformation.json" \
    --parameters "file://$RUN_DIR/parameters.json" \
    --resource-types AWS::EC2::VPC AWS::EC2::InternetGateway AWS::EC2::VPCGatewayAttachment AWS::EC2::Subnet AWS::EC2::RouteTable AWS::EC2::Route AWS::EC2::SubnetRouteTableAssociation AWS::EC2::SecurityGroup AWS::EC2::KeyPair AWS::EC2::Instance \
    --tags Key=CloudLab,Value=clip-it-assignment "Key=LabStack,Value=$STACK_NAME" \
    --on-failure ROLLBACK --output json > "$RUN_DIR/create-stack.json"
  py bind-state "$RUN_DIR/state.json" "$RUN_DIR/create-stack.json"
  printf 'Lab stack creation requested. Waiting for CloudFormation; Nginx readiness is checked separately.\n'
  if ! "${AWS[@]}" cloudformation wait stack-create-complete --stack-name "$STACK_NAME"; then
    "${AWS[@]}" cloudformation describe-stack-events --stack-name "$STACK_NAME" --output json > "$RUN_DIR/create-events.json" || true
    error "Stack did not complete. Inspect private .local create-events.json and run cleanup for this lab stack."
  fi
  status
  printf 'Allow cloud-init a few minutes, then run: ./infra/cloud-lab/lab.sh verify\n'
}

status() {
  read_stack
  printf 'Stack status: %s\n' "$(py field "$RUN_DIR/stack.json" Stacks.0.StackStatus)"
  local website
  website="$(py output "$RUN_DIR/stack.json" WebsiteUrl 2>/dev/null || true)"
  [[ -z "$website" ]] || printf 'Website: %s\nHealth: %shealth\n' "$website" "$website"
  printf 'Private AWS details: %s\n' "$RUN_DIR"
}

verify() {
  need curl; need ssh
  [[ -n "${SSH_PRIVATE_KEY_FILE:-}" && -f "$SSH_PRIVATE_KEY_FILE" ]] || error "Set SSH_PRIVATE_KEY_FILE to the matching local private key for required SSH verification."
  read_stack
  local instance vpc subnet routes sg ip
  instance="$(py output "$RUN_DIR/stack.json" InstanceId)"
  vpc="$(py output "$RUN_DIR/stack.json" VpcId)"
  subnet="$(py output "$RUN_DIR/stack.json" SubnetId)"
  routes="$(py output "$RUN_DIR/stack.json" RouteTableId)"
  sg="$(py output "$RUN_DIR/stack.json" SecurityGroupId)"
  ip="$(py output "$RUN_DIR/stack.json" PublicIp)"
  "${AWS[@]}" ec2 describe-instances --instance-ids "$instance" --output json > "$RUN_DIR/instances.json"
  "${AWS[@]}" ec2 describe-instance-credit-specifications --instance-ids "$instance" --output json > "$RUN_DIR/credits.json"
  "${AWS[@]}" ec2 describe-volumes --filters "Name=attachment.instance-id,Values=$instance" --output json > "$RUN_DIR/volumes.json"
  "${AWS[@]}" ec2 describe-vpcs --vpc-ids "$vpc" --output json > "$RUN_DIR/vpc.json"
  "${AWS[@]}" ec2 describe-subnets --subnet-ids "$subnet" --output json > "$RUN_DIR/subnet.json"
  "${AWS[@]}" ec2 describe-route-tables --route-table-ids "$routes" --output json > "$RUN_DIR/routes.json"
  "${AWS[@]}" ec2 describe-security-groups --group-ids "$sg" --output json > "$RUN_DIR/security-group.json"
  local health_meta homepage_meta login_status
  # No authentication is sent, redirects are not followed, and no proxy env is used.
  health_meta="$(curl --noproxy '*' --silent --show-error --connect-timeout 10 --max-time 20 --dump-header "$RUN_DIR/health-headers.txt" --output "$RUN_DIR/health-body.txt" --write-out '%{http_code} %{content_type}' "http://$ip/health")"
  homepage_meta="$(curl --noproxy '*' --silent --show-error --connect-timeout 10 --max-time 30 --output "$RUN_DIR/homepage.html" --write-out '%{http_code}' "http://$ip/")"
  login_status="$(curl --noproxy '*' --silent --show-error --connect-timeout 10 --max-time 20 --dump-header "$RUN_DIR/login-headers.txt" --output /dev/null --write-out '%{http_code}' "http://$ip/login")"
  python3 - "$RUN_DIR" "$health_meta" "$homepage_meta" "$login_status" <<'PY'
from pathlib import Path
import json, sys
p = Path(sys.argv[1])
health = sys.argv[2].split(' ', 1)
headers = (p / 'login-headers.txt').read_text().splitlines()
location = next((line.split(':', 1)[1].strip() for line in headers if line.lower().startswith('location:')), '')
(p / 'http.json').write_text(json.dumps({'healthStatus': int(health[0]), 'healthContentType': health[1] if len(health) > 1 else '', 'homepageStatus': int(sys.argv[3]), 'loginStatus': int(sys.argv[4]), 'loginLocation': location}, indent=2) + '\n')
PY
  # accept-new records the first host key and rejects a changed one on later runs.
  # The private key remains local; stdin contains only this fixed diagnostic script.
  ssh -i "$SSH_PRIVATE_KEY_FILE" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -o "UserKnownHostsFile=$RUN_DIR/known_hosts" \
    -o ConnectTimeout=10 -o ConnectionAttempts=1 -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=2 "ec2-user@$ip" 'bash -s' \
    > "$RUN_DIR/ssh-verification.json" 2> "$RUN_DIR/ssh-verification.error.txt" <<'REMOTE'
set -euo pipefail
systemctl is-active --quiet nginx
sudo nginx -t > /dev/null 2>&1
[[ "$(curl --noproxy '*' --fail --silent --show-error --connect-timeout 10 --max-time 20 http://127.0.0.1/health)" == 'OK' ]]
[[ "$(curl --noproxy '*' --silent --show-error --connect-timeout 10 --max-time 30 --output /dev/null --write-out '%{http_code}' http://127.0.0.1/)" == '200' ]]
[[ "$(curl --noproxy '*' --silent --show-error --connect-timeout 10 --max-time 30 --output /dev/null --write-out '%{http_code}' https://example.com/)" == '200' ]]
printf '{"sshConnected":true,"nginxActive":true,"nginxConfigValid":true,"localhostHealthOk":true,"localhostHomepage200":true,"outboundHttps200":true}\n'
REMOTE
  py verify "$RUN_DIR"
  printf 'Verified summary without account IDs/ARNs/IPs: %s/verification-summary.redacted.json\n' "$RUN_DIR"
}

cleanup() {
  [[ -f "$RUN_DIR/state.json" ]] || error "No local create record. Refusing cleanup of an untracked stack."
  read_stack
  py owned-state "$RUN_DIR/state.json" "$RUN_DIR/stack.json" "$ACCOUNT"
  # Delete by exact StackId, so a new stack of the same name cannot be targeted.
  local stack_id imported
  stack_id="$(py field "$RUN_DIR/stack.json" Stacks.0.StackId)"
  imported="$STACK_NAME-ssh"
  "${AWS[@]}" cloudformation delete-stack --stack-name "$stack_id"
  printf 'Deletion requested only for the tracked lab stack. Waiting for deletion.\n'
  if ! "${AWS[@]}" cloudformation wait stack-delete-complete --stack-name "$stack_id"; then
    "${AWS[@]}" cloudformation describe-stack-events --stack-name "$stack_id" --output json > "$RUN_DIR/delete-events.json" || true
    error "Cleanup not complete. Inspect private delete-events.json; no unrelated resources will be deleted."
  fi
  "${AWS[@]}" ec2 describe-instances --filters Name=tag:CloudLab,Values=clip-it-assignment "Name=tag:LabStack,Values=$STACK_NAME" --output json > "$RUN_DIR/cleanup-instances.json"
  "${AWS[@]}" ec2 describe-volumes --filters Name=tag:CloudLab,Values=clip-it-assignment "Name=tag:LabStack,Values=$STACK_NAME" --output json > "$RUN_DIR/cleanup-volumes.json"
  "${AWS[@]}" ec2 describe-vpcs --filters Name=tag:CloudLab,Values=clip-it-assignment "Name=tag:LabStack,Values=$STACK_NAME" --output json > "$RUN_DIR/cleanup-vpc.json"
  "${AWS[@]}" ec2 describe-internet-gateways --filters Name=tag:CloudLab,Values=clip-it-assignment "Name=tag:LabStack,Values=$STACK_NAME" --output json > "$RUN_DIR/cleanup-igw.json"
  "${AWS[@]}" ec2 describe-subnets --filters Name=tag:CloudLab,Values=clip-it-assignment "Name=tag:LabStack,Values=$STACK_NAME" --output json > "$RUN_DIR/cleanup-subnets.json"
  "${AWS[@]}" ec2 describe-route-tables --filters Name=tag:CloudLab,Values=clip-it-assignment "Name=tag:LabStack,Values=$STACK_NAME" --output json > "$RUN_DIR/cleanup-routes.json"
  "${AWS[@]}" ec2 describe-security-groups --filters Name=tag:CloudLab,Values=clip-it-assignment "Name=tag:LabStack,Values=$STACK_NAME" --output json > "$RUN_DIR/cleanup-sg.json"
  if [[ "$(py field "$RUN_DIR/state.json" importedKey)" == 'True' ]]; then
    "${AWS[@]}" ec2 describe-key-pairs --filters "Name=key-name,Values=$imported" --output json > "$RUN_DIR/cleanup-key.json"
  else
    printf '{"KeyPairs":[], "existingKeyNotTargeted":true}\n' > "$RUN_DIR/cleanup-key.json"
  fi
  py cleanup-summary "$RUN_DIR"
  printf 'Cleanup verified for the tracked lab stack. Existing key pairs and original hosting were not targeted.\nRedacted summary: %s/cleanup-summary.redacted.json\n' "$RUN_DIR"
}

case "${1:-}" in
  -h|--help|help) usage ;;
  preflight|deploy|status|verify|cleanup)
    [[ $# -eq 1 ]] || error "This command accepts environment configuration, not extra arguments."
    init
    "$1"
    ;;
  *) usage; exit 1 ;;
esac
