import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('merge_prompt', Path(__file__).resolve().parents[1] / 'scripts/merge-prompt.py')
prompts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompts)


class PromptTests(unittest.TestCase):
    def test_independent_block_preserves_owner_stack_bom_crlf_and_replays(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, target = root / 'source.md', root / 'GEMINI.md'
            original = '\ufeffPersonal instructions\r\n<!-- scrooge-stack:begin -->\r\nKeep other stack rules\r\n<!-- scrooge-stack:end -->\r\n'
            target.write_bytes(original.encode('utf-8'))
            source.write_text('Obsidian rules\n', encoding='utf-8')
            self.assertTrue(prompts.merge(source, target, 'scrooge-obsidian'))
            first = target.read_bytes()
            self.assertTrue(first.startswith(original.encode('utf-8')))
            self.assertEqual(first.count(b'<!-- scrooge-obsidian:begin -->'), 1)
            self.assertFalse(prompts.merge(source, target, 'scrooge-obsidian'))
            self.assertEqual(target.read_bytes(), first)
            source.write_text('New Obsidian rules\n', encoding='utf-8')
            self.assertTrue(prompts.merge(source, target, 'scrooge-obsidian'))
            self.assertTrue(target.read_bytes().startswith(original.encode('utf-8')))
            self.assertEqual(len(list(root.glob('GEMINI.md.bak.*'))), 2)

    def test_invalid_marker_or_name_preserves_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, target = root / 'source.md', root / 'GEMINI.md'
            source.write_text('Rules')
            for old in ['Owner\n<!-- scrooge-obsidian:begin -->\n', '<!-- scrooge-obsidian:end -->\n<!-- scrooge-obsidian:begin -->']:
                target.write_text(old)
                with self.assertRaises(ValueError):
                    prompts.merge(source, target, 'scrooge-obsidian')
                self.assertEqual(target.read_text(), old)
            with self.assertRaises(ValueError):
                prompts.merge(source, target, 'invalid -->')

    def test_default_block_stays_compatible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, target = root / 'source.md', root / 'AGENTS.md'
            source.write_text('Rules')
            prompts.merge(source, target)
            self.assertIn('<!-- scrooge-stack:begin -->', target.read_text())
