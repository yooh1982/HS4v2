#!/usr/bin/env python3
"""
OBDP Install Check - 보고서 생성
result_*.json 을 읽어 HTML 및 Markdown 보고서를 생성합니다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORTS_DIR = TOOL_ROOT / "reports"


def load_result(result_path: Path) -> dict:
    with open(result_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_markdown(data: dict) -> str:
    run_id = data.get("run_id", "?")
    hostname = data.get("hostname", "?")
    installer_name = data.get("installer_name", "")
    summary = data.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)

    lines = [
        "# OBDP Install Check Report",
        "",
        f"- **Run ID**: {run_id}",
        f"- **Hostname**: {hostname}",
        f"- **Installer**: {installer_name}",
        f"- **Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "## Summary",
        "",
        f"| Total | Passed | Failed |",
        f"|-------|--------|--------|",
        f"| {total} | {passed} | {failed} |",
        "",
        "## Component Results",
        "",
    ]
    for comp in data.get("components", []):
        status = "PASS" if comp.get("passed") else "FAIL"
        lines.append(f"### {comp.get('name', comp.get('id'))} — {status}")
        lines.append("")
        for ch in comp.get("checks", []):
            ch_status = "✓" if ch.get("passed") else "✗"
            lines.append(f"- {ch_status} **{ch.get('description', '')}**: {ch.get('detail', '')[:200]}")
        lines.append("")
    return "\n".join(lines)


def generate_html(data: dict) -> str:
    run_id = data.get("run_id", "?")
    hostname = data.get("hostname", "?")
    installer_name = data.get("installer_name", "")
    summary = data.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    all_passed = failed == 0

    rows = []
    for comp in data.get("components", []):
        status = "PASS" if comp.get("passed") else "FAIL"
        row_class = "pass" if comp.get("passed") else "fail"
        checks_cells = []
        for ch in comp.get("checks", []):
            ch_status = "✓" if ch.get("passed") else "✗"
            ch_class = "pass" if ch.get("passed") else "fail"
            detail = (ch.get("detail") or "").replace("<", "&lt;").replace(">", "&gt;")[:300]
            checks_cells.append(f'<span class="{ch_class}">{ch_status} {ch.get("description", "")}</span> {detail}')
        rows.append(
            f'<tr class="{row_class}"><td>{comp.get("name", comp.get("id"))}</td><td class="{row_class}">{status}</td>'
            f'<td><ul>{"".join("<li>" + c + "</li>" for c in checks_cells)}</ul></td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OBDP Install Check — {run_id}</title>
<style>
  body {{ font-family: sans-serif; margin: 1rem 2rem; background: #f5f5f5; }}
  h1 {{ color: #333; }}
  .meta {{ color: #666; margin-bottom: 1.5rem; }}
  .summary {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; }}
  .summary span {{ padding: 0.5rem 1rem; border-radius: 6px; }}
  .summary .total {{ background: #e3f2fd; }}
  .summary .passed {{ background: #e8f5e9; }}
  .summary .failed {{ background: #ffebee; }}
  table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; }}
  th {{ background: #37474f; color: white; }}
  tr.pass {{ background: #f1f8e9; }}
  tr.fail {{ background: #ffebee; }}
  .pass {{ color: #2e7d32; }}
  .fail {{ color: #c62828; }}
  ul {{ margin: 0; padding-left: 1.2rem; }}
  li {{ margin: 0.2rem 0; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>OBDP Install Check Report</h1>
<div class="meta">
  <strong>Run ID</strong>: {run_id} &nbsp;|&nbsp;
  <strong>Hostname</strong>: {hostname} &nbsp;|&nbsp;
  <strong>Installer</strong>: {installer_name} &nbsp;|&nbsp;
  <strong>Generated</strong>: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC
</div>
<div class="summary">
  <span class="total">Total: {total}</span>
  <span class="passed">Passed: {passed}</span>
  <span class="failed">Failed: {failed}</span>
</div>
<table>
<thead><tr><th>Component</th><th>Status</th><th>Checks</th></tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
</body>
</html>
"""
    return html


def main() -> int:
    parser = argparse.ArgumentParser(description="OBDP Install Check Report Generator")
    parser.add_argument("--result", required=True, help="result_YYYYMMDD_HHMMSS.json 경로")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="보고서 출력 디렉터리")
    parser.add_argument("--format", choices=["both", "html", "md"], default="both")
    args = parser.parse_args()

    result_path = Path(args.result)
    if not result_path.exists():
        print(f"Result file not found: {result_path}", file=sys.stderr)
        return 1

    data = load_result(result_path)
    run_id = data.get("run_id", "unknown")
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    if args.format in ("both", "md"):
        md_content = generate_markdown(data)
        md_path = reports_dir / f"report_{run_id}.md"
        md_path.write_text(md_content, encoding="utf-8")
        print(f"Markdown report: {md_path}")

    if args.format in ("both", "html"):
        html_content = generate_html(data)
        html_path = reports_dir / f"report_{run_id}.html"
        html_path.write_text(html_content, encoding="utf-8")
        print(f"HTML report: {html_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
