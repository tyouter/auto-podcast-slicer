import json
from pathlib import Path

report = json.loads(Path('output/experiments/full_pipeline_validation_report.json').read_text(encoding='utf-8'))
content = report['content_validation']

critical_issues = [i for i in content['issues'] if i['severity'] == 'critical']
print(f"=== CRITICAL CONTENT ISSUES ({len(critical_issues)}) ===")
types = {}
for i in critical_issues:
    t = i['issue_type']
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")

print()
for i in critical_issues[:15]:
    print(f"  #{i['entry_index']}: [{i['issue_type']}] {i['description']}")

print()
warning_issues = [i for i in content['issues'] if i['severity'] == 'warning']
types = {}
for i in warning_issues:
    t = i['issue_type']
    types[t] = types.get(t, 0) + 1
print(f"=== WARNING CONTENT ISSUES ({len(warning_issues)}) ===")
for t, c in sorted(types.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")
