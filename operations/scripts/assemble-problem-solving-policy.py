#!/usr/bin/env python3
"""TSK62 isolated candidate assembly; never installs or changes native limits.

CLI: HERMES_HOME=<target> python this_script.py ROLE TARGET [--verify-only]
The caller must provide the candidate native runtime on PYTHONPATH. JSON stdout
contains the actual SOUL + project-context fragment, NOT the entire LLM prompt.
Only fresh descendants of the approved task evidence directory are writable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

# TSK62 candidate-only binding. Never use the historical TSK63 evidence root.
EVIDENCE_ROOT = Path('/opt/data/cache/tsk62-v0212-development-hfr6lbjs')
ROLES = ('default', 'demian', 'hans', 'wendy', 'tesla', 'turing', 'watson', 'mason')


class NativeVerificationError(ValueError):
    """Fail closed while retaining the actual observed context for diagnostics."""

    def __init__(self, message, result):
        super().__init__(message)
        self.result = result


def _target(target):
    path = Path(target)
    if '..' in path.parts:
        raise ValueError('target path traversal is forbidden')
    resolved = path.resolve()
    # An allowlist, not a denylist: this excludes live homes and install trees,
    # including symlink escapes from the evidence directory.
    if resolved == EVIDENCE_ROOT or not resolved.is_relative_to(EVIDENCE_ROOT):
        raise ValueError('target must be a descendant of the approved evidence root')
    return resolved


def _sources(root, role):
    if role not in ROLES:
        raise ValueError(f'unknown role: {role!r}')
    root = Path(root).resolve()
    source = root / ('operations/governance' if role == 'default'
                     else f'operations/agents/{role}')
    paths = {
        'canonical': root / 'operations/docs/ai-problem-solving-policy.md',
        'common': root / 'operations/agents/AGENTS.md',
        'role_agents': source / 'AGENTS.md',
        'role_soul': source / 'SOUL.md',
    }
    contents = {key: path.read_text(encoding='utf-8').strip()
                for key, path in paths.items()}
    if not all(contents.values()):
        raise ValueError('incomplete source policy')
    return paths, contents


def materialize(root, role, target):
    """Combine three unchanged contracts once and copy SOUL byte-for-byte."""
    paths, contents = _sources(root, role)
    raw_target = Path(target)
    target = _target(target)
    if raw_target.is_symlink() or target.exists():
        raise FileExistsError(str(raw_target))
    agents = '\n\n'.join(contents[key] for key in
                         ('canonical', 'common', 'role_agents')) + '\n'
    if agents.count(contents['canonical']) != 1:
        raise ValueError('canonical contract must occur exactly once')
    # mkdir(exist_ok=False) reserves a fresh directory; no overwrite mode.
    target.mkdir(parents=True, exist_ok=False)
    with (target / 'AGENTS.md').open('x', encoding='utf-8') as stream:
        stream.write(agents)
    with (target / 'SOUL.md').open('xb') as stream:
        stream.write(paths['role_soul'].read_bytes())
    return target


def verify_native(root, role, target):
    """Exercise REAL native selection, scanning and caps, without patching it."""
    paths, contents = _sources(root, role)
    target = _target(target)
    if os.environ.get('HERMES_HOME') != str(target):
        raise ValueError('HERMES_HOME must exactly match the resolved candidate target')
    if not target.is_dir():
        raise ValueError('incomplete candidate target')
    from agent import prompt_builder

    if Path(prompt_builder.get_hermes_home()).resolve() != target:
        raise ValueError('native HERMES_HOME does not match candidate target')
    loader = Path(prompt_builder.__file__).resolve()
    digest = hashlib.sha256(loader.read_bytes()).hexdigest()
    # v0.2.12 is a full native checkout, not the old partial runtime-src overlay.
    expected = (Path(root) / 'agent/prompt_builder.py').resolve()
    if loader != expected or digest != hashlib.sha256(expected.read_bytes()).hexdigest():
        raise ValueError('native loader differs from candidate runtime source')
    soul = prompt_builder.load_soul_md()
    context = prompt_builder.build_context_files_prompt(cwd=str(target), skip_soul=True)
    effective = '\n\n'.join(part for part in (soul, context) if part)
    result = {
        'role': role, 'hermes_home': str(target), 'cwd': str(target),
        'process_cwd': str(Path.cwd().resolve()),
        'native_loader': str(loader), 'native_loader_sha256': digest,
        'source_sha256': {key: hashlib.sha256(path.read_bytes()).hexdigest()
                          for key, path in paths.items()},
        'soul_prompt': soul, 'context_prompt': context,
        'effective_prompt': effective,
        'truncated': '[...truncated ' in effective,
        'scope': 'native SOUL and project context only; not LLM behavior',
    }
    missing = [key for key, text in contents.items() if text not in effective]
    if (result['truncated'] or missing or
            effective.count(contents['canonical']) != 1 or
            not context.startswith('# Project Context\n') or
            '\n## AGENTS.md\n' not in context or
            (target / 'SOUL.md').read_bytes() != paths['role_soul'].read_bytes()):
        raise NativeVerificationError(
            f'native policy truncated or incomplete (missing={missing})', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=ROLES)
    parser.add_argument('target', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        # Validate before materializing; never silently change the caller's home.
        if os.environ.get('HERMES_HOME') != str(_target(args.target)):
            raise ValueError('HERMES_HOME must exactly match the candidate target')
        if not args.verify_only:
            materialize(root, args.role, args.target)
        result = verify_native(root, args.role, args.target)
    except (ValueError, OSError) as error:
        print(json.dumps({'error': str(error), 'observed': getattr(error, 'result', None)},
                         ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
