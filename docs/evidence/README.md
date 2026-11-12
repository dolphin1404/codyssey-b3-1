# 증빙 목록

## 기존 자료 — 2026-10-03

아래는 기존 로컬·Vercel 검증입니다. 날짜와 실행 환경을 유지해 보관하며 오늘 실제 EC2 증빙으로 사용하지 않습니다.

| 자료 | 환경과 의미 |
| --- | --- |
| [local-troubleshooting](20261003-local-troubleshooting.json) | 로컬 Docker `/health` 누락 404와 수정 후 200 |
| [local-validation](20261003-local-validation.json) | 최종 로컬 Nginx의 공개 경로·health·인증 경로·쓰기 차단 |
| [local-tooling-validation](20261003-local-tooling-validation.json) | 당시 템플릿·문법·보호 조건 검사 |
| [production-baseline](20261003-current-production-baseline.json) | 당시 기존 Vercel 홈·로그인·API 응답 참고 |
| [운영 서비스 화면](20261003-current-production.png) | 당시 기존 Vercel의 CLIP-IT 공개 화면 |

## 실제 배포 후 추가

- 실제 EC2 공인 IP와 `200 OK`·`OK`를 보여주는 `external-health.png`
- SSH·Nginx·localhost·아웃바운드·라우팅·SG·IAM 근거
- 실제 장애·수정 결과와 리소스 삭제 조회 근거

실제 실행 후 추가하며 파일이 없거나 기록 대기이면 완료로 표시하지 않습니다. 개인키·AWS 비밀 키·세션 토큰·DB 문자열과 private `.local/` 전체는 제출하지 않습니다.
