# 서울 AWS 클라우드 배포 실습

기존 ClipIt 앱은 `https://cbnu-clip-it.vercel.app`에 그대로 두고, **과제용 서울 EC2에 Nginx를 설치해 공개 홈 화면을 제공**하는 구성입니다. Next.js 전체 앱·DB·기존 AWS 백엔드를 EC2로 옮긴 구성으로 보고하면 안 됩니다. EC2의 `/health`는 Nginx 자체에서 `200`, `text/plain`, `OK\n`을 반환하며 원본 서비스 장애와 독립적입니다.

## 만들어지는 리소스

| 항목 | 값 |
| --- | --- |
| 리전 | 서울 `ap-northeast-2` |
| 별도 VPC / 공용 서브넷 | `10.20.0.0/16` / `10.20.1.0/24` |
| 인터넷 연결 | Internet Gateway, `0.0.0.0/0` 기본 경로, 서브넷 라우트 연결 |
| 인스턴스 | Amazon Linux 2023 x86_64, `t3.micro`, 공인 IPv4 |
| 루트 디스크 | 암호화 gp3 8 GiB, 종료 시 삭제 |
| CPU 크레딧 / 메타데이터 | `standard` / IMDSv2 필수 |
| 인바운드 | TCP 80 전체 공개, TCP 22 학습자 공인 IPv4 `/32`만 |
| SSH 키 | 서울의 기존 키 페어 1개 사용 또는 로컬 공개 키 1개 가져오기 |
| 소유 범위 | `clip-it-cloud-lab-*` 스택과 `CloudLab=clip-it-assignment` 태그 |

NAT Gateway, EIP, 로드밸런서, RDS, S3, IAM 리소스는 만들지 않습니다. 기존 운영 리소스를 참조하거나 수정하는 코드도 없습니다. 공인 IP는 고정하지 않으며 인스턴스 정지/시작 시 바뀔 수 있습니다.

## HTTP 실습 주소의 공개 범위

공개 `GET/HEAD /`, `GET/HEAD /api/works`, Next.js 정적 파일·이미지, 루트 이미지·폰트만 고정 Vercel 호스트로 프록시합니다. Cookie/Authorization은 전달하지 않고 응답 Set-Cookie도 제거합니다. 로그인·회원가입·관리자·라이브러리·리더와 나머지 경로는 원본 HTTPS로 `308` 이동합니다. 계정 기능은 원본 HTTPS 주소에서 사용하세요. `/api/works`의 쓰기 메서드는 차단됩니다.

## 준비와 비용 확인

AWS CLI v2 최신 버전(`freetier get-account-plan-state` 지원), Bash, Python 3, curl, OpenSSH가 필요합니다. IAM 사용자/역할 프로필을 미리 구성하세요. **AWS root 자격 증명은 거절**합니다. 스크립트는 자격 증명을 생성하거나 읽어 출력하지 않습니다.

`t3.micro`와 8 GiB를 선택했다는 사실만으로 무료가 보장되지는 않습니다. 계정 생성 시기·플랜·만료일·남은 크레딧·다른 리소스 사용량에 따라 EC2, EBS, 공인 IPv4, 전송 비용이 발생할 수 있습니다. [AWS EC2 무료 이용 안내](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html)와 [무료 이용 플랜 안내](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)를 참고하고, **현재 계정의 Billing/Free Tier/Credits 화면에서 이 실습의 비용과 크레딧 적용 여부를 확인**하세요. 예산 알림 설정도 권장합니다.

배포 전 스크립트는 API로 `t3.micro`와 Amazon Linux AMI의 `FreeTierEligible`, 현재 계정의 `ACTIVE` 플랜과 양수 USD 크레딧을 확인하고 사용량을 저장합니다. 확인 불가·만료·잔액 없음이면 생성 전에 중단합니다. `FREE_TIER_CONFIRMED=yes`는 콘솔에서 EC2/EBS/IPv4/전송 및 크레딧 적용을 확인했다는 명시적 확인이며, API 검사를 우회하지 않습니다. 이 자동 경로는 활성 크레딧이 있는 계정을 대상으로 합니다. 유료 계정도 남은 크레딧이 없으면 거절합니다. 별도 프로모션 크레딧만 있는 계정은 이 API 판정과 다를 수 있으므로 임의로 통과시켜 무료라고 제출하지 마세요.

