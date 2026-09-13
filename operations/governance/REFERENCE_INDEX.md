# REFERENCE_INDEX.md — 제품/업무 기준 자료 인덱스

## 목적

이 파일은 데미안과 직원 AI들이 제품/업무 기준 자료를 찾기 위한 상위 인덱스다.
세부 자료가 없거나 최신 여부가 불확실하면 `확인 필요`로 표시한다. 먼저 승인된 도구로 Drive 원본·Notion 검토 요약·담당 Staff를 확인하고 Sinclair에게는 남은 결정만 요청한다. Drive는 원본 권위, Notion은 원문 링크를 가진 검토된 관리 정보, Kanban은 실행 상태 SoT다.

## 통합 정보 구조

- HermesVault 정보 구조 표준 v1: `/opt/data/workspace/AI_KNOWLEDGE/README.md`
- Metadata schema: `/opt/data/workspace/AI_KNOWLEDGE/HermesVault/90_governance_policy/metadata_schema.json`
- 전달 패키지 기준: `/opt/data/workspace/AI_KNOWLEDGE/HermesVault/90_governance_policy/transfer_package_policy.md`
- 중복 자료는 최신 날짜 기준본만 기본 노출하며 과거본은 `superseded`로 보관한다.
- 현재는 구조와 규격만 생성된 상태이며 기존 업무자료 migration은 시작하지 않았다.

## 공통 운영 문서

- 개발 환경 가이드(Hermes Desktop 지휘·검증 + VS Code 편집·디버깅 병행): `/opt/data/devdocs/개발환경-가이드.md`
- 공통 협업/승인 규칙: `/opt/data/agents/AGENTS.md`
- 데미안 라우팅/정기 보고 규칙: `/opt/data/agents/demian/AGENTS.md`
- 전 Staff Problem-Solving / Tutor 단일 상세 계약: `operations/docs/ai-problem-solving-policy.md`
- 기존 AI Tutoring 호환 포인터: `operations/docs/demian-ai-tutoring.md`
- 후보 native policy bundle 조립·검증: `operations/scripts/assemble-problem-solving-policy.py`
- Slack Lounge Staff 자율참여·실행 계약: `operations/docs/라운지-자율참여-실행계약.md`
- 데미안 SOUL: `/opt/data/agents/demian/SOUL.md`
- 한스 SOUL: `/opt/data/agents/hans/SOUL.md`
- 웬디 SOUL: `/opt/data/agents/wendy/SOUL.md`
- 팀 registry: `/opt/data/agents/registry.yaml`

## 직원별 역할 자료

- 한스 / Sales Support AI: 견적 요청 정리, 고객 회신 초안, 내부 문의 메일, 일정/계약/세금계산서/검수 정리
- 웬디 / Maintenance AI: 기존 고객 관리, 유지보수 갱신, 반복 장애, 불만 징후, 이탈 위험, EOS/EOL, 고도화 가능성
- 테슬라 / EDLP Technical Analysis AI: EDLP 기술 확인
- 튜링 / NDLP Technical Analysis AI: NDLP 기술 확인
- 왓슨 / Goldmine Search Bot: 과거 장애/구축/문의 이력 확인
- 다빈치 / Redmine Search Bot: 개발 이력, 버그, 패치, 개선 요청 확인
- 메이슨 / Marketing & Proposal AI: 제안서, 발표자료, 영업 메시지

## 제품 기준 포인터

- EDLP: Privacy-i, PV-i, EDR, MyPC Keeper, Agent, Endpoint 정책, 장치 제어, 출력 보안, 화면 캡처 제어, EOS/EOL
- NDLP: Mail-i, Webkeeper, WebkeeperSG_Suite, Network DLP, SWG, SSL 복호화, Mirror/Inline 구성, 로그서버, 생성형 AI 사이트/업로드 제어

## 고객·사업 참고자료

- 부방그룹·테크로스 EDLP/NDLP 고도화 견적(2026-08-04, 내부 참고용): `/opt/data/workspace/customer_materials/부방그룹/2026-08-04_부방_테크로스_EDLP_NDLP_고도화_견적/INDEX.md`

## 판단 원칙

- 공식 문서가 없으면 확정 답변하지 않는다.
- 과거 이력은 참고 자료이며 현재 고객 환경에 그대로 적용된다고 단정하지 않는다.
- 고객 발송 전에는 데미안 검수와 싱클레어 승인이 필요하다.
