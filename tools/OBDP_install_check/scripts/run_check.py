#!/usr/bin/env python3
"""
OBDP Install Check - 검증 실행 스크립트
설치 컴포넌트별 검증을 수행하고, 실행 내역을 로그에 남기며 결과 JSON을 출력합니다.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML 필요: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# 스크립트 기준 경로
SCRIPT_DIR = Path(__file__).resolve().parent
TOOL_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = TOOL_ROOT / "config" / "install_components.yaml"
DEFAULT_LOGS_DIR = TOOL_ROOT / "logs"
DEFAULT_RESULTS_DIR = TOOL_ROOT / "results"


def expand_path(path: str) -> Path:
    if path.startswith("~"):
        return Path(path).expanduser().resolve()
    return Path(path).resolve()


def setup_logging(log_dir: Path, run_id: str) -> logging.Logger:
    """실행별 로그 파일 생성 및 로거 설정."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run_{run_id}.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger("obdp_install_check")
    logger.info("Log file: %s", log_file)
    return logger


def load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_cmd(cmd: str, shell: bool = False, timeout: int = 15) -> tuple[int, str, str]:
    """명령 실행, (returncode, stdout, stderr) 반환."""
    try:
        if shell:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                executable="/bin/bash" if os.name != "nt" else None,
            )
        else:
            proc = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


# systemctl status 출력에서 정상 동작 판단
# active (running): 일반 서비스. active (exited): postgresql 같은 메타/원샷 유닛
SYSTEMD_ACTIVE_OK = ("Active: active (running)", "Active: active (exited)")


def check_systemd(unit: str, logger: logging.Logger, status_max_chars: int = 2000) -> tuple[bool, str]:
    """systemctl status 출력으로 정상 동작 여부 판단. detail에 status 전체 포함."""
    code, out, err = run_cmd(f"systemctl status {unit} --no-pager -l")
    combined = (out or "") + "\n" + (err or "")
    detail = combined.strip() or "no output"
    if len(detail) > status_max_chars:
        detail = detail[:status_max_chars] + "\n... (truncated)"
    out_str = out or ""
    if any(ok in out_str for ok in SYSTEMD_ACTIVE_OK):
        return True, detail
    return False, detail


def check_command(
    cmd: str,
    expect_stdout: str | None,
    expect_stdout_contains: str | None,
    shell: bool,
    description: str,
    logger: logging.Logger,
) -> tuple[bool, str]:
    logger.debug("Run: %s", cmd)
    if shell:
        cmd = os.path.expanduser(cmd)
    code, out, err = run_cmd(cmd, shell=shell)
    combined = (out + "\n" + err).strip()
    if code != 0:
        return False, combined or f"exit code {code}"
    if expect_stdout and expect_stdout not in out:
        return False, f"Expected stdout to contain: {expect_stdout!r}; got: {out!r}"
    if expect_stdout_contains and expect_stdout_contains not in out and expect_stdout_contains not in err:
        return False, f"Expected output to contain: {expect_stdout_contains!r}; got: {combined!r}"
    return True, combined or "OK"


def check_path(path: str, expand_user: bool, logger: logging.Logger) -> tuple[bool, str]:
    p = Path(path)
    if expand_user:
        p = p.expanduser().resolve()
    else:
        p = p.resolve()
    exists = p.exists()
    return exists, str(p) if exists else f"Not found: {p}"


def check_path_any(paths: list[str], logger: logging.Logger) -> tuple[bool, str]:
    """여러 경로 중 하나라도 존재하면 통과."""
    for path in paths:
        p = Path(path).resolve()
        if p.exists():
            return True, str(p)
    return False, f"Not found: {', '.join(paths)}"


def check_journalctl(unit: str, lines: int, logger: logging.Logger, detail_max_chars: int = 3000) -> tuple[bool, str]:
    """journalctl 최근 로그를 가져와 detail에 포함. 정상 수집 시 통과."""
    cmd = f"journalctl -u {unit} -n {lines} --no-pager"
    logger.debug("Run: %s", cmd)
    code, out, err = run_cmd(cmd)
    combined = (out or "").strip() + "\n" + (err or "").strip()
    detail = combined.strip() or "no output"
    if len(detail) > detail_max_chars:
        detail = detail[:detail_max_chars] + "\n... (truncated)"
    return code == 0, detail


