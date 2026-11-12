# 실습 리소스 정리

현재 상태: AWS 배포 전. 아래 항목은 실제 계정에서 확인 후 체크한다.
미실행 항목을 종료/삭제 완료로 간주하지 않는다.

- [ ] 생성한 스택의 리소스 ID 목록 저장: `aws cloudformation list-stack-resources --stack-name codyssey-b3-1`
- [ ] `python3 manage.py --profile PROFILE cleanup --confirm-stack codyssey-b3-1` 성공 출력 저장
- [ ] EC2 ID를 describe-instances로 조회하여 terminated 확인
- [ ] 기록한 EBS ID가 describe-volumes에서 더 이상 존재하지 않는지 확인
- [ ] Elastic IP: 이 템플릿은 생성하지 않음. 수동 할당했다면 해당 Allocation ID만 release
- [ ] Internet Gateway detach 및 삭제 확인
- [ ] Subnet, Route Table, Security Group, VPC 삭제 확인
- [ ] 별도로 만든 실습 키페어 삭제. 기존 공유 키페어는 유지
- [ ] NAT Gateway, ELB, RDS: 이 템플릿은 생성하지 않음. 별도 생성 여부 확인
- [ ] Billing에서 사용량/크레딧 확인 (반영 지연이 있을 수 있음)

종료(stop)는 삭제(terminate)가 아니다. EBS와 퍼블릭 IPv4 등 잔여 비용 항목도 확인한다.
스택 삭제가 실패하면 CloudFormation Events의 실패 리소스를 확인하고 원인을 해결한다.
계정 전체 리소스를 일괄 삭제하지 않는다.
