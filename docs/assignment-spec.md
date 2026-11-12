# CLIP-IT에 적용한 클라우드 배포 과제

원래 과제의 필수 결과물·네트워크·보안·정리 조건을 유지하고, 구현 대상을 졸업작품 CLIP-IT으로 구체화한 명세입니다. 작성 기준일: 2026-11-12.

## 1. 미션 소개

CLIP-IT은 고전 문학의 원문을 읽으며 해당 구절의 AI 영상 장면을 함께 감상하는 웹 서비스입니다. 기존 웹은 Vercel에서 제공하고 사용자 인증·문학 데이터·영상 저장은 기존 AWS 운영 리소스를 사용합니다.

이번 미션에서는 CLIP-IT의 공개 화면에 접속하는 서울 EC2 진입점을 만듭니다. 독립 VPC·Public Subnet·IGW·Route Table을 구성하고 EC2에 Nginx를 설치합니다. 공개 홈·작품 목록·정적 파일은 기존 HTTPS 사이트에 연결하고, `/health`에서 EC2의 고정 응답을 제공합니다.

평가자가 외부에서 EC2까지 이어지는 경로, SG와 IAM의 역할, 오류 분석과 리소스 정리 결과를 확인할 수 있어야 합니다.

## 2. 최종 결과물

| 결과물 | CLIP-IT 적용 내용 | 제출 최소 규격 |
| --- | --- | --- |
| 아키텍처 1장 | 서울 VPC·Subnet·IGW·EC2·SG와 요청 흐름, 기존 Vercel·도쿄 운영 영역 | `docs/architecture.png` 또는 PDF |
| 외부 접속 증빙 1개 | **B 방식**: 외부 PC에서 EC2 공인 IP의 `/health` → 200 / `OK` | README 실제 IP/URL·방식 + 화면 1장 이상 |
| 트러블슈팅 보고서 1개 | 실제 문제를 증상→가설→검증→조치→결과→재발 방지로 기록 | `docs/troubleshooting.md` 또는 PDF |
| 정리 체크리스트 1개 | 실습 EC2·EBS·EIP·IGW·VPC 정리와 조회 근거 | `docs/cleanup-checklist.md` |

실행 시각·리소스 ID·SSH/HTTP/아웃바운드 결과는 `docs/deployment-record.md`에 기록합니다. 준비된 문서와 실제 클라우드 검증 완료 상태를 구분합니다.

## 3. 과제 목표

실습 후 다음을 CLIP-IT 요청 흐름으로 설명할 수 있어야 합니다.

- 브라우저 요청이 IGW·Public Subnet·SG를 거쳐 EC2 Nginx에 도착하는 과정
- VPC·Subnet·Route Table·IGW·공인 IP의 역할
- SG의 네트워크 제어와 IAM의 AWS 작업 권한 제어 차이
- 공개 화면 프록시, EC2 자체 `/health`, 기존 HTTPS 로그인 경로의 역할
- 실제 응답·Nginx·cloud-init 로그를 근거로 장애를 분석하는 방법
- 운영 서비스는 유지하면서 실습 리소스만 삭제하고 잔여 비용 항목을 확인하는 방법

## 4. 기능 요구 사항

### 네트워크

- 서울에 VPC `10.20.0.0/16` 한 개와 Public Subnet `10.20.1.0/24` 한 개를 생성합니다.
- 전용 IGW를 VPC에 연결하고 서브넷 Route Table에 `0.0.0.0/0 → IGW`를 설정합니다.
- EC2에 공인 IPv4를 자동 할당하고 인스턴스에서 `curl https://example.com`의 정상 응답을 확인합니다.

### EC2와 CLIP-IT 공개 화면

- Public Subnet에 Amazon Linux 2023, `t3.micro` 한 대와 암호화 gp3 8 GiB 루트 볼륨을 구성합니다.
- SSH 접속, Nginx 서비스·설정 검사를 통과하고 `curl http://localhost/`가 200을 반환해야 합니다.
- 공개 `GET/HEAD /`, `GET/HEAD /api/works`, 정적 파일·이미지는 고정 Vercel 호스트로 HTTPS 프록시합니다.
- `/health`는 원본 사이트에 요청하지 않고 Nginx가 `200`, `text/plain`, `OK`를 직접 반환합니다.
- 로그인·회원가입·리더·관리자 등 나머지 경로는 기존 HTTPS 주소로 이동합니다.
- 프록시에서 Cookie·Authorization 전달과 응답 Set-Cookie를 제거하고 `/api/works` 쓰기 요청을 차단합니다.

### 접근 제어

- HTTP TCP 80은 `0.0.0.0/0`에 공개합니다.
- SSH TCP 22는 실습자의 현재 공인 IPv4 `/32`에서만 허용합니다.
- 인터넷 전체에 모든 포트를 개방하는 인바운드는 생성하지 않습니다.
- EC2 메타데이터는 IMDSv2를 요구합니다.

### IAM 최소 권한

