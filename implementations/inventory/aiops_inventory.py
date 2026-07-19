#!/usr/bin/env python3
"""AIS-0009/AIS-0010 reference implementation."""
from __future__ import annotations
import argparse, json, os, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

TOOLS = ["claude","codex","opencode","kimi","gemini","aider","ollama"]
MCP_PATHS = [Path.home()/".config", Path.home()/".claude", Path.home()/".codex", Path.home()/".kimi", Path.cwd()]


def run(argv:list[str])->dict:
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=5,check=False)
        return {"argv":argv,"returncode":p.returncode,"stdout":p.stdout[:4000],"stderr":p.stderr[:2000]}
    except Exception as e:
        return {"argv":argv,"error":str(e)}


def version(name:str)->dict:
    path=shutil.which(name)
    result={"name":name,"installed":bool(path),"path":path}
    if path:
        probe=run([name,"--version"])
        result["version_probe"]=probe
    return result


def discover_mcp()->list[dict]:
    hits=[]
    names={"mcp.json","mcp.yaml","mcp.yml","claude_desktop_config.json","settings.json","config.toml"}
    seen=set()
    for root in MCP_PATHS:
        if not root.exists(): continue
        for p in root.rglob("*"):
            if len(p.parts)-len(root.parts)>4: continue
            if p.is_file() and (p.name in names or "mcp" in p.name.lower()):
                s=str(p)
                if s not in seen:
                    seen.add(s); hits.append({"path":s,"size":p.stat().st_size})
    return hits


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="ai-capability-registry.json")
    args=ap.parse_args()
    report={
      "schema_version":"0.1.0",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "host":run(["hostname"]),
      "agents":[version(x) for x in TOOLS],
      "mcp":{"config_candidates":discover_mcp()},
      "environment":{"names":sorted(k for k in os.environ if any(x in k.upper() for x in ["MCP","OPENAI","ANTHROPIC","GITHUB","CODEX","CLAUDE","KIMI"]))},
      "permissions":{"uid":os.getuid(),"euid":os.geteuid(),"is_root":os.geteuid()==0},
    }
    Path(args.output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(args.output)
    return 0

if __name__=="__main__": raise SystemExit(main())
