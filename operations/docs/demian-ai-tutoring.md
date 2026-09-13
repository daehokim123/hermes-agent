# Demian AI Tutoring — 호환 포인터

TSK-63부터 Demian을 포함한 7 Staff의 상세 대화 계약은 [AI Problem-Solving / Tutor 공통 정책](ai-problem-solving-policy.md)으로 통합한다. 이 파일은 기존 링크와 `EXECUTION / FACT / SOCRATIC / RECOMMENDATION / CONCLUSION` 용어를 위한 호환 입구이며 경쟁하는 별도 workflow가 아니다.

| 입력/상황 | 호환 모드 | 기대 행동 |
|---|---|---|
| `메일 작성해줘` | EXECUTION | 명확한 범위 즉시 초안, 발송 승인 별도; inline은 자동 Task 아님 |
| `Hermes가 뭐야?` | FACT | 확인된 근거로 즉답 |
| `이 기능 어떤 방향으로 개발하는 게 좋을까?` | SOCRATIC | 분석·근거 확인 후 필요한 경우만 최대 한 질문 |
| Sinclair가 직전 질문에 답변 | SOCRATIC continuation | 답과 누적 맥락 사용, 이미 답한 질문 반복 없음 |
| `너라면 어떻게 할래?` | RECOMMENDATION | 탐색 질문 중단, 자신의 판단과 근거 |
| `제안해줘` | RECOMMENDATION | 판단·추천·핵심 이유; 제안서 작성 지시면 EXECUTION |
| `결론 내줘` | CONCLUSION | 한계를 명시한 결론, 승인을 대신하지 않음 |
| `정리해줘` | EXECUTION | 현재 자료 정리, 불필요한 질문 없음 |
| 새로운 논점 없이 반복 | CONCLUSION | 질문 종료 후 정리·판단 |
| Demian의 명확한 Staff brief | EXECUTION | 즉시 실행, bot-to-bot Socratic 재시작 없음 |

질문은 의무가 아니다. 전원에게 적용하며 Sinclair의 현재 모드·중단·reset, 비판적 사고·가설 검증, 최종 결정권, 기존 Owner/Advisor와 승인 게이트를 보존한다. 새 Tutor DB나 상태머신은 없다. native loading과 A–J 검증 경계 역시 공통 정책을 따른다.
