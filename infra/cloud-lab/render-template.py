#!/usr/bin/env python3
"""Generate CloudFormation JSON with the reviewed nginx.conf embedded verbatim."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def ref(name):
    return {"Ref": name}


def sub(value):
    return {"Fn::Sub": value}


def tags(name):
    return [
        {"Key": "Name", "Value": sub("${AWS::StackName}-" + name)},
        {"Key": "CloudLab", "Value": "clip-it-assignment"},
        {"Key": "LabStack", "Value": ref("AWS::StackName")},
    ]


def template():
    nginx = (HERE / "nginx.conf").read_text()
    bootstrap = "\n".join([
        "#!/bin/bash",
        "set -euo pipefail",
        "dnf install -y nginx ca-certificates",
        "ln -sf /etc/pki/tls/certs/ca-bundle.crt /etc/ssl/certs/ca-certificates.crt",
        "# Replace the packaged default server; it otherwise competes on port 80.",
        "cat > /etc/nginx/nginx.conf <<'NGINX_MAIN'",
        "user nginx;",
        "worker_processes auto;",
        "error_log /var/log/nginx/error.log;",
        "pid /run/nginx.pid;",
        "include /usr/share/nginx/modules/*.conf;",
        "events { worker_connections 1024; }",
        "http {",
        "    include /etc/nginx/mime.types;",
        "    default_type application/octet-stream;",
        "    sendfile on;",
        "    keepalive_timeout 65;",
        "    access_log /var/log/nginx/access.log;",
        "    include /etc/nginx/conf.d/*.conf;",
        "}",
        "NGINX_MAIN",
        "cat > /etc/nginx/conf.d/cloud-lab.conf <<'NGINX_LAB'",
        nginx.rstrip(),
        "NGINX_LAB",
        "nginx -t",
        "systemctl enable --now nginx",
        "curl --fail --silent http://127.0.0.1/health",
        "",
    ])
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Isolated Seoul cloud lab: public Nginx showcase of the existing ClipIt Vercel app, plus local /health. No app/backend migration.",
        "Metadata": {"CloudLab": "clip-it-assignment", "Upstream": "https://cbnu-clip-it.vercel.app"},
        "Parameters": {
            "AmazonLinuxAmiId": {"Type": "AWS::EC2::Image::Id", "Description": "Seoul Amazon-owned AL2023 x86_64 AMI resolved and checked by lab.sh."},
            "SshAllowedCidr": {
                "Type": "String",
                "Description": "Learner's current public IPv4 /32 only. Never 0.0.0.0/0.",
                "AllowedPattern": r"^((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])/32$",
                "ConstraintDescription": "Provide a single valid IPv4 address with /32.",
            },
            "ExistingKeyPairName": {"Type": "String", "Default": "", "MaxLength": 255, "Description": "Existing Seoul EC2 key pair name; mutually exclusive with SshPublicKeyMaterial."},
            "SshPublicKeyMaterial": {
                "Type": "String", "Default": "", "NoEcho": True,
                "AllowedPattern": r"^$|^ssh-(rsa|ed25519) [A-Za-z0-9+/]+={0,3}( [^\r\n]*)?$",
                "Description": "OpenSSH public key only; imports a lab-owned key pair. Never paste a private key.",
            },
        },
        "Rules": {
            "ExactlyOneSshKey": {"Assertions": [{
                "Assert": {"Fn::Or": [
                    {"Fn::And": [{"Fn::Equals": [ref("ExistingKeyPairName"), ""]}, {"Fn::Not": [{"Fn::Equals": [ref("SshPublicKeyMaterial"), ""]}]}]},
                    {"Fn::And": [{"Fn::Not": [{"Fn::Equals": [ref("ExistingKeyPairName"), ""]}]}, {"Fn::Equals": [ref("SshPublicKeyMaterial"), ""]}]},
                ]},
                "AssertDescription": "Supply exactly one existing key pair or one OpenSSH public key.",
            }]},
        },
        "Conditions": {"ImportPublicKey": {"Fn::Not": [{"Fn::Equals": [ref("SshPublicKeyMaterial"), ""]}]}},
        "Resources": {
            "LabVpc": {"Type": "AWS::EC2::VPC", "Properties": {
                "CidrBlock": "10.20.0.0/16", "EnableDnsSupport": True, "EnableDnsHostnames": True,
                "InstanceTenancy": "default", "Tags": tags("vpc"),
            }},
            "InternetGateway": {"Type": "AWS::EC2::InternetGateway", "Properties": {"Tags": tags("igw")}},
            "GatewayAttachment": {"Type": "AWS::EC2::VPCGatewayAttachment", "Properties": {
                "VpcId": ref("LabVpc"), "InternetGatewayId": ref("InternetGateway"),
            }},
            "PublicSubnet": {"Type": "AWS::EC2::Subnet", "Properties": {
                "VpcId": ref("LabVpc"), "CidrBlock": "10.20.1.0/24", "MapPublicIpOnLaunch": True,
                "AvailabilityZone": {"Fn::Select": [0, {"Fn::GetAZs": ref("AWS::Region")}]},
                "Tags": tags("public-subnet"),
            }},
            "PublicRouteTable": {"Type": "AWS::EC2::RouteTable", "Properties": {
                "VpcId": ref("LabVpc"), "Tags": tags("public-routes"),
            }},
            "DefaultInternetRoute": {"Type": "AWS::EC2::Route", "DependsOn": "GatewayAttachment", "Properties": {
                "RouteTableId": ref("PublicRouteTable"), "DestinationCidrBlock": "0.0.0.0/0",
                "GatewayId": ref("InternetGateway"),
            }},
            "PublicRouteAssociation": {"Type": "AWS::EC2::SubnetRouteTableAssociation", "Properties": {
                "SubnetId": ref("PublicSubnet"), "RouteTableId": ref("PublicRouteTable"),
            }},
            "WebSecurityGroup": {"Type": "AWS::EC2::SecurityGroup", "Properties": {
                "GroupDescription": "ClipIt lab: public HTTP; learner public IPv4 /32 SSH only",
                "VpcId": ref("LabVpc"), "Tags": tags("web-sg"),
                "SecurityGroupIngress": [
                    {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "CidrIp": "0.0.0.0/0", "Description": "Public assignment website and health"},
                    {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "CidrIp": ref("SshAllowedCidr"), "Description": "Learner current public IPv4 only"},
                ],
                "SecurityGroupEgress": [
                    {"IpProtocol": "-1", "CidrIp": "0.0.0.0/0", "Description": "Package installation, DNS, HTTPS origin"},
                ],
            }},
            "ImportedSshKey": {"Type": "AWS::EC2::KeyPair", "Condition": "ImportPublicKey", "Properties": {
                "KeyName": sub("${AWS::StackName}-ssh"), "PublicKeyMaterial": ref("SshPublicKeyMaterial"), "Tags": tags("ssh"),
            }},
            "WebInstance": {"Type": "AWS::EC2::Instance", "DependsOn": ["GatewayAttachment", "DefaultInternetRoute", "PublicRouteAssociation"], "Properties": {
                "ImageId": ref("AmazonLinuxAmiId"), "InstanceType": "t3.micro",
                "KeyName": {"Fn::If": ["ImportPublicKey", ref("ImportedSshKey"), ref("ExistingKeyPairName")]},
                "CreditSpecification": {"CPUCredits": "standard"}, "Monitoring": False,
                "MetadataOptions": {"HttpTokens": "required", "HttpEndpoint": "enabled", "HttpPutResponseHopLimit": 1},
                "BlockDeviceMappings": [{"DeviceName": "/dev/xvda", "Ebs": {
                    "VolumeSize": 8, "VolumeType": "gp3", "Encrypted": True, "DeleteOnTermination": True,
                }}],
                "NetworkInterfaces": [{"DeviceIndex": "0", "SubnetId": ref("PublicSubnet"), "GroupSet": [ref("WebSecurityGroup")], "AssociatePublicIpAddress": True, "DeleteOnTermination": True}],
                "PropagateTagsToVolumeOnCreation": True, "Tags": tags("web"),
                "UserData": {"Fn::Base64": bootstrap},
            }},
        },
        "Outputs": {
            "Region": {"Value": ref("AWS::Region")},
            "VpcId": {"Value": ref("LabVpc")},
            "SubnetId": {"Value": ref("PublicSubnet")},
            "InternetGatewayId": {"Value": ref("InternetGateway")},
            "RouteTableId": {"Value": ref("PublicRouteTable")},
            "SecurityGroupId": {"Value": ref("WebSecurityGroup")},
            "InstanceId": {"Value": ref("WebInstance")},
            "PublicIp": {"Value": {"Fn::GetAtt": ["WebInstance", "PublicIp"]}},
            "WebsiteUrl": {"Value": sub("http://${WebInstance.PublicIp}/")},
            "HealthUrl": {"Value": sub("http://${WebInstance.PublicIp}/health")},
            "SshKeyPairName": {"Value": {"Fn::If": ["ImportPublicKey", ref("ImportedSshKey"), ref("ExistingKeyPairName")]}},
            "OriginUrl": {"Value": "https://cbnu-clip-it.vercel.app"},
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify checked-in template equals nginx + generator without writing.")
    args = parser.parse_args()
    content = json.dumps(template(), ensure_ascii=False, indent=2) + "\n"
    output = HERE / "cloudformation.json"
    if args.check:
        if not output.exists() or output.read_text() != content:
            parser.exit(1, "cloudformation.json is stale. Run python3 infra/cloud-lab/render-template.py\n")
        print("CloudFormation template and nginx.conf match.")
    else:
        output.write_text(content)
        print("Generated cloudformation.json (no AWS calls).")


if __name__ == "__main__":
    main()
