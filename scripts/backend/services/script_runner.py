"""
Script Runner - 调用学术调查引擎脚本的服务层
"""

import asyncio
import os
import json
from pathlib import Path
from typing import List, Optional

SCRIPTS_DIR = "/Users/xiaoy/Desktop/端上台来/scripts"

# 脚本映射表
SCRIPT_MAP = {
    "text_profiler": {
        "cmd": ["python3", "analysis/text_profiler.py"],
        "cwd": SCRIPTS_DIR,
        "needs_input": True,
        "input_flag": "--input",
        "output_flag": "--output",
    },
    "paper_quality": {
        "cmd": ["python3", "analysis/paper_quality_rubric.py"],
        "cwd": SCRIPTS_DIR,
        "needs_input": True,
        "input_flag": "--profile",
    },
    "hybrid_score": {
        "cmd": ["python3", "analysis/hybrid_scorer.py"],
        "cwd": SCRIPTS_DIR,
    },
    "investigate_init": {
        "cmd": ["python3", "investigate.py", "init"],
        "cwd": SCRIPTS_DIR,
        "needs_case_dir": True,
    },
    "investigate_status": {
        "cmd": ["python3", "investigate.py", "status"],
        "cwd": SCRIPTS_DIR,
        "needs_case_dir": True,
    },
    "investigate_orchestrate": {
        "cmd": ["python3", "investigate.py", "orchestrate"],
        "cwd": SCRIPTS_DIR,
        "needs_case_dir": True,
        "args": ["--mode", "auto", "--max-rounds", "3"],
    },
    "investigate_generate": {
        "cmd": ["python3", "investigate.py", "generate"],
        "cwd": SCRIPTS_DIR,
        "needs_case_dir": True,
    },
    "citation_profiler": {
        "cmd": ["python3", "analysis/citation_profiler.py"],
        "cwd": SCRIPTS_DIR,
    },
    "stylometry": {
        "cmd": ["python3", "analysis/stylometry_profiler.py"],
        "cwd": SCRIPTS_DIR,
    },
    "journal_check": {
        "cmd": ["python3", "investigate.py", "journal-check"],
        "cwd": SCRIPTS_DIR,
        "needs_case_dir": True,
    },
}


async def run_script(
    script_key: str,
    case_dir: Optional[str] = None,
    input_path: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    timeout: int = 120,
) -> dict:
    """Run an investigation script and return result summary.

    Returns:
        {"success": bool, "stdout": str, "stderr": str, "returncode": int}
    """
    config = SCRIPT_MAP.get(script_key)
    if not config:
        return {"success": False, "stdout": "", "stderr": f"Unknown script: {script_key}", "returncode": -1}

    cmd = list(config["cmd"])
    cwd = config.get("cwd", SCRIPTS_DIR)

    # Auto-discover input files if needed but not provided
    if config.get("needs_input") and not input_path and case_dir:
        pdfs_dir = os.path.join(case_dir, "pdfs")
        if os.path.isdir(pdfs_dir):
            pdfs = [f for f in os.listdir(pdfs_dir) if f.lower().endswith(".pdf")]
            if pdfs:
                input_path = os.path.join(pdfs_dir, pdfs[0])
            else:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"案件目录 {case_dir}/pdfs/ 下没有找到PDF文件。请先上传论文PDF。",
                    "returncode": -1,
                }
        else:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"案件目录 {case_dir} 下没有 pdfs/ 文件夹。请先上传论文PDF。",
                "returncode": -1,
            }

    if config.get("needs_case_dir") and case_dir:
        cmd.extend(["--case-dir", case_dir])

    if config.get("needs_input") and input_path:
        cmd.extend([config["input_flag"], input_path])
        if config.get("output_flag") and case_dir:
            output_path = os.path.join(case_dir, "reports", f"{script_key}_output.json")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cmd.extend([config["output_flag"], output_path])

    if config.get("args"):
        cmd.extend(config["args"])

    if extra_args:
        cmd.extend(extra_args)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace")[:8000],
            "stderr": stderr.decode("utf-8", errors="replace")[:4000],
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def list_available_scripts() -> List[str]:
    """Return list of available script keys."""
    return list(SCRIPT_MAP.keys())


def get_script_info(script_key: str) -> Optional[dict]:
    """Get info about a script."""
    return SCRIPT_MAP.get(script_key)
