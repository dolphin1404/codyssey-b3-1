# CLIP-IT 실제 배포·검증 기록

별도로 진행하는 EC2 배포 결과를 제출본에 옮겨 적는 기록지입니다. 작성 시점에는 실제 AWS 접속·정리 증거가 이 제출본에 반영되지 않았습니다. 기대값을 관측 결과로 복사하지 않습니다.

## 환경과 리소스

| 항목 | 설계 / 기대값 | 실제 결과 |
| --- | --- | --- |
| 실행 시각 | KST | 기록 대기 |
| 리전 | `ap-northeast-2` | 기록 대기 |
| IAM 사용자/Role·정책 | 비루트, 제한 정책 | 기록 대기 |
| 스택 이름 / StackId | `clip-it-cloud-lab-*` | 기록 대기 |
| VPC / Subnet / IGW / Route Table / SG | 독립 서울 자원 | 기록 대기 |
| EC2 / EBS ID | `t3.micro`, 암호화 gp3 8 GiB | 기록 대기 |
| 키페어 / 새 키 여부 | 기존 키 또는 전용 공개키 한 개 | 기록 대기 |
| 공인 IP / 외부 URL | `http://<EC2_PUBLIC_IP>/health` | 기록 대기 |

## 실제 확인 결과

| 항목 | 성공 기준 | 실제 상태 / 시각 / 증거 파일 |
| --- | --- | --- |
| SG | 80 공개, 22 개인 IPv4 `/32` | 기록 대기 |
| 라우팅 | Subnet 연결, `0.0.0.0/0 → IGW` | 기록 대기 |
| SSH / Nginx | 접속·active·`nginx -t` 정상 | 기록 대기 |
| EC2 localhost `/` | HTTP 200 | 기록 대기 |
| EC2 localhost `/health` | 200 / `text/plain` / `OK` | 기록 대기 |
| EC2 HTTPS 아웃바운드 | `https://example.com` HTTP 200 | 기록 대기 |
| 외부 B 방식 `/health` | 실제 EC2 IP에서 200 / `OK` | 기록 대기 |
| 공개 홈 | CLIP-IT 화면 HTTP 200 | 기록 대기 |
| 로그인 | 고정 Vercel HTTPS 원본 이동 | 기록 대기 |
| 외부 스크린샷 | URL/IP와 응답 표시 | 실제 캡처 후 `docs/evidence/external-health.png` 연결 |
| 장애 분석 | 원인·Before/After 근거 | 실제 기록 추가 |
| 정리 완료 | EC2·EBS·EIP·IGW·VPC 확인 | 체크리스트에 실제 기록 추가 |

원시 AWS 출력은 Git 제외된 `infra/cloud-lab/.local/`에 저장됩니다. 제출에는 비밀값을 제거한 근거만 선별하고 README의 접속 정보와 기록을 일치시킵니다. 계정·사용자·키 이름은 평가에 필요한 범위만 노출합니다.

삭제 뒤에도 검증 당시 주소와 시각은 보존하고 현재 가동 여부를 별도로 기록합니다. 임시 인프라 복구 예약은 원래 배포 작업에서 관리합니다.
