"""Structural Tutor compatibility + real native loading, NOT LLM behavior.

Read candidate policies only; no live profiles, model calls or external services.
The legacy document keeps examples; the all-staff canonical owns the contract.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'operations/docs/ai-problem-solving-policy.md'
LEGACY = ROOT / 'operations/docs/demian-ai-tutoring.md'
STAFF_PROFILES = ('demian', 'hans', 'wendy', 'tesla', 'turing', 'watson', 'mason')


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8').strip()


def _assembler():
    spec = importlib.util.spec_from_file_location(
        'tutor_assembly', ROOT / 'operations/scripts/assemble-problem-solving-policy.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(('message', 'mode'), [
    ('메일 작성해줘', 'EXECUTION'),
    ('Hermes가 뭐야?', 'FACT'),
    ('이 기능 어떤 방향으로 개발하는 게 좋을까?', 'SOCRATIC'),
    ('너라면 어떻게 할래?', 'RECOMMENDATION'),
    ('제안해줘', 'RECOMMENDATION'),
    ('결론 내줘', 'CONCLUSION'),
    ('정리해줘', 'EXECUTION'),
])
def test_acceptance_examples_are_bound_to_expected_modes(message, mode):
    rows = [line for line in _read(LEGACY).splitlines()
            if line.startswith('|') and f'`{message}`' in line]
    assert len(rows) == 1
    assert mode in rows[0]
    assert 'ai-problem-solving-policy.md' in _read(LEGACY)


def test_socratic_continuation_and_convergence_contract():
    policy = _read(POLICY)
    for text in ('한 응답에 최대 하나의 집중 질문', '질문 없이 분석·조회·정리를 진행해도 된다',
                 '직전 답변', '이미 답한 내용을 다시 묻지', '기존 내용이 반복되면',
                 '질문을 종료하고 정리와 판단으로 전환'):
        assert text in policy
    assert '질문을 정확히 하나' not in policy


def test_fact_and_critical_reasoning_contract():
    policy = _read(POLICY)
    for text in ('현재 사실은 도구로 원천을 조회', '사용자 생각을 되묻지 않는다',
                 '비판적 사고', '가설 검증', '약한 전제·반증·대안',
                 '최종 판단과 승인은 Sinclair에게'):
        assert text in policy


def test_recommendation_overrides_socratic_mode():
    policy = _read(POLICY)
    for text in ('이전 SOCRATIC 흐름보다 우선', '질문을 즉시 중단',
                 '각 Staff 자신의 판단', '추천은 Sinclair 승인이나 외부 실행 권한이 아니다'):
        assert text in policy


def test_execution_keeps_owner_and_approval_governance():
    policy = _read(POLICY)
    for text in ('승인된 범위에서 불필요한 확인 질문 없이 즉시 수행',
                 'Owner를 실제 호출', '실제 ACK 전에는 수행 중이라고 보고하지 않는다',
                 '최종 판단과 승인은 Sinclair에게', '외부 연락은 Sinclair 승인 전 내부 초안'):
        assert text in policy


def test_staff_executes_without_restarting_socratic_mode():
    policy = _read(POLICY)
    assert 'Staff는 Demian의 명확한 brief를 받으면 즉시 실행' in policy
    assert '다시 Socratic Mode로 시작하지 않는다' in policy
    assert 'bot-to-bot 재인터뷰는 금지' in policy
    for profile in STAFF_PROFILES:
        for name in ('AGENTS.md', 'SOUL.md'):
            source = _read(ROOT / f'operations/agents/{profile}/{name}')
            assert 'AI Tutor' in source
            assert 'ai-problem-solving-policy.md' in source
            assert 'Demian에만 적용' not in source


@pytest.mark.parametrize('role', ('default', 'demian'))
def test_demian_prompt_sources_point_to_single_tutoring_contract(role):
    source = ROOT / ('operations/governance' if role == 'default'
                     else f'operations/agents/{role}')
    agents = _read(source / 'AGENTS.md')
    assert '전 Staff Problem-Solving / AI Tutor' in agents
    assert 'EXECUTION / FACT / SOCRATIC / RECOMMENDATION' in agents
    assert 'AI Tutor' in _read(source / 'SOUL.md')
    assert 'ai-problem-solving-policy.md' in agents


@pytest.mark.parametrize('role', ('default', 'demian'))
def test_default_context_cap_keeps_full_assembled_tutoring(tmp_path, monkeypatch, role):
    assembler = _assembler()
    target = assembler.materialize(ROOT, role, tmp_path / role)
    monkeypatch.setenv('HERMES_HOME', str(target))
    result = assembler.verify_native(ROOT, role, target)
    assert result['truncated'] is False
    assert result['context_prompt'].count(_read(POLICY)) == 1
    assert '한 응답에 최대 하나의 집중 질문' in result['context_prompt']
    source = ROOT / ('operations/governance' if role == 'default'
                     else f'operations/agents/{role}')
    assert _read(source / 'AGENTS.md') in result['context_prompt']
    assert _read(source / 'SOUL.md') in result['soul_prompt']
