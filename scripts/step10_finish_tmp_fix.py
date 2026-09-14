from pathlib import Path
import runpy

path = Path("scripts/step10_finish_tmp.py")
text = path.read_text(encoding="utf-8")
needle = 'changed.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\\n", encoding="utf-8")'
replacement = 'changed.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\\\\n", encoding="utf-8")'
assert needle in text
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
runpy.run_path(str(path), run_name="__main__")
