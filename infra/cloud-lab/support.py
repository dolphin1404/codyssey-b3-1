#!/usr/bin/env python3
"""Private local state and validation helpers. Never prints credentials or ARNs."""
import argparse
import base64
import datetime as dt
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
LAB = "clip-it-assignment"
REGION = "ap-northeast-2"


def fail(message):
    raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    Path(path).chmod(0o600)


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def validate_identity(path):
    identity = read(path)
    arn = identity.get("Arn", "")
    account = identity.get("Account", "")
    if not re.fullmatch(r"\d{12}", account) or not arn.startswith("arn:aws:"):
        fail("A valid IAM user/role in the standard AWS partition is required.")
    if arn.endswith(":root"):
        fail("AWS root credentials are rejected. Use the scoped IAM lab operator.")
    if ":user/" not in arn and ":assumed-role/" not in arn and ":federated-user/" not in arn:
        fail("Use an IAM user or assumed/federated role for the lab.")
    return account


def validate_cidr(value):
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        fail("SSH_CIDR must be the learner's current public IPv4 address followed by /32.")
    if network.version != 4 or network.prefixlen != 32 or not network.network_address.is_global:
        fail("SSH_CIDR must be a public IPv4 /32; empty, broad, private and reserved ranges are rejected.")
    return str(network)


def validate_key():
    existing = os.environ.get("KEY_PAIR_NAME", "")
    key_file = os.environ.get("SSH_PUBLIC_KEY_FILE", "")
    if bool(existing) == bool(key_file):
        fail("Set exactly one of KEY_PAIR_NAME or SSH_PUBLIC_KEY_FILE.")
    if existing:
        if len(existing) > 255 or existing != existing.strip() or not existing.isascii() or "\n" in existing:
            fail("KEY_PAIR_NAME must be a valid existing EC2 key pair name.")
        return existing, ""
    path = Path(key_file).expanduser().resolve()
    text = path.read_text().strip()
    if not re.fullmatch(r"ssh-(rsa|ed25519) [A-Za-z0-9+/]+={0,3}( [^\r\n]*)?", text):
        fail("SSH_PUBLIC_KEY_FILE must contain one OpenSSH RSA/ED25519 public key. Private keys are rejected.")
    try:
        base64.b64decode(text.split()[1], validate=True)
    except ValueError:
        fail("Malformed public SSH key.")
    result = subprocess.run(["ssh-keygen", "-l", "-f", str(path)], capture_output=True, text=True)
    if result.returncode:
        fail("ssh-keygen rejected the public SSH key.")
    # Drop the optional comment (often a personal email) from stack parameters.
    return "", " ".join(text.split()[:2])


def stack(path):
    values = read(path).get("Stacks", [])
    if len(values) != 1:
        fail("Expected exactly one CloudFormation stack.")
    value = values[0]
    tags = {v["Key"]: v["Value"] for v in value.get("Tags", [])}
    if tags.get("CloudLab") != LAB or tags.get("LabStack") != os.environ["STACK_NAME"]:
        fail("This is not the named lab-owned stack. Refusing access/cleanup.")
    return value


def outputs(path):
    return {v["OutputKey"]: v["OutputValue"] for v in stack(path).get("Outputs", [])}


def assert_cost(path, account):
    plan = read(path)
    if plan.get("accountId") != account:
        fail("Free Tier response does not match the current AWS account.")
    if plan.get("accountPlanStatus") != "ACTIVE" or plan.get("accountPlanType") not in {"FREE", "PAID"}:
        fail("No active Free Tier account plan was verified. Deployment is blocked.")
    credits = plan.get("accountPlanRemainingCredits", {})
    amount = credits.get("amount")
    if credits.get("unit") != "USD" or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0:
        fail("No positive Free Tier credit balance was verified. Deployment is blocked.")
    expiry = plan.get("accountPlanExpirationDate")
    if plan.get("accountPlanType") == "FREE" and not expiry:
        fail("Free plan expiration could not be checked. Deployment is blocked.")
    if expiry and dt.datetime.fromisoformat(expiry.replace("Z", "+00:00")) <= dt.datetime.now(dt.timezone.utc):
        fail("The account plan expiration date has passed. Deployment is blocked.")
    if os.environ.get("FREE_TIER_CONFIRMED") != "yes":
        fail("Review Billing/Free Tier and credit applicability for EC2, 8 GiB gp3, public IPv4 and transfer first. Then set FREE_TIER_CONFIRMED=yes; this acknowledges the check, not a zero-cost promise.")
    return {"checkedAt": timestamp(), "activePlan": True, "positiveCredits": True, "consoleCostReviewAcknowledged": True}


