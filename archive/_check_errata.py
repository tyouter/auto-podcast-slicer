import json
from pathlib import Path
from pipeline.loader import load_project

ctx = load_project()
custom_errata = ctx.custom_errata

print("=== 勘误表 (wrong → right) ===")
for wrong, right in list(custom_errata.items())[:20]:
    print(f"  '{wrong}' → '{right}'")
print(f"  ... total: {len(custom_errata)} entries")
