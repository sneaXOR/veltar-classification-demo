"""Score a saved browser response; no network, no credentials."""
import json
import pathlib
from evaluate import CASES, validate

root = pathlib.Path(__file__).resolve().parent
response = json.loads((root / 'claude-free-response.json').read_text(encoding='utf-8'))
assert len(response) == 3
assert {item['case'] for item in response} == {case['id'] for case in CASES}
results = []
for case in CASES:
    item = next(item for item in response if item['case'] == case['id'])
    results.append({'case': case['id'], **validate(case, item['extraction'])})
report = {'mode': 'Claude Free browser interface', 'model_displayed': 'Sonnet 5.5 Medium',
          'date': '2026-10-08', 'api_calls': 0, 'paid_purchase': False,
          'synthetic_data': True, 'correct_fields': sum(item['correct_fields'] for item in results),
          'total_fields': 12, 'cases': results,
          'limitation': 'One combined prompt, three synthetic examples; not API integration or production reliability evidence.'}
(root / 'claude-free-score.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
