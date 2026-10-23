import argparse
import json

from .sources import collect_construction, collect_events, run_all
from .common import result_dict, write_json, utc_now
from .sources import REPORTS

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seoul-only", action="store_true", help="Collect only Seoul construction and cultural-event APIs")
    args = parser.parse_args()
    if args.seoul_only:
        construction, construction_rows = collect_construction()
        events, event_rows = collect_events()
        path = REPORTS / "public_data_manifest.json"
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"results": [], "processed_counts": {}, "integration_policy": {}}
        replacements = {"construction": construction, "events": events}
        retained = [x for x in current.get("results", []) if x.get("dataset") not in replacements]
        current["generated_at"] = utc_now()
        current["results"] = retained + [result_dict(construction), result_dict(events)]
        current.setdefault("processed_counts", {}).update({"construction_events": len(construction_rows), "cultural_events": len(event_rows)})
        write_json(path, current)
    else:
        run_all()
