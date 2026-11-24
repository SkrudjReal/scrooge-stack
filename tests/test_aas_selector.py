import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('aas_select', Path(__file__).resolve().parents[1] / 'skills/aas-skill-selector/scripts/select.py')
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.payload = {'task': 'Test Python', 'capabilities': {'testing': [{'id': 'pytest-skill', 'description': 'pytest'}]}}
        self.answer = {'name': 'testing', 'type': 'choice', 'choice': 'pytest-skill', 'confidence': .9}

    def run_selection(self, answers):
        with patch.object(selector.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value = io.StringIO(json.dumps({'answers': answers}))
            result = selector.select(self.payload, 'test-key')
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api.openai.com/v1/decisions')
            self.assertEqual(json.loads(request.data)['questions'][0]['choices'][0]['value'], 'pytest-skill')
            return result

    def test_valid_selection(self):
        self.assertEqual(self.run_selection([self.answer])['answers'][0]['choice'], 'pytest-skill')

    def test_bad_or_uncertain_answers(self):
        for changes in [{'choice': 'invented'}, {'confidence': .4}, {'confidence': True}, {'type': 'refusal'}, {'name': 'other'}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_selection([{**self.answer, **changes}])
        with self.assertRaises(ValueError):
            self.run_selection([self.answer, self.answer])

    def test_missing_key_falls_back_without_network(self):
        with patch.dict(selector.os.environ, {}, clear=True), patch.object(selector.sys, 'argv', ['select.py']), patch('sys.stdout', new_callable=io.StringIO) as output, patch.object(selector.urllib.request, 'build_opener') as opener:
            self.assertEqual(selector.main(), 2)
            self.assertEqual(json.loads(output.getvalue())['reason'], 'missing_api_key')
            opener.assert_not_called()

    def test_http_error_falls_back_without_secret(self):
        with patch.dict(selector.os.environ, {'OPENAI_API_KEY': 'private-test-key'}, clear=True), patch.object(selector.sys, 'argv', ['select.py']), patch('sys.stdin', io.StringIO(json.dumps(self.payload))), patch('sys.stdout', new_callable=io.StringIO) as output, patch.object(selector.urllib.request, 'build_opener', side_effect=OSError('private-test-key')):
            self.assertEqual(selector.main(), 2)
            self.assertNotIn('private-test-key', output.getvalue())


if __name__ == '__main__':
    unittest.main()
