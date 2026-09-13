"""TSK62 native loading of preserved b56 policy; NOT LLM behavior evaluation."""
import importlib.util
import json
from pathlib import Path
import pytest
from agent import prompt_builder

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'operations/scripts/assemble-problem-solving-policy.py'
ROLES = ('default', 'demian', 'hans', 'wendy', 'tesla', 'turing', 'watson', 'mason')


def helper():
    assert SCRIPT.is_file(), 'Native candidate bundle assembler missing'
    spec = importlib.util.spec_from_file_location('tsk63_assembly', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize('role', ROLES)
def test_native_full_contract_exactly_once_per_role(tmp_path, monkeypatch, role):
    mod = helper()
    # Keep actual native context evidence under the approved TSK62 root: the
    # canonical runner removes pytest tmp directories after each file.
    import tempfile
    evidence = Path(tempfile.mkdtemp(prefix='policy-native-', dir=mod.EVIDENCE_ROOT))
    target = evidence / role
    mod.materialize(ROOT, role, target)
    monkeypatch.setenv('HERMES_HOME', str(target))
    monkeypatch.chdir(target)
    result = mod.verify_native(ROOT, role, target)
    assert result['process_cwd'] == str(target.resolve())
    assert result['hermes_home'] == result['cwd'] == str(target.resolve())
    assert Path(result['native_loader']) == ROOT / 'agent/prompt_builder.py'
    (target / 'effective-context.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    canonical = (ROOT / 'operations/docs/ai-problem-solving-policy.md').read_text().strip()
    assert result['effective_prompt'].count(canonical) == 1
    source = ROOT / ('operations/governance' if role == 'default' else f'operations/agents/{role}')
    assert (source / 'SOUL.md').read_text().strip() in result['effective_prompt']
    assert (source / 'AGENTS.md').read_text().strip() in result['effective_prompt']
    assert result['native_loader_sha256']
    assert result['truncated'] is False


def test_pointer_alone_does_not_load_contract(tmp_path, monkeypatch):
    (tmp_path / 'AGENTS.md').write_text('See operations/docs/ai-problem-solving-policy.md')
    monkeypatch.setattr(prompt_builder, 'get_hermes_home', lambda: tmp_path)
    result = prompt_builder.build_context_files_prompt(cwd=str(tmp_path), skip_soul=True)
    assert 'TSK63-CANONICAL-BEGIN' not in result


def test_native_truncation_fails_closed(tmp_path, monkeypatch):
    mod = helper()
    target = tmp_path / 'hans'
    mod.materialize(ROOT, 'hans', target)
    monkeypatch.setenv('HERMES_HOME', str(target))
    monkeypatch.setattr(prompt_builder, 'get_hermes_home', lambda: target)
    monkeypatch.setattr(prompt_builder, '_get_context_file_max_chars', lambda *a: 1000)
    with pytest.raises(ValueError, match='truncated|incomplete'):
        mod.verify_native(ROOT, 'hans', target)


def test_higher_priority_context_fails_closed(tmp_path, monkeypatch):
    mod = helper()
    target = tmp_path / 'mason'
    mod.materialize(ROOT, 'mason', target)
    (target / '.hermes.md').write_text('Higher priority project context')
    monkeypatch.setenv('HERMES_HOME', str(target))
    monkeypatch.setattr(prompt_builder, 'get_hermes_home', lambda: target)
    with pytest.raises(ValueError, match='incomplete'):
        mod.verify_native(ROOT, 'mason', target)


def test_existing_target_is_never_overwritten(tmp_path):
    mod = helper()
    path = tmp_path / 'existing'
    path.mkdir()
    (path / 'SOUL.md').write_text('keep')
    with pytest.raises(FileExistsError):
        mod.materialize(ROOT, 'hans', path)
    assert (path / 'SOUL.md').read_text() == 'keep'


@pytest.mark.parametrize('target', [
    '/opt/hermes/tsk63-candidate', '/opt/data/profiles/tsk63-candidate',
    '/opt/data/agents/tsk63-candidate', '/opt/data/tsk63-candidate',
    '/tmp/tsk63-unapproved',
    '/opt/data/cache/problem-solving-policy-9ufby77a/tsk62-candidate',
    '/opt/data/cache/tsk62-v0212-development-hfr6lbjs',
])
def test_materialization_rejects_non_evidence_destinations(target):
    with pytest.raises(ValueError, match='evidence root'):
        helper().materialize(ROOT, 'hans', Path(target))


def test_symlink_escape_and_target_traversal_rejected(tmp_path):
    mod = helper()
    link = tmp_path / 'escape'
    link.symlink_to('/opt/hermes', target_is_directory=True)
    with pytest.raises(ValueError, match='evidence root'):
        mod.materialize(ROOT, 'hans', link / 'tsk63-candidate')
    with pytest.raises(ValueError, match='traversal'):
        mod.materialize(ROOT, 'hans', tmp_path / 'unused' / '..' / 'candidate')


@pytest.mark.parametrize('name', ['.hermes.md', 'HERMES.md', 'AGENTS.override.md'])
def test_selected_higher_priority_source_is_preserved_and_observed(tmp_path, monkeypatch, name):
    mod = helper()
    target = mod.materialize(ROOT, 'hans', tmp_path / 'hans')
    selected = target / name
    selected.write_text('Preserve higher priority source')
    monkeypatch.setenv('HERMES_HOME', str(target))
    with pytest.raises(mod.NativeVerificationError, match='incomplete') as exc:
        mod.verify_native(ROOT, 'hans', target)
    assert 'Preserve higher priority source' in exc.value.result['effective_prompt']
    assert selected.read_text() == 'Preserve higher priority source'


def test_duplicate_contract_fails_closed(tmp_path, monkeypatch):
    mod = helper()
    target = mod.materialize(ROOT, 'hans', tmp_path / 'hans')
    canonical = (ROOT / 'operations/docs/ai-problem-solving-policy.md').read_text()
    with (target / 'AGENTS.md').open('a') as stream:
        stream.write('\n' + canonical)
    monkeypatch.setenv('HERMES_HOME', str(target))
    with pytest.raises(ValueError, match='incomplete|truncated'):
        mod.verify_native(ROOT, 'hans', target)


def test_source_soul_bytes_preserved(tmp_path, monkeypatch):
    mod = helper()
    target = mod.materialize(ROOT, 'hans', tmp_path / 'hans')
    source = ROOT / 'operations/agents/hans/SOUL.md'
    assert (target / 'SOUL.md').read_bytes() == source.read_bytes()
    with (target / 'SOUL.md').open('a') as stream:
        stream.write('\nUnexpected extra identity')
    monkeypatch.setenv('HERMES_HOME', str(target))
    with pytest.raises(ValueError, match='incomplete'):
        mod.verify_native(ROOT, 'hans', target)


def test_missing_home_rejected_without_native_initialization(tmp_path, monkeypatch):
    mod = helper()
    target = mod.materialize(ROOT, 'hans', tmp_path / 'hans')
    monkeypatch.delenv('HERMES_HOME', raising=False)
    with pytest.raises(ValueError, match='HERMES_HOME'):
        mod.verify_native(ROOT, 'hans', target)


def test_unknown_role_and_live_home_are_rejected(tmp_path, monkeypatch):
    mod = helper()
    with pytest.raises(ValueError, match='role'):
        mod.materialize(ROOT, '../hans', tmp_path / 'bad')
    target = tmp_path / 'hans'
    mod.materialize(ROOT, 'hans', target)
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'unrelated'))
    with pytest.raises(ValueError, match='HERMES_HOME'):
        mod.verify_native(ROOT, 'hans', target)
