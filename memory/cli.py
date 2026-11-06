"""給 Pi bridge 呼叫的 CLI：capture / retrieve / inject / recall / forget。"""
from __future__ import annotations
import argparse
import json
import sys

from .core import capture, retrieve, build_injection, make_observation, forget


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m memory.cli")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture")
    c.add_argument("--summary", required=True)
    c.add_argument("--session", default="cli")
    c.add_argument("--tags", default="")

    r = sub.add_parser("retrieve")
    r.add_argument("--query", required=True)
    r.add_argument("--k", type=int, default=8)

    i = sub.add_parser("inject")
    i.add_argument("--query", required=True)
    i.add_argument("--budget", type=int, default=2000)

    # /recall（人類可讀地列出相關記憶）
    rc = sub.add_parser("recall")
    rc.add_argument("--query", required=True)
    rc.add_argument("--k", type=int, default=8)

    # /forget（依 id 或 query 子字串刪除記憶）
    fg = sub.add_parser("forget")
    fg.add_argument("--id", default=None)
    fg.add_argument("--query", default=None)

    args = p.parse_args(argv)
    if args.cmd == "capture":
        tags = [t for t in args.tags.split(",") if t]
        obs = make_observation(args.summary, session_id=args.session, tags=tags)
        capture(obs)
        print(f"Remembered: {obs['summary']}")  # 已遮罩，secrets 不外露
    elif args.cmd == "retrieve":
        print(json.dumps(retrieve(args.query, args.k), ensure_ascii=False))
    elif args.cmd == "inject":
        sys.stdout.write(build_injection(args.query, args.budget))
    elif args.cmd == "recall":
        hits = retrieve(args.query, args.k)
        if not hits:
            print("(no relevant memory)")
        for h in hits:
            print(f"- [{h['id'][:8]}] {h['summary']}")
    elif args.cmd == "forget":
        if not args.id and not args.query:
            p.error("forget needs --id or --query")
        n = forget(obs_id=args.id, query=args.query)
        print(f"Forgot {n} memory item(s).")


if __name__ == "__main__":
    main()
