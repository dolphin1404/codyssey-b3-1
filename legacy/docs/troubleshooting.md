# 트러블슈팅 기록

현재 AWS 계정에서 실행하지 않았으므로 실제 장애/복구 결과는 아직 없다.
다음 절차는 재현 계획이며 제출용 완료 증빙이 아니다.

## HTTP 접근 불가 조사 계획

1. 증상: 외부 `curl --connect-timeout 5 http://IP/health`의 실제 종료 코드·출력을 기록한다.
2. 가설: 보안 그룹 TCP 80 누락, IGW 기본 경로 누락, 퍼블릭 IP 미할당,
   또는 user-data/Nginx 기동 실패를 구분한다.
3. 검증: `describe-security-groups`, `describe-route-tables`, `describe-instances`와
   SSH 내부 `systemctl status nginx`, `sudo nginx -t`, `curl -i localhost/health`,
   `sudo tail -n 80 /var/log/cloud-init-output.log`의 출력을 보관한다.
4. 조치: 확인된 원인 한 가지만 수정한다. 예: 실습 보안 그룹의 TCP 80만 허용.
5. 결과: 동일 curl 명령의 Before/After 출력과 측정 시각을 남긴다.
6. 재발 방지: 템플릿 검증과 health 검증을 배포 절차에 포함한다.

의도적 장애 실습은 이 저장소가 만든 인스턴스에서만 수행한다.
예를 들어 SSH로 Nginx를 정지한 뒤 외부 연결 실패와 서비스 상태를 기록하고,
다시 시작한 뒤 동일 요청이 200/OK로 바뀌는지 확인할 수 있다.
실행 전후 실제 로그와 화면을 이 문서에 추가해야 최종 보고서가 완성된다.