Free Tier API는 계정 전체 정보를 조회하는 `us-east-1` 서명 엔드포인트입니다. 이 읽기 요청 때문에 다른 리전에 리소스가 생성되지는 않습니다. 인프라 요청은 전부 서울이며 다른 `AWS_REGION`/`AWS_DEFAULT_REGION`은 거절합니다.

## CLI 실행

이 제출 저장소의 루트 디렉터리에서 실행합니다. 아래 IP·키 경로·프로필 값은 본인 값으로 바꾸세요. 문서 예시 IP는 실제 공인 IP가 아니므로 스크립트가 거절합니다.

```bash
export AWS_PROFILE=cloud-lab
export AWS_REGION=ap-northeast-2
export STACK_NAME=clip-it-cloud-lab-seoul
export SSH_CIDR='203.0.113.10/32' # 반드시 본인의 현재 공인 IPv4 /32로 교체
export KEY_PAIR_NAME='my-existing-seoul-key'
export SSH_PRIVATE_KEY_FILE="$HOME/.ssh/my-existing-seoul-key.pem"

# Billing/Free Tier/Credits에서 비용/만료/잔액 확인한 뒤에만 설정
export FREE_TIER_CONFIRMED=yes

./infra/cloud-lab/lab.sh preflight  # 읽기만 수행; 아직 생성하지 않음
./infra/cloud-lab/lab.sh deploy     # 검사를 다시 수행한 후 별도 실습 스택 생성
./infra/cloud-lab/lab.sh status
```

기존 키 대신 본인이 소유한 OpenSSH RSA/ED25519 공개 키를 가져오려면 `KEY_PAIR_NAME`을 해제하고 다음 값을 사용합니다. 비밀 키는 로컬 SSH 연결에만 사용하며 AWS에 업로드하지 않습니다.

```bash
unset KEY_PAIR_NAME
export SSH_PUBLIC_KEY_FILE="$HOME/.ssh/cloud-lab.pub"
export SSH_PRIVATE_KEY_FILE="$HOME/.ssh/cloud-lab"
```

두 키 옵션을 동시에 지정하거나 모두 비워 두면 중단합니다. `deploy`는 새 스택만 생성하며 동명의 기존 스택을 수정하지 않습니다. 스택 생성 완료는 Nginx 설치 완료를 뜻하지 않으므로 cloud-init이 끝날 때까지 수 분 기다리고 검증하세요.

```bash
./infra/cloud-lab/lab.sh verify
```

검증은 AWS API의 VPC/서브넷/라우트/보안 그룹/EC2/CPU 크레딧/EBS 설정, 외부 HTTP 홈·`/health`·로그인 HTTPS 이동, **실제 SSH 연결 후 Nginx 설정/서비스·localhost 홈/health·`https://example.com` 외부 통신**을 확인합니다. SSH는 `/32`에 지정한 공인 IP에서 실행해야 합니다. 암호화 비밀 키라면 미리 SSH 에이전트에 로드하세요. 전용 `.local/…/known_hosts`와 `StrictHostKeyChecking=accept-new`를 사용해 이후 호스트 키 변경을 거절합니다. 첫 연결 전 EC2 콘솔의 인스턴스 로그에서 호스트 키 지문을 확인하세요.

원시 AWS/SSH/HTTP 결과, 계정 ID/ARN/IP/키 이름은 `.local/`에만 저장하며 디렉터리 700/파일 600, Git 제외입니다. 제출용으로 복사할 수 있는 `verification-summary.redacted.json`에는 계정 ID/ARN/IP/키를 포함하지 않습니다. **실제로 검증된 결과만 제출**하고 `.local/` 전체를 커밋하지 마세요. 스크린샷도 계정 ID/사용자명/ARN/키 정보를 가린 뒤 사용하세요.