def run_checks(config: dict, logger: logging.Logger) -> dict:
    """설정에 따라 모든 검증 실행, 결과 딕셔너리 반환."""
    run_start = datetime.utcnow().isoformat() + "Z"
    hostname = run_cmd("hostname")[1] or "unknown"
    results = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "run_start": run_start,
        "hostname": hostname,
        "installer_id": config.get("installer_id", "unknown"),
        "installer_name": config.get("installer_name", ""),
        "components": [],
    }
    components = config.get("components", [])

    for comp in sorted(components, key=lambda c: c.get("order", 99)):
        comp_id = comp.get("id", "?")
        comp_name = comp.get("name", comp_id)
        logger.info("Checking component: %s (%s)", comp_name, comp_id)
        comp_result = {
            "id": comp_id,
            "name": comp_name,
            "order": comp.get("order"),
            "checks": [],
            "passed": True,
        }
        for ch in comp.get("checks", []):
            ch_type = ch.get("type")
            desc = ch.get("description", ch_type)
            passed = False
            detail = ""

            if ch_type == "systemd":
                unit = ch.get("unit")
                if unit:
                    passed, detail = check_systemd(unit, logger)
            elif ch_type == "command":
                passed, detail = check_command(
                    ch.get("cmd", ""),
                    ch.get("expect_stdout"),
                    ch.get("expect_stdout_contains"),
                    ch.get("shell", False),
                    desc,
                    logger,
                )
            elif ch_type == "path":
                path = ch.get("path", "")
                passed, detail = check_path(path, ch.get("expand_user", False), logger)
            elif ch_type == "path_any":
                passed, detail = check_path_any(ch.get("paths", []), logger)
            elif ch_type == "journalctl":
                unit = ch.get("unit", "")
                n_lines = ch.get("lines", 30)
                if unit:
                    passed, detail = check_journalctl(unit, n_lines, logger)
                else:
                    passed, detail = False, "journalctl: unit not specified"

            comp_result["checks"].append({
                "type": ch_type,
                "description": desc,
                "passed": passed,
                "detail": detail[:1000],
            })
            if not passed:
                comp_result["passed"] = False
            logger.info("  %s: %s - %s", desc, "PASS" if passed else "FAIL", detail[:200])

        results["components"].append(comp_result)

    passed_count = sum(1 for c in results["components"] if c["passed"])
    results["summary"] = {
        "total": len(results["components"]),
        "passed": passed_count,
        "failed": len(results["components"]) - passed_count,
    }
    logger.info("Summary: %d passed, %d failed out of %d components",
                results["summary"]["passed"], results["summary"]["failed"], results["summary"]["total"])
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="OBDP Install Check - 설치 결과 검증")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="install_components.yaml 경로")
    parser.add_argument("--logs-dir", default=str(DEFAULT_LOGS_DIR), help="로그 디렉터리")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR), help="결과 JSON 저장 디렉터리")
    parser.add_argument("--no-report", action="store_true", help="결과 JSON만 저장, 보고서 생성 생략")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(args.logs_dir)
    results_dir = Path(args.results_dir)
    logger = setup_logging(log_dir, run_id)

    logger.info("Config: %s", config_path)
    config = load_config(config_path)
    results = run_checks(config, logger)

    results_dir.mkdir(parents=True, exist_ok=True)
    result_file = results_dir / f"result_{run_id}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("Result JSON: %s", result_file)

    if not args.no_report:
        report_script = SCRIPT_DIR / "report_generator.py"
        if report_script.exists():
            subprocess.run(
                [sys.executable, str(report_script), "--result", str(result_file)],
                cwd=TOOL_ROOT,
            )

    return 0 if results["summary"]["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
