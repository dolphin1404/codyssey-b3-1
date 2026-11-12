"""명시한 AWS 프로필로 실습 스택을 생성·검증·정리한다."""

import argparse
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

from build_template import build


ROOT = Path(__file__).resolve().parent
STACK = "codyssey-b3-1"
REGION = "ap-northeast-2"


def aws(profile, *args):
    result = subprocess.run(
        ["aws", "--profile", profile, "--region", REGION, "--output", "json", "--no-cli-pager", *args],
        check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("check", help="인증 주체와 계정 확인 (읽기 전용)")
    deploy = sub.add_parser("deploy")
    deploy.add_argument("--ami", required=True)
    deploy.add_argument("--key-name", required=True)
    deploy.add_argument("--ssh-cidr", required=True)
    deploy.add_argument("--confirm-free-tier", action="store_true", required=True,
                        help="계정의 EC2/EBS/IPv4 무료 사용 또는 크레딧 확인 후 지정")
    sub.add_parser("verify")
    cleanup = sub.add_parser("cleanup")
    cleanup.add_argument("--confirm-stack", choices=[STACK], required=True)
    args = parser.parse_args()
    identity = aws(args.profile, "sts", "get-caller-identity")
    if identity["Arn"].endswith(":root"):
        raise ValueError("루트 계정은 사용할 수 없습니다. 실습용 IAM 사용자/Role을 선택하세요.")
    if args.action == "check":
        print(json.dumps(identity, indent=2))
        return
    if args.action == "deploy":
        network = ipaddress.ip_network(args.ssh_cidr, strict=True)
        if network.version != 4 or network.prefixlen != 32 or not network.network_address.is_global:
            raise ValueError("SSH에는 본인의 공인 IPv4/32를 지정하세요.")
        template = ROOT / "infra" / "template.json"
        template.parent.mkdir(exist_ok=True)
        template.write_text(json.dumps(build(), indent=2) + "\n")
        aws(args.profile, "cloudformation", "validate-template", "--template-body", f"file://{template}")
        result = aws(args.profile, "cloudformation", "create-stack", "--stack-name", STACK,
            "--template-body", f"file://{template}", "--parameters",
            f"ParameterKey=AmiId,ParameterValue={args.ami}",
            f"ParameterKey=KeyName,ParameterValue={args.key_name}",
            f"ParameterKey=SshCidr,ParameterValue={args.ssh_cidr}",
            "--tags", "Key=Project,Value=codyssey-b3-1", "--timeout-in-minutes", "15")
        print(json.dumps(result, indent=2))
        aws(args.profile, "cloudformation", "wait", "stack-create-complete", "--stack-name", STACK)
        print("생성 완료. user-data 완료 후 verify를 실행하세요.")
    elif args.action == "verify":
        stack = aws(args.profile, "cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
        outputs = {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}
        with urllib.request.urlopen(outputs["HealthUrl"], timeout=10) as response:
            body = response.read().decode()
            if response.status != 200 or body.strip() != "OK":
                raise ValueError("health 응답이 기대값과 다릅니다.")
            print(f"{outputs['HealthUrl']}\nHTTP {response.status}\n{body}")
        print("브라우저에서 위 URL을 열어 스크린샷도 저장하세요.")
    else:
        # 고정된 실습 스택만 삭제하며 다른 리소스는 탐색해서 삭제하지 않는다.
        stack = aws(args.profile, "cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
        if not any(tag["Key"] == "Project" and tag["Value"] == STACK for tag in stack.get("Tags", [])):
            raise ValueError("실습 프로젝트 태그가 없는 스택입니다.")
        print(json.dumps(aws(args.profile, "cloudformation", "list-stack-resources", "--stack-name", STACK), indent=2))
        aws(args.profile, "cloudformation", "delete-stack", "--stack-name", STACK)
        aws(args.profile, "cloudformation", "wait", "stack-delete-complete", "--stack-name", STACK)
        print("스택 삭제 완료. docs/cleanup-checklist.md의 잔여 리소스 확인을 수행하세요.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"오류: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr, file=sys.stderr)
        sys.exit(1)
