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
        self.answer = {'name': 'candidate_0', 'type': 'predicate', 'probability': .9}

    def run_selection(self, answers):
        candidates = [candidate for group in self.payload['capabilities'].values() for candidate in group]
        probabilities = {answer['name']: answer.get('probability', 0) for answer in answers}
        retained = list(dict.fromkeys(candidate['id'] for index, candidate in enumerate(candidates)
                                      if probabilities.get(f'candidate_{index}', 0) >= .75))
        refined = {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': json.dumps({'skillIds': retained})}]}]}
        with patch.object(selector, 'post', side_effect=[{'answers': answers}, refined]) as post:
            result = selector.select(self.payload, 'test-key')
            self.assertEqual(post.call_args_list[0].args[0], 'decisions')
            body = post.call_args_list[0].args[1]
            self.assertEqual(body['questions'][0]['type'], 'predicate')
            self.assertEqual(json.loads(body['input'])['candidates'][0]['id'], 'pytest-skill')
            return result

    def test_valid_selection(self):
        self.assertEqual(self.run_selection([self.answer])['answers'][0]['skillIds'], ['pytest-skill'])

    def test_uncertain_answer_is_retained_for_review(self):
        result = self.run_selection([{**self.answer, 'probability': .4}])
        self.assertEqual(result['answers'][0]['candidates'], [{'id': 'pytest-skill', 'probability': .4}])
        self.assertEqual(result['needs_review'], ['testing'])

    def test_no_match_is_retained_for_discovery_review(self):
        result = self.run_selection([{**self.answer, 'probability': .1}])
        self.assertEqual(result['answers'][0]['skillIds'], [])
        self.assertEqual(result['needs_review'], ['testing'])

    def test_uncertainty_does_not_discard_other_capabilities(self):
        self.payload['capabilities']['unit_tests'] = self.payload['capabilities']['testing']
        result = self.run_selection([self.answer, {**self.answer, 'name': 'candidate_1', 'probability': .4}])
        self.assertEqual(len(result['answers']), 2)
        self.assertEqual(result['needs_review'], ['unit_tests'])

    def test_bad_answers(self):
        for changes in [{'probability': -1}, {'probability': 1.1}, {'probability': True}, {'probability': float('nan')}, {'type': 'refusal'}, {'name': 'other'}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_selection([{**self.answer, **changes}])
        with self.assertRaises(ValueError):
            self.run_selection([self.answer, self.answer])

    def test_complementary_skills_are_selected_in_same_capability(self):
        self.payload['capabilities']['testing'] += [
            {'id': 'webapp-testing', 'description': 'Browser tests'},
            {'id': 'unrelated', 'description': 'Unrelated skill'}]
        result = self.run_selection([
            self.answer,
            {**self.answer, 'name': 'candidate_1', 'probability': .95},
            {**self.answer, 'name': 'candidate_2', 'probability': .1}])
        self.assertEqual(result['answers'][0]['skillIds'], ['pytest-skill', 'webapp-testing'])
        self.assertEqual(result['needs_review'], [])

    def test_deduplication_removes_alternative_but_keeps_complement(self):
        groups = {'testing': {'skillIds': ['pytest-skill', 'similar-unit-tests', 'webapp-testing']}}
        kept = ['pytest-skill', 'webapp-testing']
        response = {'status': 'completed', 'model': 'gpt-6-luna', 'service_tier': 'fast',
                    'output': [{'content': [{'type': 'output_text', 'text': json.dumps({'skillIds': kept})}]}]}
        with patch.object(selector, 'post', return_value=response) as post:
            result = selector.deduplicate('Unit tests and real browser tests', groups, [], 'test-key')
        self.assertEqual(groups['testing']['skillIds'], kept)
        self.assertEqual(result['removedSkillIds'], ['similar-unit-tests'])
        self.assertEqual(result['service_tier'], 'fast')
        endpoint, body, _ = post.call_args.args
        self.assertEqual(endpoint, 'responses')
        self.assertEqual(body['reasoning'], {'effort': 'low'})
        self.assertEqual(body['service_tier'], 'priority')
        self.assertFalse(body['store'])

    def test_deduplication_rejects_invalid_or_incomplete_results(self):
        for kept in [['invented'], ['unit', 'unit'], [], ['unit']]:
            groups = {'logic': {'skillIds': ['unit']}, 'browser': {'skillIds': ['browser']}}
            response = {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': json.dumps({'skillIds': kept})}]}]}
            with self.subTest(kept=kept), patch.object(selector, 'post', return_value=response), self.assertRaises(ValueError):
                selector.deduplicate('Test logic and browser', groups, [], 'test-key')
        with patch.object(selector, 'post', return_value={'status': 'incomplete'}), self.assertRaises(ValueError):
            selector.deduplicate('Test', {'testing': {'skillIds': ['unit', 'browser']}}, [], 'test-key')

    def test_single_selected_id_skips_second_api_call(self):
        with patch.object(selector, 'post') as post:
            result = selector.deduplicate('Test', {'testing': {'skillIds': ['unit']}}, [], 'test-key')
        self.assertTrue(result['skipped'])
        post.assert_not_called()

    def test_shared_id_is_returned_once_for_composition(self):
        self.payload['capabilities']['integration'] = self.payload['capabilities']['testing']
        result = self.run_selection([self.answer, {**self.answer, 'name': 'candidate_1'}])
        self.assertEqual(result['skillIds'], ['pytest-skill'])
        self.assertEqual(len(result['answers']), 2)
        self.assertTrue(result['deduplication']['skipped'])

    def test_reordered_answers_are_matched_by_name(self):
        self.payload['capabilities']['testing'].append({'id': 'webapp-testing', 'description': 'Browser tests'})
        result = self.run_selection([{**self.answer, 'name': 'candidate_1', 'probability': .1}, self.answer])
        self.assertEqual(result['answers'][0]['skillIds'], ['pytest-skill'])

    def test_duplicate_names_in_complete_response_are_rejected(self):
        self.payload['capabilities']['testing'].append({'id': 'webapp-testing', 'description': 'Browser tests'})
        with self.assertRaises(ValueError):
            self.run_selection([self.answer, self.answer])

    def test_candidate_limit_checked_before_network(self):
        self.payload['capabilities']['testing'] = [{'id': f'skill-{i}', 'description': 'test'} for i in range(401)]
        with patch.object(selector.urllib.request, 'build_opener') as opener, self.assertRaises(ValueError):
            selector.select(self.payload, 'test-key')
        opener.assert_not_called()

    def test_missing_key_falls_back_without_network(self):
        with patch.dict(selector.os.environ, {}, clear=True), patch.object(selector.sys, 'argv', ['select.py']), patch('sys.stdout', new_callable=io.StringIO) as output, patch.object(selector.urllib.request, 'build_opener') as opener:
            self.assertEqual(selector.main(), 2)
            self.assertEqual(json.loads(output.getvalue())['reason'], 'missing_api_key')
            opener.assert_not_called()

    def test_http_error_falls_back_without_secret(self):
        with patch.dict(selector.os.environ, {'OPENAI_API_KEY': 'private-test-key'}, clear=True), patch.object(selector.sys, 'argv', ['select.py']), patch('sys.stdin', io.StringIO(json.dumps(self.payload))), patch('sys.stdout', new_callable=io.StringIO) as output, patch.object(selector.urllib.request, 'build_opener', side_effect=OSError('private-test-key')):
            self.assertEqual(selector.main(), 2)
            self.assertNotIn('private-test-key', output.getvalue())

    def test_http_status_is_reported_without_body(self):
        error = selector.urllib.error.HTTPError('https://api.openai.com/v1/decisions', 429, 'private-test-key', {}, None)
        with patch.dict(selector.os.environ, {'OPENAI_API_KEY': 'private-test-key'}, clear=True), patch.object(selector.sys, 'argv', ['select.py']), patch('sys.stdin', io.StringIO(json.dumps(self.payload))), patch('sys.stdout', new_callable=io.StringIO) as output, patch.object(selector.urllib.request, 'build_opener', side_effect=error):
            self.assertEqual(selector.main(), 2)
            self.assertEqual(json.loads(output.getvalue()), {'fallback': 'luna-low', 'reason': 'http_error', 'status': 429})


if __name__ == '__main__':
    unittest.main()
