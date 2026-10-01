# -*- coding: utf-8 -*-
"""编排店透视市场分析刷新：发现 xlsx、分析 JSON、导入并校验批次。

默认只执行分析和导入预览；只有传入 --apply 才会备份数据库并写入。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = Path(r"E:\skill-dianshang\月复盘SKILL\analyze_socks.py")
DEFAULT_FILES_DIR = os.environ.get("TMALL_MARKET_FILES_DIR", r"C:\Users\Administrator\Downloads")
DEFAULT_JSON = os.environ.get(
    "TMALL_MARKET_ANALYSIS_JSON",
    str(ANALYZER.with_name("analysis_result.json")),
)
DEFAULT_DB = os.environ.get("TMALL_DB_PATH", str(ROOT / "data" / "dashboard.db"))


def run(command: list[str]) -> None:
    print("$ " + " ".join(str(part) for part in command))
    subprocess.run(command, check=True, cwd=ROOT)


def read_metadata(json_path: Path) -> dict:
    with json_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    required = ("analysis_date", "period_start", "period_end")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise SystemExit(f"分析结果缺少元数据: {', '.join(missing)}")
    return data


def validate_batch(db_path: Path, metadata: dict) -> dict:
    source = "店透视市场排行"
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, period_start, period_end FROM market_analysis_runs "
            "WHERE analysis_date=? AND source=?",
            (metadata["analysis_date"], source),
        ).fetchone()
        if row is None:
            raise RuntimeError("找不到刚导入的市场分析批次")
        run_id, period_start, period_end = row
        if (period_start, period_end) != (metadata["period_start"], metadata["period_end"]):
            raise RuntimeError(
                f"批次周期不一致: 数据库 {period_start}~{period_end}, "
                f"JSON {metadata['period_start']}~{metadata['period_end']}"
            )
        counts = {}
        for table in (
            "market_category_stats",
            "market_products",
            "market_keywords",
            "market_overlap_shops",
        ):
            counts[table] = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        return {"run_id": run_id, "counts": counts}
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="刷新店透视市场排行批次")
    parser.add_argument("--files-dir", default=DEFAULT_FILES_DIR)
    parser.add_argument("--window", help="指定窗口，如 20260817~20260913；默认最新窗口")
    parser.add_argument("--json", dest="json_path", default=DEFAULT_JSON)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--python", default=sys.executable, help="分析脚本使用的 Python 解释器")
    parser.add_argument("--analyzer", default=str(ANALYZER))
    parser.add_argument("--apply", action="store_true", help="备份并写入数据库；默认 dry-run")
    parser.add_argument("--backup-destination", help="--apply 时使用的 SQLite 备份路径")
    args = parser.parse_args(argv)

    json_path = Path(args.json_path).resolve()
    db_path = Path(args.db).resolve()
    analyzer = Path(args.analyzer).resolve()
    if not analyzer.is_file():
        raise SystemExit(f"分析脚本不存在: {analyzer}")
    if not db_path.is_file():
        raise SystemExit(f"数据库不存在: {db_path}")

    analyze_command = [
        args.python,
        str(analyzer),
        "--files-dir",
        args.files_dir,
        "--output",
        str(json_path),
        "--quiet",
    ]
    if args.window:
        analyze_command.extend(["--window", args.window])
    run(analyze_command)
    metadata = read_metadata(json_path)

    import_command = [
        args.python,
        "-m",
        "scripts.import_market_ranking",
        "--db",
        str(db_path),
        "--json",
        str(json_path),
    ]
    if args.apply:
        if not args.backup_destination:
            parser.error("--apply 需要同时提供 --backup-destination")
        import_command.extend(["--apply", "--backup-destination", args.backup_destination])
    run(import_command)

    report = {
        "mode": "apply" if args.apply else "dry-run",
        "json": str(json_path),
        "database": str(db_path),
        "period_start": metadata["period_start"],
        "period_end": metadata["period_end"],
        "analysis_date": metadata["analysis_date"],
    }
    if args.apply:
        report["batch"] = validate_batch(db_path, metadata)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({**report, "message": "未写入数据库；加 --apply 执行导入"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
