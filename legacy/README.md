# 이전 독립 실습 구현 보관

CLIP-IT과 연결하지 않고 `Hello Cloud` 페이지를 제공하던 이전 B3-1 구성입니다. 현재 CLIP-IT 배포 경로는 저장소 루트의 `infra/cloud-lab/lab.sh`입니다.

| 보관 파일 | 이전 역할 |
| --- | --- |
| `build_template.py`, `infra/template.json` | `10.30.0.0/16` 독립 실습 템플릿 |
| `manage.py` | 이전 `codyssey-b3-1` 스택 관리 |
| `user-data.sh` | `Hello Cloud` 페이지 설치 |
| `infra/operator-policy.json` | 이전 실습 정책 |
| `docs/` | 이전 트러블슈팅·정리 안내 |
| `README.original.md` | 개정 전 안내 원문 |

이전 명령·스택·네트워크는 현재 CLIP-IT 구성과 섞어 쓰지 않습니다. 이전 템플릿 회귀 확인은 저장소 루트에서 실행합니다.

```bash
python3 -m unittest discover -s legacy/tests -v
```