def image(path):
    values = read(path).get("Images", [])
    if len(values) != 1:
        fail("Expected one Amazon Linux image.")
    value = values[0]
    if not (value.get("Architecture") == "x86_64" and value.get("State") == "available" and value.get("RootDeviceName") == "/dev/xvda" and value.get("Name", "").startswith("al2023-ami-") and value.get("FreeTierEligible") is True):
        fail("The AMI is not the checked AL2023 x86_64, /dev/xvda, available, FreeTierEligible image.")
    if value.get("ProductCodes"):
        fail("Marketplace images are not allowed.")
    return value["ImageId"]


def verify(directory):
    d = Path(directory)
    s = stack(d / "stack.json")
    out = outputs(d / "stack.json")
    params = {p["ParameterKey"]: p.get("ParameterValue") for p in s.get("Parameters", [])}
    expected_ssh = validate_cidr(params.get("SshAllowedCidr", ""))
    checks = {}
    def check(name, value):
        checks[name] = bool(value)
    instance = read(d / "instances.json")["Reservations"][0]["Instances"][0]
    check("stack_complete_in_seoul", s["StackStatus"] == "CREATE_COMPLETE" and out.get("Region") == REGION)
    check("instance_running_t3_micro", instance["State"]["Name"] == "running" and instance["InstanceType"] == "t3.micro")
    check("instance_in_lab_network", instance["VpcId"] == out["VpcId"] and instance["SubnetId"] == out["SubnetId"])
    check("public_ipv4", instance.get("PublicIpAddress") == out["PublicIp"] and ipaddress.ip_address(out["PublicIp"]).version == 4)
    check("checked_ami", instance["ImageId"] == params["AmazonLinuxAmiId"] and instance.get("Architecture") == "x86_64")
    check("imds_v2", instance.get("MetadataOptions", {}).get("HttpTokens") == "required")
    credits = read(d / "credits.json")["InstanceCreditSpecifications"]
    check("standard_cpu_credits", len(credits) == 1 and credits[0]["CpuCredits"] == "standard")
    vol = read(d / "volumes.json")["Volumes"]
    mappings = instance.get("BlockDeviceMappings", [])
    check("one_encrypted_gp3_8_gib_root", len(vol) == 1 and vol[0]["Size"] == 8 and vol[0]["VolumeType"] == "gp3" and vol[0]["Encrypted"] is True)
    check("root_deleted_on_termination", len(mappings) == 1 and mappings[0]["Ebs"].get("DeleteOnTermination") is True)
    vpc = read(d / "vpc.json")["Vpcs"][0]
    subnet = read(d / "subnet.json")["Subnets"][0]
    check("vpc_cidr", vpc["CidrBlock"] == "10.20.0.0/16")
    check("public_subnet_cidr", subnet["CidrBlock"] == "10.20.1.0/24" and subnet.get("MapPublicIpOnLaunch") is True)
    routes = read(d / "routes.json")["RouteTables"][0]
    check("internet_default_route", any(r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("GatewayId") == out["InternetGatewayId"] and r.get("State") == "active" for r in routes["Routes"]))
    check("subnet_route_associated", any(a.get("SubnetId") == out["SubnetId"] for a in routes["Associations"]))
    groups = read(d / "security-group.json")["SecurityGroups"]
    actual = []
    for rule in groups[0].get("IpPermissions", []):
        if rule.get("Ipv6Ranges") or rule.get("UserIdGroupPairs") or rule.get("PrefixListIds"):
            actual.append(("unexpected_source",))
        for ip in rule.get("IpRanges", []):
            actual.append((rule.get("IpProtocol"), rule.get("FromPort"), rule.get("ToPort"), ip["CidrIp"]))
    check("only_http_world_and_ssh_learner", sorted(actual, key=str) == sorted([("tcp", 80, 80, "0.0.0.0/0"), ("tcp", 22, 22, expected_ssh)], key=str))
    check("only_lab_security_group", [g["GroupId"] for g in instance["SecurityGroups"]] == [out["SecurityGroupId"]])
    health = read(d / "http.json")
    check("health_exact_200_plain_ok", health["healthStatus"] == 200 and health["healthContentType"].lower().startswith("text/plain") and (d / "health-body.txt").read_bytes() == b"OK\n")
    check("homepage_200", health["homepageStatus"] == 200)
    check("login_redirects_to_https_origin", health["loginStatus"] == 308 and health["loginLocation"] == "https://cbnu-clip-it.vercel.app/login")
    ssh = read(d / "ssh-verification.json")
    check("ssh_nginx_localhost_outbound", all(ssh.get(k) is True for k in ["sshConnected", "nginxActive", "nginxConfigValid", "localhostHealthOk", "localhostHomepage200", "outboundHttps200"]))
    summary = {"checkedAt": timestamp(), "source": "AWS API + public HTTP + SSH/localhost/outbound checks", "region": REGION, "cloudVerified": all(checks.values()), "checks": checks, "deploymentModel": "EC2 Nginx public showcase proxy; original app/backend remain on existing hosting"}
    write(d / "verification-summary.redacted.json", summary)
    for name, ok in checks.items():
        print(("PASS " if ok else "FAIL ") + name)
    if not all(checks.values()):
        fail("Lab verification failed; inspect private .local evidence. Do not submit an unverified completion claim.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    parser.add_argument("args", nargs="*")
    ns = parser.parse_args()
    c, a = ns.command, ns.args
    if c == "identity":
        print(validate_identity(a[0]))
    elif c == "cidr":
        print(validate_cidr(os.environ.get("SSH_CIDR", "")))
    elif c == "key":
        existing, public = validate_key()
        write(a[0], {"existing": existing, "public": public})
    elif c == "cost":
        write(a[2], assert_cost(a[0], a[1]))
    elif c == "image":
        print(image(a[0]))
    elif c == "instance-type":
        values = read(a[0]).get("InstanceTypes", [])
        if len(values) != 1 or values[0].get("InstanceType") != "t3.micro" or values[0].get("FreeTierEligible") is not True:
            fail("AWS did not mark t3.micro as FreeTierEligible in Seoul. Deployment is blocked.")
    elif c == "parameters":
        key = read(a[1])
        write(a[0], [{"ParameterKey": k, "ParameterValue": v} for k, v in {"AmazonLinuxAmiId": a[2], "SshAllowedCidr": validate_cidr(os.environ.get("SSH_CIDR", "")), "ExistingKeyPairName": key["existing"], "SshPublicKeyMaterial": key["public"]}.items()])
    elif c == "field":
        value = read(a[0])
        for part in a[1].split("."):
            value = value[int(part)] if isinstance(value, list) else value[part]
        print(value)
    elif c == "output":
        print(outputs(a[0])[a[1]])
    elif c == "stack":
        stack(a[0])
    elif c == "new-state":
        write(a[0], {"account": a[1], "region": REGION, "stackName": os.environ["STACK_NAME"], "attemptedAt": timestamp(), "templateSha256": hashlib.sha256((HERE / "cloudformation.json").read_bytes()).hexdigest(), "importedKey": bool(read(Path(a[0]).parent / "key-selection.json")["public"])})
    elif c == "bind-state":
        value = read(a[0])
        value["stackId"] = read(a[1])["StackId"]
        write(a[0], value)
    elif c == "owned-state":
        value = read(a[0])
        s = stack(a[1])
        if value.get("account") != a[2] or value.get("region") != REGION or value.get("stackName") != s["StackName"]:
            fail("Private deployment state does not match this account/region/stack.")
        if not value.get("stackId"):
            fail("No exact StackId was saved. Refusing cleanup; recover the create response or verify the lab stack manually in CloudFormation first.")
        if value["stackId"] != s["StackId"]:
            fail("Stack was replaced since this lab run; refusing cleanup.")
        created = dt.datetime.fromisoformat(s["CreationTime"].replace("Z", "+00:00"))
        attempted = dt.datetime.fromisoformat(value["attemptedAt"])
        if created < attempted - dt.timedelta(seconds=5):
            fail("Stack predates this lab's create attempt; refusing cleanup.")
    elif c == "verify":
        verify(a[0])
    elif c == "cleanup-summary":
        d = Path(a[0])
        instances = [i for r in read(d / "cleanup-instances.json").get("Reservations", []) for i in r.get("Instances", []) if i["State"]["Name"] != "terminated"]
        checks = {"no_live_lab_instances": not instances, "no_lab_volumes": not read(d / "cleanup-volumes.json").get("Volumes"), "no_lab_vpc": not read(d / "cleanup-vpc.json").get("Vpcs"), "no_imported_lab_key": not read(d / "cleanup-key.json").get("KeyPairs"), "no_lab_igw": not read(d / "cleanup-igw.json").get("InternetGateways"), "no_lab_subnets": not read(d / "cleanup-subnets.json").get("Subnets"), "no_lab_route_tables": not read(d / "cleanup-routes.json").get("RouteTables"), "no_lab_security_groups": not read(d / "cleanup-sg.json").get("SecurityGroups")}
        write(d / "cleanup-summary.redacted.json", {"checkedAt": timestamp(), "region": REGION, "stackDeleteWaiterSucceeded": True, "checks": checks, "cleanupVerified": all(checks.values())})
        if not all(checks.values()):
            fail("Stack deletion completed, but lab-tagged leftovers were found. Inspect private evidence; do not delete unrelated resources.")
    else:
        fail("Unknown helper command.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, OSError, TypeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
