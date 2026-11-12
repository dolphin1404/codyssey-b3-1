# AWS 웹 서비스 배포

서울 리전 VPC/Public Subnet/IGW/Route Table/보안 그룹/EC2를 구성하는
CloudFormation 템플릿과 Nginx 설치 스크립트다. 외부 검증은 **B: GET /health**를 사용한다.

현재 상태: 코드와 로컬 구조 검증 완료, 실제 AWS 배포 및 접속 증빙은 미완료.
IAM 프로필과 계정별 프리 티어/크레딧 확인이 필요하다. 아직 실제 Public IP/URL은 없다.
`docs/architecture.png`는 배포 예정 구성도다.

## 준비

Python 3.10+, AWS CLI v2, SSH 클라이언트가 필요하다.
계정 관리자가 실습 전용 IAM 사용자 또는 Role에 `infra/operator-policy.json`을 검토해
적용한다. AdministratorAccess나 루트 계정을 사용하지 않는다.
정책은 서울 리전의 필요한 EC2 작업과 이 실습 CloudFormation 스택에 한정한다.
EC2 자원은 생성 전 ID가 없으므로 Resource가 `*`인 작업이 있다. 전용 실습 계정에서
사용하고, 공유 계정이라면 관리자와 자원 ARN/태그 조건을 추가한다.
S3/RDS/IAM 관리 권한은 포함하지 않으며 EC2 자체에는 IAM Role을 붙이지 않는다.
SSH 키페어는 계정 관리자가 서울 리전에 미리 준비한다.

micro 인스턴스라고 자동으로 무료인 것은 아니다. 배포 전에 계정별 EC2/EBS 및
퍼블릭 IPv4 사용량·크레딧을 확인한다. 확인되지 않으면 deploy를 실행하지 않는다.

```bash
python3 build_template.py
python3 -m unittest discover -s tests -v
aws configure --profile codyssey-lab
python3 manage.py --profile codyssey-lab check
```

서울 리전의 Amazon Linux 2023 x86_64 AMI ID와 준비한 키페어 이름을 지정한다.

```bash
python3 manage.py --profile codyssey-lab deploy \
  --ami ami-REPLACE --key-name YOUR_KEY \
  --ssh-cidr YOUR_PUBLIC_IP/32 --confirm-free-tier
python3 manage.py --profile codyssey-lab verify
```

스택 생성 완료와 Nginx 설치 완료는 다를 수 있다. 실패 시 cloud-init 로그를 확인한다.
SSH: `ssh -i YOUR_KEY.pem ec2-user@PUBLIC_IP`.
인스턴스 안에서 `curl -i http://localhost/health`와 `curl -I https://example.com`으로
로컬 서비스 및 아웃바운드를 검증한다. 외부 브라우저에서 `http://PUBLIC_IP/health`를
열고 URL과 OK 응답이 보이는 스크린샷을 `docs/`에 저장한 뒤 이 README에 링크한다.

실습 후 [정리 체크리스트](docs/cleanup-checklist.md)를 수행한다.
[트러블슈팅 기록](docs/troubleshooting.md)은 실제 로그를 확보한 뒤 완성한다.
키/인증 파일은 커밋하지 않는다. HTTPS, Docker 배포는 보너스이므로 포함하지 않는다.

설계 참고: [EC2 NetworkInterface](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ec2-instance-networkinterface.html),
[보안 그룹 ingress](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-securitygroupingress.html),
[EC2 IAM 정책 예시](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ExamplePolicies_EC2.html).
