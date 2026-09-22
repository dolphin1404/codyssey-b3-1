"""서울 리전 실습용 CloudFormation JSON 템플릿을 생성한다."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def ref(name):
    return {"Ref": name}


def resource(kind, **properties):
    return {"Type": "AWS::EC2::" + kind, "Properties": properties}


def build():
    tags = [{"Key": "Project", "Value": "codyssey-b3-1"}]
    resources = {
        "Vpc": resource("VPC", CidrBlock="10.30.0.0/16", EnableDnsSupport=True,
                        EnableDnsHostnames=True, Tags=tags),
        "Subnet": resource("Subnet", VpcId=ref("Vpc"), CidrBlock="10.30.1.0/24", Tags=tags),
        "Gateway": resource("InternetGateway", Tags=tags),
        "Attachment": resource("VPCGatewayAttachment", VpcId=ref("Vpc"), InternetGatewayId=ref("Gateway")),
        "RouteTable": resource("RouteTable", VpcId=ref("Vpc"), Tags=tags),
        "DefaultRoute": resource("Route", RouteTableId=ref("RouteTable"),
                                 DestinationCidrBlock="0.0.0.0/0", GatewayId=ref("Gateway")),
        "RouteAssociation": resource("SubnetRouteTableAssociation", SubnetId=ref("Subnet"),
                                     RouteTableId=ref("RouteTable")),
        "WebSecurityGroup": resource("SecurityGroup", VpcId=ref("Vpc"),
            GroupDescription="HTTP public; SSH from operator only", Tags=tags,
            SecurityGroupIngress=[
                {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "CidrIp": "0.0.0.0/0"},
                {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "CidrIp": ref("SshCidr")},
            ]),
        "WebInstance": resource("Instance", ImageId=ref("AmiId"), InstanceType="t3.micro",
            KeyName=ref("KeyName"), Tags=tags,
            MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled"},
            BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {
                "VolumeSize": 8, "VolumeType": "gp3", "Encrypted": True, "DeleteOnTermination": True}}],
            NetworkInterfaces=[{"DeviceIndex": "0", "AssociatePublicIpAddress": True,
                "SubnetId": ref("Subnet"), "GroupSet": [ref("WebSecurityGroup")]}],
            UserData={"Fn::Base64": (ROOT / "user-data.sh").read_text(encoding="utf-8")}),
    }
    resources["DefaultRoute"]["DependsOn"] = "Attachment"
    resources["WebInstance"]["DependsOn"] = ["DefaultRoute", "RouteAssociation"]
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Codyssey B3-1 public web service (Seoul only)",
        "Parameters": {
            "AmiId": {"Type": "AWS::EC2::Image::Id", "Description": "Amazon Linux 2023 x86_64 AMI in Seoul"},
            "KeyName": {"Type": "AWS::EC2::KeyPair::KeyName"},
            "SshCidr": {"Type": "String", "AllowedPattern": r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}/32",
                        "Description": "Operator public IPv4 /32 only"},
        },
        "Rules": {"SeoulOnly": {"Assertions": [{"Assert": {"Fn::Equals": [ref("AWS::Region"), "ap-northeast-2"]},
                                                     "AssertDescription": "Use ap-northeast-2"}]}},
        "Resources": resources,
        "Outputs": {
            "PublicIp": {"Value": {"Fn::GetAtt": ["WebInstance", "PublicIp"]}},
            "InstanceId": {"Value": ref("WebInstance")},
            "VpcId": {"Value": ref("Vpc")},
            "HealthUrl": {"Value": {"Fn::Sub": "http://${WebInstance.PublicIp}/health"}},
        },
    }


if __name__ == "__main__":
    destination = ROOT / "infra" / "template.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(destination)
