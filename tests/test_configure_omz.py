import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/configure-omz.py'
spec = importlib.util.spec_from_file_location('configure_omz', MODULE)
omz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(omz)


class ConfigureOmzTests(unittest.TestCase):
    def test_preserves_unrelated_content_backup_and_reinstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.zshrc'
            original = 'export PATH="$HOME/bin:$PATH"\nZSH_THEME="old"\nplugins=(git)\nsource "$ZSH/oh-my-zsh.sh"\nalias a=b\n'
            path.write_text(original)
            self.assertTrue(omz.configure(path, dry_run=True))
            self.assertEqual(path.read_text(), original)
            self.assertTrue(omz.configure(path))
            result = path.read_text()
            self.assertIn('export PATH="$HOME/bin:$PATH"\n', result)
            self.assertIn('alias a=b\n', result)
            self.assertIn("zstyle ':omz:update' mode auto\n", result)
            self.assertEqual(list(Path(tmp).glob('.zshrc.bak.*'))[0].read_text(), original)
            self.assertFalse(omz.configure(path))
            self.assertEqual(path.read_text(), result)

    def test_ambiguous_assignments_do_not_modify_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.zshrc'
            original = 'plugins=(git)\nplugins=(docker)\nsource "$ZSH/oh-my-zsh.sh"\n'
            path.write_text(original)
            with self.assertRaises(ValueError):
                omz.configure(path)
            self.assertEqual(path.read_text(), original)
            self.assertEqual(list(Path(tmp).glob('*.bak.*')), [])

    def test_setting_after_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.zshrc'
            original = 'source "$ZSH/oh-my-zsh.sh"\nplugins=(git)\n'
            path.write_text(original)
            with self.assertRaises(ValueError):
                omz.configure(path)
            self.assertEqual(path.read_text(), original)


if __name__ == '__main__':
    unittest.main()
