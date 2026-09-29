#!/usr/bin/env python3
"""
ClipMine CLI – quick local testing without the API server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from backend.config import get_settings
from backend.core.pipeline import process_video
from backend.core.captions import list_styles
from backend.models.database import init_db, list_jobs, get_job


def main():
    parser = argparse.ArgumentParser(
        description="ClipMine – Privacy-first AI video clipper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py process video.mp4
  python cli.py process https://youtube.com/watch?v=... --max-clips 6 --style karaoke
  python cli.py styles
  python cli.py history
  python cli.py job <job_id>
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # process
    p_proc = sub.add_parser("process", help="Process a local file or URL")
    p_proc.add_argument("source", help="Local video path or URL")
    p_proc.add_argument("--max-clips", type=int, default=8, help="Max clips to generate")
    p_proc.add_argument(
        "--style",
        default="viral",
        choices=[s["id"] for s in list_styles()],
        help="Caption style",
    )

    # styles
    sub.add_parser("styles", help="List available caption styles")

    # history
    p_hist = sub.add_parser("history", help="Show recent jobs")
    p_hist.add_argument("--limit", type=int, default=20)

    # job detail
    p_job = sub.add_parser("job", help="Show details of a specific job")
    p_job.add_argument("job_id")

    args = parser.parse_args()
    init_db()

    if args.command == "styles":
        print("\nAvailable caption styles:")
        for s in list_styles():
            print(f"  • {s['id']:12} → {s['name']}")
        print()
        return

    if args.command == "history":
        jobs = list_jobs(limit=args.limit)
        if not jobs:
            print("No jobs yet.")
            return
        print(f"\n{'ID':10} {'Status':10} {'Clips':6} {'Style':10} {'Created'}")
        print("-" * 60)
        for j in jobs:
            print(
                f"{j['id']:10} {j['status']:10} {j['clips_rendered']:<6} "
                f"{j['caption_style']:10} {j['created_at'][:19]}"
            )
        print()
        return

    if args.command == "job":
        job = get_job(args.job_id)
        if not job:
            print(f"Job {args.job_id} not found.")
            sys.exit(1)
        print(json.dumps(job, indent=2))
        return

    if args.command == "process":
        source = args.source
        is_url = source.startswith("http://") or source.startswith("https://")

        if not is_url and not Path(source).exists():
            print(f"File not found: {source}")
            sys.exit(1)

        print(f"\n▶ Processing: {source}")
        print(f"  Max clips : {args.max_clips}")
        print(f"  Style     : {args.style}\n")

        result = asyncio.run(
            process_video(
                source=source,
                is_url=is_url,
                max_clips=args.max_clips,
                caption_style=args.style,
            )
        )

        print(f"\n✓ Done! Job ID: {result['job_id']}")
        print(f"  Candidates found : {result['candidates_found']}")
        print(f"  Clips rendered   : {result['clips_rendered']}\n")

        for c in result.get("clips", []):
            print(f"  [{c['score']:3}] {c['title']}")
            print(f"       {c['path']}")
            print(f"       {c['hook']}\n")


if __name__ == "__main__":
    main()
