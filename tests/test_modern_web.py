import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('modern_web', ROOT / 'scripts/install-modern-web.py')
modern = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modern)


class ModernWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'source with spaces'
        self.source = self.repo / 'skills/modern-web-guidance'
        (self.source / 'guides').mkdir(parents=True)
        (self.source / 'SKILL.md').write_text('Official skill')
        (self.source / 'guides/dialog.md').write_text('Dialog guide')
        (self.repo / 'LICENSE').write_text('Upstream license')
        self.dest = self.root / 'home/skills/modern-web-guidance'

    def test_copy_includes_guides_license_and_preserves_local_edits(self):
        modern.install_skill(self.source, self.dest)
        self.assertEqual((self.dest / 'guides/dialog.md').read_text(), 'Dialog guide')
        self.assertEqual((self.dest / 'LICENSE').read_text(), 'Upstream license')
        (self.dest / 'SKILL.md').write_text('Owner version')
        modern.install_skill(self.source, self.dest)
        self.assertEqual((self.dest / 'SKILL.md').read_text(), 'Owner version')

    def test_copy_failure_does_not_leave_partial_skill(self):
        with patch.object(modern.shutil, 'copy2', side_effect=OSError('copy failed')):
            with self.assertRaisesRegex(OSError, 'copy failed'):
                modern.install_skill(self.source, self.dest)
        self.assertFalse(self.dest.exists())
        self.assertEqual(list(self.dest.parent.iterdir()), [])

    def test_dangling_destination_is_preserved(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.symlink_to(self.root / 'missing', target_is_directory=True)
        modern.install_skill(self.source, self.dest)
        self.assertTrue(self.dest.is_symlink())

    def test_checkout_rejects_non_git_and_wrong_origin_and_incomplete_source(self):
        with self.assertRaisesRegex(ValueError, 'existing path'):
            modern.checkout(self.repo)
        (self.repo / '.git').mkdir()
        with patch.object(modern.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='https://example.com/other.git\n')):
            with self.assertRaisesRegex(ValueError, 'Unexpected Git origin'):
                modern.checkout(self.repo)
        with patch.object(modern.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout=modern.UPSTREAM)):
            self.assertEqual(modern.checkout(self.repo), self.source)
            (self.repo / 'LICENSE').unlink()
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                modern.checkout(self.repo)

    def test_clone_failure_propagates(self):
        with patch.object(modern.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['git'])):
            with self.assertRaises(subprocess.CalledProcessError):
                modern.checkout(self.root / 'new source')

    def test_all_host_paths_and_custom_codex_home(self):
        with patch.dict(os.environ, CODEX_HOME=str(self.root / 'custom codex')):
            self.assertEqual(modern.destinations(self.root, ['codex', 'agy', 'gemini']), [
                self.root / 'custom codex/skills/modern-web-guidance',
                self.root / '.gemini/config/skills/modern-web-guidance',
                self.root / '.gemini/skills/modern-web-guidance'])

    def test_dry_run_has_no_side_effects_or_subprocesses(self):
        with patch.object(modern.subprocess, 'run', side_effect=AssertionError('must not run')):
            modern.main(['--targets', 'codex,agy,gemini', '--data-dir', str(self.root / 'runtime'), '--dry-run'])
        self.assertFalse((self.root / 'runtime').exists())

    def test_old_node_and_invalid_targets_stop_before_clone(self):
        with patch.object(modern.shutil, 'which', return_value='/fake/node'), patch.object(
                modern.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='v20.0.0')), patch.object(modern, 'checkout') as clone:
            with self.assertRaisesRegex(ValueError, 'Node.js 22'):
                modern.main(['--targets', 'codex'])
            clone.assert_not_called()
        with self.assertRaises(SystemExit):
            modern.main(['--targets', 'codex,'])


if __name__ == '__main__':
    unittest.main()
