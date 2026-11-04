"""Vault-relative paths remain Obsidian/FTS-compatible on Windows and Linux."""
from scripts.memory_index import search, update_index
from scripts.wiki_compile import snapshot_wiki_space
from scripts.wiki_init import init_wiki_space
from scripts.wiki_lint import lint_space
from scripts.wiki_ingest import _build_raw_frontmatter
from scripts.generate_notes import render_note_md
import yaml


def test_nested_fts_folder_filter_returns_portable_paths(tmp_path):
    vault = tmp_path / 'vault'
    nested = vault / 'Notes/Deep/Knowledge.md'
    nested.parent.mkdir(parents=True)
    nested.write_text('# Knowledge\nportablequartz\n', encoding='utf-8')
    config = {'vault': {'vault_path': str(vault)}, 'memory': {'db_dir': str(tmp_path / 'index')}}
    update_index(config, full=True, quiet=True)
    hits = search(config, 'portablequartz', folder='Notes')
    assert [h['path'] for h in hits] == ['Notes/Deep/Knowledge.md']


def test_wiki_snapshot_and_lint_use_portable_relative_keys(tmp_path):
    root = tmp_path / 'demo'
    init_wiki_space(root=root, slug='demo', mode='project', title='Demo', description='', force=False)
    snapshot = snapshot_wiki_space(root)
    assert 'pages/overview.md' in snapshot['pages']
    assert all('\\' not in key for key in snapshot['pages'])
    assert lint_space(root) == []


def test_windows_source_paths_survive_yaml_roundtrip():
    source = 'C:\\Users\\example\\Documents\\Research "quoted".md'
    raw = _build_raw_frontmatter('demo', 'source', source, '2026-01-01')
    assert yaml.safe_load(raw.split('---', 2)[1])['raw_source'] == source
    note = render_note_md({'title': 'Test', 'source_doc': source, 'note_type': 'atomic',
                           'tags': ['tech/ai'], 'date': '2026-01-01', 'body': 'Body'})
    assert yaml.safe_load(note.split('---', 2)[1])['source_doc'] == source
