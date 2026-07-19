#!/usr/bin/env python3
"""AIS-0012 compliance runner."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

CHECKS={
 "AIS-0003-REQ-001": lambda r: "generated_at" in r and "collectors" in r,
 "AIS-0009-REQ-001": lambda r: isinstance(r.get("mcp",{}).get("config_candidates",[]),list),
 "AIS-0010-REQ-001": lambda r: isinstance(r.get("agents",[]),list),
 "AIS-0010-REQ-002": lambda r: "permissions" in r,
}

def load(path:str)->dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--discovery")
    ap.add_argument("--registry")
    ap.add_argument("--output",default="compliance-result.json")
    args=ap.parse_args()
    merged={}
    if args.discovery: merged.update(load(args.discovery))
    if args.registry: merged.update(load(args.registry))
    results=[]
    for req,check in CHECKS.items():
        try: passed=bool(check(merged)); detail=""
        except Exception as e: passed=False; detail=str(e)
        results.append({"requirement_id":req,"passed":passed,"detail":detail})
    report={"schema_version":"0.1.0","generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"passed":sum(x["passed"] for x in results),"failed":sum(not x["passed"] for x in results)},"results":results}
    Path(args.output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(args.output)
    return 0 if report["summary"]["failed"]==0 else 1
if __name__=="__main__": raise SystemExit(main())