실패 시 `.local/<스택 이름>/ssh-verification.error.txt`, EC2 콘솔 시스템 로그 또는 SSH의 `sudo tail -n 80 /var/log/cloud-init-output.log`, `sudo nginx -t`, `sudo journalctl -u nginx --no-pager`를 확인합니다. `/health`가 200인데 홈이 502이면 EC2 Nginx는 살아 있고 원본 HTTPS/DNS/TLS 연결 문제를 조사해야 합니다.

## 실습만 정리

```bash
./infra/cloud-lab/lab.sh cleanup
```

자신이 `deploy`로 만든 로컬 생성 기록, AWS 계정·서울 리전·스택 ID·실습 태그를 확인한 뒤 **정확한 스택 ID만 삭제**합니다. 삭제 완료를 기다리고 실습 태그의 활성 인스턴스/EBS/VPC/IGW/서브넷/라우트/보안 그룹/가져온 키가 남지 않았는지 조회해 `cleanup-summary.redacted.json`에 기록합니다. 기존 키 페어는 삭제하지 않습니다. 실패·잔여 리소스가 발견되면 검증 실패로 중단하며 다른 리소스를 일괄 삭제하지 않습니다. 생성 API 응답이 유실되어 정확한 StackId가 기록되지 않았다면 이름·태그만으로 소유를 추정하지 않고 정리를 거절합니다. 이 경우 콘솔에서 정확한 생성 스택/리소스를 확인해 정리하세요. EC2만 정지하면 EBS 비용이 남을 수 있으므로 실습 완료 후 스택을 삭제하세요.

## 콘솔에서 진행해야 할 때

CLI 프로필이 없으면, IAM 사용자/역할로 로그인하고 Billing에서 비용/크레딧을 확인한 다음 **서울** CloudFormation에서 `cloudformation.json`을 업로드해 `clip-it-cloud-lab-*`라는 별도 스택을 만듭니다. 파라미터에는 서울의 최신 Amazon Linux 2023 x86_64 AMI ID(EC2 AMI 화면에서 Amazon 소유·무료 이용 대상 확인), 현재 공인 IPv4 `/32`, 기존 키 이름 또는 공개 키 중 하나만 넣습니다. 스택 태그 `CloudLab=clip-it-assignment`, `LabStack=<스택 이름>`도 추가합니다. 정책 예제는 CLI의 `--resource-types` 제한을 요구하므로 일반 콘솔 CreateStack에는 별도 관리자가 검토한 콘솔용 권한이 필요할 수 있습니다.

콘솔 생성에는 이 도구의 로컬 소유 기록이 없으므로 `cleanup`은 거절합니다. 콘솔에서 해당 **실습 스택**의 리소스 탭과 출력·스택 ID를 기록하고, 생성한 인스턴스에 직접 SSH해 위 명령을 확인한 뒤 스택 삭제를 실행하세요. 인스턴스·EBS·IGW·서브넷·VPC 삭제를 콘솔에서 확인하고 증거를 남깁니다. 기존 운영 리소스는 대상으로 선택하지 않습니다.

## IAM 예제와 로컬 검증

`managed-policy-network.example.json`과 `managed-policy-compute.example.json` **두 개를 함께 적용**하는 구성으로, 실습에 필요한 범위로 권한을 제한하기 위한 예제입니다. 실제 계정에서의 작업별 권한 적용은 배포·검증·정리 단계에서 확인해야 합니다. 각각 managed policy의 공백 제외 6,144자 한도 안에 들어갑니다. 계정 관리자가 두 파일의 `ACCOUNT_ID`를 실제 계정 ID로 바꾸고, 기존 키를 쓰면 `EXISTING_KEY_PAIR_NAME`도 지정해서 각각 managed policy로 생성하여 IAM 사용자 또는 역할에 둘 다 연결해야 합니다. 합본 `operator-policy.example.json`은 역할 inline 정책(공백 제외 10,240자 한도)용 참고이며, IAM 사용자 inline 또는 단일 managed policy에 붙이면 크기 한도를 초과합니다. 공개 키 가져오기만 사용하면 기존 키 ARN 항목을 제거할 수 있습니다. 자동으로 IAM 정책을 설치하는 기능은 없습니다.

