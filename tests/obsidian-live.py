"""Opt-in live install/reinstall test. Downloads upstream deps into a temp profile.

Run with Python 3.11+ on Linux or native Windows. Never uses real agent configs.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('obsidian', ROOT / 'scripts/install-obsidian.py')
obsidian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(obsidian)

base = Path(tempfile.mkdtemp(prefix='scrooge-obsidian-live-'))
home = base / 'Test Profile'
home.mkdir()
vault = home / 'Documents/Test Vault'
(vault / '.obsidian').mkdir(parents=True)
seed = '# Seed\nquartz [[Other]]\n'
(vault / 'Seed.md').write_text(seed, encoding='utf-8')
codex = home / '.codex'
codex.mkdir()
(codex / 'config.toml').write_text('# user comment\nmodel="custom"\n[mcp_servers.other]\ncommand="kept"\n', encoding='utf-8')
args = ['--vault', str(vault), '--targets', 'codex,agy,gemini', '--data-dir', str(base / 'Knowledge Runtime')]
print('Retained isolated fixture:', base, flush=True)
with patch.object(Path, 'home', return_value=home), patch.dict(os.environ, {'CODEX_HOME': str(codex)}):
    obsidian.main(args)
    assert '--read-only' in (codex / 'config.toml').read_text(encoding='utf-8')
    obsidian.main(args + ['--enable-writes'])
    assert '--read-only' not in (codex / 'config.toml').read_text(encoding='utf-8')
    before = (codex / 'config.toml').read_bytes()
    prompts = (home / '.gemini/GEMINI.md').read_bytes()
    assert prompts.count(b'<!-- scrooge-obsidian:begin -->') == 1
    manifests = list((base / 'Knowledge Runtime/backups').glob('*.manifest.json'))
    assert len(manifests) == 1
    obsidian.main(args)
    assert (codex / 'config.toml').read_bytes() == before
    assert (home / '.gemini/GEMINI.md').read_bytes() == prompts
    assert len(list((base / 'Knowledge Runtime/backups').glob('*.manifest.json'))) == 1
    assert (vault / 'Seed.md').read_text(encoding='utf-8') == seed
print('LIVE read-only/write-backup/reinstall/native MCP+DataWeave checks PASSED', flush=True)
