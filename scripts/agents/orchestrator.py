#!/usr/bin/env python3
"""
agents/orchestrator.py — Central scheduler for multi-agent investigation workflow (v3.2).

Manages agent lifecycle and coordinates execution rounds.
Agents communicate via the filesystem: case_dir/agent_logs/{agent}/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from base import BaseAgent
from core.utils import get_logger


class Orchestrator:
    """Central scheduler for multi-agent investigation workflow."""

    def __init__(self, case_dir: Path, mode: str = "manual"):
        self.case_dir = Path(case_dir)
        self.mode = mode  # "manual" or "auto"
        self.logger = get_logger("orchestrator")
        self.agents: dict[str, BaseAgent] = {}
        self.round_count = 0
        self.max_rounds = 20  # safety limit

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agents(self):
        """Instantiate all 4 agents."""
        from zhu_xiansheng import ZhuXiansheng
        from dududu import Dududu
        from huangmao import Huangmao
        from laozhoumo import LaoZhoumo

        self.agents = {
            "zhu_xiansheng": ZhuXiansheng(self.case_dir),
            "dududu": Dududu(self.case_dir),
            "huangmao": Huangmao(self.case_dir),
            "laozhoumo": LaoZhoumo(self.case_dir),
        }
        self.logger.info("Registered %d agents", len(self.agents))

    # ------------------------------------------------------------------
    # Round execution
    # ------------------------------------------------------------------

    def run_round(self) -> dict:
        """Execute one complete round."""
        self.round_count += 1
        self.logger.info("=== Round %d ===", self.round_count)

        # Step 1: ZhuXiansheng executes pending tasks
        zhu = self.agents["zhu_xiansheng"]
        zhu_result = zhu.run()

        # Step 2: Huangmao roams data (independent)
        mao = self.agents["huangmao"]
        mao_result = mao.run()

        # Step 3: Dududu analyzes
        dudu = self.agents["dududu"]
        dudu_result = dudu.run()

        # Step 4: LaoZhoumo coordinates
        lao = self.agents["laozhoumo"]
        lao_result = lao.run(context={"round": self.round_count})

        return {
            "round": self.round_count,
            "zhu": zhu_result,
            "mao": mao_result,
            "dudu": dudu_result,
            "lao": lao_result,
        }

    # ------------------------------------------------------------------
    # High-level runners
    # ------------------------------------------------------------------

    def run_until_human_decision(self) -> dict:
        """Run rounds until CRITICAL detected, phase complete, or max rounds."""
        lao = self.agents.get("laozhoumo")
        while self.round_count < self.max_rounds:
            result = self.run_round()
            if lao and lao.detect_critical():
                self.logger.warning("CRITICAL detected after round %d", self.round_count)
                break
            if self._is_phase_complete(result):
                self.logger.info("Phase complete after round %d", self.round_count)
                break
        return {"status": "paused", "round": self.round_count, "last_result": result}

    def run_full_investigation(self) -> dict:
        """Run complete investigation."""
        lao = self.agents.get("laozhoumo")
        if self.mode == "manual":
            result = self.run_until_human_decision()
            self.logger.info("Manual mode: paused after round %d for human decision", self.round_count)
            return result

        # auto mode
        while self.round_count < self.max_rounds:
            result = self.run_round()
            if lao and lao.detect_critical():
                self.logger.warning("CRITICAL detected in auto mode after round %d", self.round_count)
                break
            if self._is_phase_complete(result):
                self.logger.info("Investigation complete after round %d", self.round_count)
                break
        return {"status": "complete", "round": self.round_count, "last_result": result}

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        """Remove temporary files and pause flags."""
        removed = 0
        for agent_name, agent in self.agents.items():
            log_dir = agent.log_dir
            if not log_dir.is_dir():
                continue
            for path in log_dir.glob("intermediate_*.json"):
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
            # Remove pause flags if any
            pause_flag = log_dir / ".paused"
            if pause_flag.exists():
                try:
                    pause_flag.unlink()
                    removed += 1
                except OSError:
                    pass
        self.logger.info("Cleanup finished: removed %d temporary files/flags", removed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_phase_complete(self, result: dict) -> bool:
        """Check if the current phase is archived (all recommendations executed)."""
        lao_result = result.get("lao", {})
        phase = lao_result.get("phase", "")
        if phase == "archived":
            return True
        # Also check STATE.md directly
        state_file = self.case_dir / ".case" / "STATE.md"
        if state_file.exists():
            try:
                content = state_file.read_text(encoding="utf-8")
                if "archived" in content.lower() and "current phase" in content.lower():
                    return True
            except Exception:
                pass
        return False
