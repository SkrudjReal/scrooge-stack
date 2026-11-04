import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_obsidian', ROOT / 'scripts/install-obsidian.py')
obsidian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(obsidian)


class ObsidianTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.codex = self.home / '.codex'
        self.vault = self.home / 'Documents/Vault with spaces'
        (self.vault / '.obsidian').mkdir(parents=True)
        self.data = self.base / 'runtime'
        self.server = self.data / 'npm/node_modules/@bitbonsai/mcpvault/dist/server.js'
        self.node = str(self.base / 'node')

    def plans(self, targets=('codex', 'agy', 'gemini'), write=False):
        return obsidian.plan_configs(self.home, self.codex, list(targets), self.vault,
                                      self.node, self.server, write)

    def persist(self, plans):
        for path, text, _ in plans:
            obsidian.save(path, text)

    def test_explicit_existing_vault_and_invalid_path(self):
        self.assertEqual(obsidian.discover_vault(str(self.vault), self.home, self.codex), self.vault)
        with self.assertRaisesRegex(ValueError, 'Not an existing'):
            obsidian.discover_vault(str(self.base / 'missing'), self.home, self.codex)
        self.assertFalse((self.base / 'missing').exists())

    def test_native_children_use_utf8_for_unicode_pipes(self):
        result = obsidian.run(sys.executable, '-c', 'import sys; print(sys.stdout.encoding); print("\u00ab\u041f\u0430\u043c\u044f\u0442\u044c\u00bb")',
                              capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.stdout.splitlines(), ['utf-8', '\u00ab\u041f\u0430\u043c\u044f\u0442\u044c\u00bb'])

    def test_registry_resolves_nonstandard_vault(self):
        registry = self.home / '.config/obsidian/obsidian.json'
        registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps({'vaults': {'id': {'path': str(self.vault), 'open': False}}}))
        with patch.object(obsidian.sys, 'platform', 'win32'):
            self.assertEqual(obsidian.discover_vault(None, self.home, self.codex), self.vault)

    def test_auto_discovery_refuses_ambiguous_choice(self):
        (self.home / 'Documents/Other/.obsidian').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'Multiple vaults'):
            obsidian.discover_vault(None, self.home, self.codex)

    def test_no_vault_does_not_create_one(self):
        empty = self.base / 'empty'
        empty.mkdir()
        with patch.object(obsidian.sys, 'platform', 'win32'):
            self.assertIsNone(obsidian.discover_vault(None, empty, empty / '.codex'))
        self.assertEqual(list(empty.iterdir()), [])

    def test_configured_vault_wins_over_other_candidates(self):
        self.persist(self.plans(('codex',)))
        (self.home / 'Documents/Other/.obsidian').mkdir(parents=True)
        self.assertEqual(obsidian.discover_vault(None, self.home, self.codex), self.vault)

    def test_merge_all_hosts_preserves_existing_and_is_idempotent(self):
        obsidian.save(self.codex / 'config.toml', '# user comment\nmodel = "custom"\n[mcp_servers.other]\ncommand = "kept"\n')
        for relative in ['.gemini/config/mcp_config.json', '.gemini/settings.json']:
            obsidian.save(self.home / relative, json.dumps({'other': 42, 'mcpServers': {'other': {'command': 'kept'}}}))
        self.persist(self.plans())
        snapshots = [(p, p.read_bytes()) for p, _, _ in self.plans()]
        self.persist(self.plans())
        self.assertEqual([(p, p.read_bytes()) for p, _ in snapshots], snapshots)
        config = tomllib.loads((self.codex / 'config.toml').read_text())
        self.assertEqual(config['model'], 'custom')
        self.assertEqual(config['mcp_servers']['other']['command'], 'kept')
        entry = config['mcp_servers']['mcpvault']
        self.assertIn('--read-only', entry['args'])
        self.assertEqual(entry['default_tools_approval_mode'], 'writes')
        self.assertEqual(len(entry['tools']), 11)
        self.assertIn('# user comment', (self.codex / 'config.toml').read_text())
        for relative in ['.gemini/config/mcp_config.json', '.gemini/settings.json']:
            config = json.loads((self.home / relative).read_text())
            self.assertEqual(config['other'], 42)
            self.assertEqual(config['mcpServers']['other']['command'], 'kept')

    def test_write_transition_changes_only_args_and_preserves_prior_writes(self):
        self.persist(self.plans())
        before = tomllib.loads((self.codex / 'config.toml').read_text())
        plans = self.plans(write=True)
        self.assertTrue(all(p[2] for p in plans))
        self.persist(plans)
        after = tomllib.loads((self.codex / 'config.toml').read_text())
        before['mcp_servers']['mcpvault']['args'].remove('--read-only')
        self.assertEqual(before, after)
        readonly_rerun = self.plans(write=False)
        self.assertTrue(all(not p[2] for p in readonly_rerun))
        self.assertNotIn('--read-only', readonly_rerun[0][1])

    def test_multiline_toml_args_preserve_adjacent_tables(self):
        text = ('[mcp_servers.mcpvault]\nargs = [\n "server",\n "vault", # keep valid TOML\n "--read-only"\n]\n'
                'enabled = false\n[mcp_servers.other]\ncommand = "other"\n')
        changed = obsidian.replace_args(text, ['server', 'vault'])
        config = tomllib.loads(changed)
        self.assertEqual(config['mcp_servers']['mcpvault']['args'], ['server', 'vault'])
        self.assertFalse(config['mcp_servers']['mcpvault']['enabled'])
        self.assertEqual(config['mcp_servers']['other']['command'], 'other')

    def test_conflict_and_malformed_configs_are_preserved(self):
        path = self.codex / 'config.toml'
        for content in ['[bad', '[mcp_servers.mcpvault]\ncommand="other"\nargs=[]\n']:
            obsidian.save(path, content)
            with self.assertRaises(ValueError):
                self.plans(('codex',))
            self.assertEqual(path.read_text(), content)
        path = self.home / '.gemini/settings.json'
        for content in ['["bad root"]', '{"mcpServers":[]}', '{"mcpServers":{"mcpvault":{"args":[]}}}']:
            obsidian.save(path, content)
            with self.assertRaises(ValueError):
                self.plans(('gemini',))
            self.assertEqual(path.read_text(), content)

    def test_backup_is_hashed_and_does_not_follow_symlinks(self):
        note = self.vault / 'личная.md'
        note.write_text('# Personal\n[[Other]]', encoding='utf-8')
        (self.vault / '.smart-env').mkdir()
        (self.vault / '.smart-env/cache').write_text('cache')
        outside = self.base / 'outside'
        outside.write_text('never read')
        (self.vault / 'link.md').symlink_to(outside)
        saved = obsidian.backup_vault(self.vault, self.data)
        self.assertEqual((saved / note.name).read_bytes(), note.read_bytes())
        self.assertTrue((saved / 'link.md').is_symlink())
        manifest = json.loads(saved.with_suffix('.manifest.json').read_text())
        self.assertIn(note.name, manifest['sha256'])
        self.assertNotIn('link.md', manifest['sha256'])
        self.assertFalse((saved / '.smart-env').exists())

    def test_dry_run_no_config_or_note_mutations(self):
        with patch.object(Path, 'home', return_value=self.home), patch.dict(os.environ, {'CODEX_HOME': str(self.codex)}):
            obsidian.main(['--vault', str(self.vault), '--targets', 'codex', '--data-dir', str(self.data), '--dry-run'])
        self.assertFalse(self.data.exists())
        self.assertFalse(self.codex.exists())
        self.assertEqual(list(self.vault.iterdir()), [self.vault / '.obsidian'])

    def test_runtime_inside_vault_refused(self):
        with patch.object(Path, 'home', return_value=self.home), patch.dict(os.environ, {'CODEX_HOME': str(self.codex)}):
            with self.assertRaisesRegex(ValueError, 'outside the vault'):
                obsidian.main(['--vault', str(self.vault), '--data-dir', str(self.vault / 'runtime'), '--dry-run'])

    def test_configure_dataweave_keeps_existing_custom_settings(self):
        repo = self.base / 'repo'
        repo.mkdir()
        text = '[vault]\nvault_path = ' + json.dumps(str(self.vault)) + '\nnotes_folder="custom"\n'
        obsidian.save(repo / 'config.toml', text)
        obsidian.configure_dataweave(repo, self.vault, self.data)
        self.assertEqual((repo / 'config.toml').read_text(), text)
        with self.assertRaises(ValueError):
            obsidian.configure_dataweave(repo, self.base / 'other', self.data)

    def test_no_transition_preserves_utf8_bom_and_crlf(self):
        self.persist(self.plans(('codex',)))
        path = self.codex / 'config.toml'
        content = b'\xef\xbb\xbf' + path.read_bytes().replace(b'\n', b'\r\n')
        path.write_bytes(content)
        self.persist(self.plans(('codex',)))
        self.assertEqual(path.read_bytes(), content)


if __name__ == '__main__':
    unittest.main()