정책은 서울·실습 스택 접두사·CloudLab 태그·허용 EC2 리소스 유형·t3.micro·암호화 gp3 최대 8 GiB로 범위를 줄이고, S3/RDS/IAM/AdministratorAccess/PassRole 권한을 주지 않습니다. Describe/ValidateTemplate/Free Tier 등 리소스 ARN 제한을 지원하지 않는 읽기/검증 작업에만 `Resource: "*"`를 사용합니다. EC2 런치의 초기 네트워크 인터페이스는 아직 태그가 없으므로 서울 ARN에 한정하고 서브넷·보안 그룹은 실습 태그를 요구합니다. 가져온 공개 키를 CloudFormation이 삭제할 때도 SSM `/ec2/keypair/*` 삭제 권한을 가상의 파라미터 이름으로 검사하므로 해당 경로 권한이 필요합니다([AWS 공식 설명](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-key-pairs.html)). 이 예제는 `aws:CalledVia=cloudformation.amazonaws.com` 조건을 함께 요구해 **운영자가 직접 SSM 파라미터를 삭제하지 못하게** 제한합니다. CloudFormation은 실습 접두사·태그·EC2 리소스 유형만 생성/삭제할 수 있고 UpdateStack/SSM 리소스/사용자 정의 리소스 권한이 없습니다. 별도의 CloudFormation service role은 지정하지 않으며 운영자의 전달된 권한(FAS)을 사용합니다([FAS 조건 키](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_forward_access_sessions.html), [CloudFormation FAS 동작](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/fas-requests-and-permission-evaluation.html)). 조건 문법과 서비스 흐름은 공식 문서로 검토했으나, 계정별 KeyPair/SSM 삭제 handler의 실제 적용은 AWS 배포 후 검증해야 합니다. 권한 오류가 나면 정리 완료로 기록하지 말고 계정 관리자와 정확한 오류·실습 리소스를 확인하세요. 비밀 키를 생성하는 `CreateKeyPair`/SSM `PutParameter` 권한은 없습니다. 계정 SCP/사용자 정의 KMS/EBS 기본 키 정책이 있으면 관리자의 추가 검토가 필요합니다.

```bash
bash -n infra/cloud-lab/lab.sh
python3 infra/cloud-lab/render-template.py --check
python3 -m json.tool infra/cloud-lab/cloudformation.json >/dev/null
python3 -m json.tool infra/cloud-lab/operator-policy.example.json >/dev/null

# Docker는 로컬 Nginx 검사용일 뿐, EC2 설치 방식이나 추가 과제 수행 증거가 아님
# 컨테이너 생성/정리도 실습용 이름 하나만 사용
# 필요할 때 nginx 공식 이미지 사용

docker run --rm -d --name clip-it-cloud-lab-preview -p 127.0.0.1:8088:80 \
  -v "$PWD/infra/cloud-lab/nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx:stable
curl -i http://127.0.0.1:8088/health
curl -I http://127.0.0.1:8088/
curl -I http://127.0.0.1:8088/login
docker stop clip-it-cloud-lab-preview
```

`nginx.conf`를 수정했으면 `python3 infra/cloud-lab/render-template.py`로 JSON을 다시 생성합니다. 이 명령은 AWS를 호출하지 않습니다. 로컬 Docker 검증만으로 AWS 배포·SSH·정리까지 완료했다고 기록하면 안 됩니다.

참고: [CloudFormation EC2](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-instance.html), [공개 SSH 키 가져오기와 CloudFormation 삭제 권한](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-key-pairs.html), [EC2 IAM 작업별 지원 조건](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html), [Free Tier 계정 상태 API](https://docs.aws.amazon.com/cli/latest/reference/freetier/get-account-plan-state.html).
