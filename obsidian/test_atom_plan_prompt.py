from scripts.atomize import REQUIRED_ATOM_FIELDS, assemble_prompt


def test_prompt_declares_the_plan_contract_used_by_validator_and_writer():
    prompt = assemble_prompt({"source_file": "test.docx", "sections": []}, [], "", "", "")
    assert all(field in prompt for field in REQUIRED_ATOM_FIELDS)
    assert 'exactly one note_type="moc"' in prompt
    assert 'Return {"notes": [...]}' in prompt
    assert "produce the plan only" in prompt
