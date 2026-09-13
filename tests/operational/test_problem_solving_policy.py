"""Structural contracts only: NOT evidence of actual LLM compliance."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
ROLES = ('demian', 'hans', 'wendy', 'tesla', 'turing', 'watson', 'mason')
POLICY = ROOT / 'operations/docs/ai-problem-solving-policy.md'


def test_canonical_all_staff_contract_exists():
    assert POLICY.is_file(), 'Approved all-staff canonical contract is missing'
    text = POLICY.read_text()
    for role in ROLES:
        assert role.capitalize() in text
    for section in ('EXECUTION', 'SOCRATIC', 'WHO', 'WHAT', 'WHY', 'QUESTION', 'NEEDED-BY', 'NEXT ACTION', 'Customer Commitment', 'Issue→Resolution'):
        assert section in text


@pytest.mark.parametrize('role', ROLES)
def test_staff_points_to_common_contract_without_competing_tutor(role):
    for name in ('SOUL.md', 'AGENTS.md'):
        text = (ROOT / 'operations/agents' / role / name).read_text()
        assert 'ai-problem-solving-policy.md' in text
        assert 'Demian에만 적용' not in text
        assert '질문을 정확히 하나' not in text


def test_legacy_exclusions_removed():
    for relative in ('operations/docs/demian-ai-tutoring.md', 'operations/governance/AGENTS.md', 'operations/agents/demian/AGENTS.md'):
        text = (ROOT / relative).read_text()
        assert '비적용 대상: Hans' not in text
        assert '한 응답에는 질문을 정확히 하나만 한다' not in text
        assert '이 모드는 Sinclair ↔ Demian에만 적용한다' not in text


def test_common_entry_is_small_and_explicit():
    path = ROOT / 'operations/agents/AGENTS.md'
    assert path.is_file()
    text = path.read_text()
    assert len(text) < 5000
    assert 'ai-problem-solving-policy.md' in text
    assert '자동' in text and 'Sinclair' in text
