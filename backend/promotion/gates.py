from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from urllib.error import URLError
from urllib.request import urlopen


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str


class PromotionGates:
    def __init__(
        self,
        api_base_url: str,
        require_smoke: bool = True,
        require_policy_clean: bool = False,
        budget_limit_usd: float | None = None,
        current_spend_usd: float | None = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.require_smoke = require_smoke
        self.require_policy_clean = require_policy_clean
        self.budget_limit_usd = budget_limit_usd
        self.current_spend_usd = current_spend_usd

    def health_check(self) -> GateResult:
        try:
            with urlopen(f"{self.api_base_url}/health", timeout=10) as response:
                status = response.getcode()
            if status == 200:
                return GateResult("health_check", True, "Health endpoint returned 200")
            return GateResult("health_check", False, f"Health endpoint returned {status}")
        except URLError as exc:
            return GateResult("health_check", False, f"Health endpoint failed: {exc}")

    def smoke_check(self) -> GateResult:
        if not self.require_smoke:
            return GateResult("smoke_check", True, "Smoke gate disabled by configuration")

        env = os.environ.copy()
        env.setdefault("API_BASE_URL", self.api_base_url)
        try:
            result = subprocess.run(
                [sys.executable, "test_smoke.py"],
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )
        except Exception as exc:
            return GateResult("smoke_check", False, f"Failed to execute smoke test: {exc}")

        if result.returncode == 0:
            return GateResult("smoke_check", True, "Smoke test passed")

        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or "Smoke test failed"
        if len(detail) > 500:
            detail = detail[:500] + "..."
        return GateResult("smoke_check", False, detail)

    def policy_compliance(self) -> GateResult:
        if not self.require_policy_clean:
            return GateResult("policy_compliance", True, "Policy compliance gate disabled")

        # Placeholder for future persistent policy_violation table query.
        return GateResult(
            "policy_compliance",
            True,
            "Policy compliance required but no persistent violations source configured yet",
        )

    def budget_check(self) -> GateResult:
        if self.budget_limit_usd is None or self.current_spend_usd is None:
            return GateResult("budget_check", True, "Budget gate skipped (no budget/spend values provided)")

        if self.current_spend_usd <= self.budget_limit_usd:
            return GateResult(
                "budget_check",
                True,
                f"Current spend ${self.current_spend_usd:.2f} is within budget ${self.budget_limit_usd:.2f}",
            )

        return GateResult(
            "budget_check",
            False,
            f"Current spend ${self.current_spend_usd:.2f} exceeds budget ${self.budget_limit_usd:.2f}",
        )

    def run(self) -> tuple[bool, list[GateResult]]:
        checks = [
            self.health_check(),
            self.smoke_check(),
            self.policy_compliance(),
            self.budget_check(),
        ]
        passed = all(item.passed for item in checks)
        return passed, checks


def _float_or_none(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run promotion gates before deployment")
    parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--require-smoke", action="store_true", default=False)
    parser.add_argument("--require-policy-clean", action="store_true", default=False)
    parser.add_argument("--budget-limit-usd", default=os.getenv("BUDGET_LIMIT_USD"))
    parser.add_argument("--current-spend-usd", default=os.getenv("CURRENT_MONTHLY_SPEND_USD"))
    args = parser.parse_args()

    gates = PromotionGates(
        api_base_url=args.api_base_url,
        require_smoke=args.require_smoke,
        require_policy_clean=args.require_policy_clean,
        budget_limit_usd=_float_or_none(args.budget_limit_usd),
        current_spend_usd=_float_or_none(args.current_spend_usd),
    )
    passed, checks = gates.run()

    payload = {
        "passed": passed,
        "checks": [asdict(check) for check in checks],
    }
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
