from pathlib import Path

path = Path("src/lidarperf/comparison.py")
text = path.read_text(encoding="utf-8")
start = text.index("def _numeric_metrics(")
end = text.index("def _scalar_changes(", start)
replacement = '''def _numeric_metrics(root: Path) -> dict[str, float]:
    aggregate_path = root / "aggregate.json"
    if aggregate_path.is_file():
        aggregate = _read_json(aggregate_path)
        metrics = aggregate.get("metrics", {})
        metric_values = metrics.get("trial_metrics", metrics)
        return {
            key: scalar
            for key, value in metric_values.items()
            if (scalar := _summary_value(value)) is not None
        }

    metrics = _read_json(root / "trials" / "0001" / "metrics.json").get("values", {})
    return {
        key: scalar
        for key, value in metrics.items()
        if (scalar := _summary_value(value)) is not None
    }


def _numeric_resources(root: Path) -> dict[str, float]:
    aggregate_path = root / "aggregate.json"
    if aggregate_path.is_file():
        aggregate = _read_json(aggregate_path)
        resources = aggregate.get("metrics", {}).get("resources")
        if isinstance(resources, dict):
            return {
                key: scalar
                for key, value in resources.items()
                if (scalar := _summary_value(value)) is not None
            }

    resources = _read_json(root / "trials" / "0001" / "resources.json").get("values", {})
    return {
        key: scalar
        for key, value in resources.items()
        if (scalar := _summary_value(value)) is not None
    }


'''
text = text[:start] + replacement + text[end:]
old = '''            reason="unexplained software-environment differences forbid strict comparison",
        ),
'''
new = '''            reason=(
                "software environments must match unless dependencies are the declared subject"
            ),
            predicate=(
                baseline.environment.software == candidate.environment.software
                or "dependencies" in declared_differences
            ),
        ),
'''
if old not in text:
    raise SystemExit("software-environment check anchor not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