- 배포·검증·정리는 별도 IAM 사용자 또는 Role로 수행합니다. 루트와 `AdministratorAccess`는 사용하지 않습니다.
- `infra/cloud-lab/managed-policy-network.example.json`, `managed-policy-compute.example.json` 두 개를 계정에 맞게 적용합니다. 서울·실습 스택·태그·허용 유형에 필요한 범위로 제한합니다.
- 기존 CLIP-IT 웹 런타임·스크립트 업로더 키를 실습 관리자로 재사용하지 않습니다.
- EC2에 앱 AWS 키나 IAM Role을 넣지 않고, 기존 RDS·Cognito·S3 관리 권한을 새로 부여하지 않습니다.
- 사용 주체와 실제 연결 정책·작업 결과를 기록해야 권한 적용 완료로 판정합니다.

### 외부 검증과 운영 안정성

- B 방식의 실제 외부 `/health` 응답·IP/URL·KST 시각·스크린샷을 남깁니다.
- 로컬 Nginx와 기존 Vercel 결과는 실행 환경을 표시해 EC2 증빙과 구분합니다.
- 종료 후 EC2 `terminated`, EBS 삭제, EIP 미생성 또는 해제, IGW 분리·삭제, VPC와 하위 리소스 삭제를 실제 조회합니다.
- 인프라 삭제 후에도 제출 문서와 검증 당시 IP·응답·삭제 근거를 보존합니다.

## 5. 보너스 과제

| 보너스 | CLIP-IT 적용 방법 | 완료에 필요한 자료 |
| --- | --- | --- |
| EC2 HTTPS | 도메인을 서울 EC2에 연결하고 Nginx 인증서 적용 | 해당 EC2 도메인의 HTTPS 응답과 인증서 확인 |
| EC2 Docker 배포 | EC2 내부에서 공개 화면용 Nginx를 컨테이너로 실행 | 이미지·명령·포트 매핑, `docker ps`와 외부 응답 화면 2장 이상, localhost 정상 응답 |

기존 Vercel HTTPS와 개발 PC Docker 검증만으로 보너스 완료로 표시하지 않습니다. 현재 기본 구성은 EC2에 Nginx 패키지를 설치합니다.

## 6. 개발 환경

| 영역 | 환경 |
| --- | --- |
| 신규 실습 인프라 | AWS 서울 `ap-northeast-2`, CloudFormation, VPC, EC2, SG |
| EC2 | Amazon Linux 2023 x86_64, `t3.micro`, Nginx, gp3 8 GiB |
| 실습 도구 | AWS CLI v2, Bash, Python 3, curl, OpenSSH |
| 기존 졸업작품 | Next.js·React / Vercel, PostgreSQL / RDS, Cognito, S3 |
| 로컬 선택 도구 | Nginx 설정 검사용 Docker. EC2 Docker 보너스와 구분 |

## 7. 제약 사항

- 신규 실습 리소스는 서울에 생성합니다. 기존 도쿄 운영 리소스의 리전·데이터는 유지합니다.
- 원 과제의 **프리 티어 범위 내 진행** 조건을 지킵니다. 계정별 무료 이용 대상·잔여 크레딧·사용량과 EC2/EBS/공인 IPv4/전송 비용 적용을 확인하고, 조건 충족을 확인할 수 없으면 리소스를 생성하지 않습니다. `micro`만으로 무료를 확정하지 않습니다.
- SSH `/32` 제한을 유지하고 개인키·AWS 키·DB 연결 문자열을 Git이나 제출 화면에 넣지 않습니다.
- NAT Gateway·EIP·ALB·신규 RDS·S3는 기본 구성에 생성하지 않습니다. 수동 추가는 추적·정리합니다.
- 임시 인프라 복구 예약은 별도의 실제 배포 작업에서 관리합니다. 이 제출본 개정으로 예약을 변경하지 않습니다.
- 정확한 실습 StackId/리소스 ID만 정리합니다. 기존 Vercel·도쿄 DB·인증·영상과 다른 운영 EC2는 보존합니다.

## 8. Test Case와 제출 전 확인

| ID | 실행 위치 / 확인 | 성공 기준 | 제출 근거 |
| --- | --- | --- | --- |
| C01 | AWS 네트워크 조회 | 전용 VPC·Subnet·IGW·인터넷 경로·서브넷 연결 | ID·라우팅 결과 |
| C02 | AWS SG 조회 | 80 공개, 22 개인 `/32`, 전체 포트 공개 없음 | 규칙 조회 / 화면 |
| C03 | 실습 IAM 확인 | 비루트 주체와 제한 정책 적용 | 사용자/Role·정책 기록 |
| C04 | EC2 SSH·Nginx | 접속·설정·서비스 정상 | SSH 명령 결과 |
| C05 | EC2 localhost `/` | HTTP 200 | 내부 결과 |
| C06 | EC2 HTTPS 아웃바운드 | `https://example.com` HTTP 200 | 내부 결과 |
| C07 | 외부 PC `/health` | 실제 EC2 IP에서 200 / `text/plain` / `OK` | README URL/IP·시각·화면 |
| C08 | 홈·작품 목록·로그인 | 공개 화면 정상, 로그인은 고정 HTTPS 원본 이동 | 응답 기록 |
| C09 | 실제 장애 1건 | 증상부터 재발 방지까지 근거 연결 | 보고서·로그 |
| C10 | 종료 후 AWS 조회 | EC2·EBS·EIP·IGW·VPC 완료/미생성 확인 | 정리 표·조회 결과 |

위 표는 성공 기준입니다. 실제 결과는 [배포·검증 기록](deployment-record.md)에 작성하고 미실행은 대기로 유지합니다.
