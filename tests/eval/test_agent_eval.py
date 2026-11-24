"""Regression evaluation of the Bacen Fintech Advisor against the golden dataset.

Run with ``make eval`` (requires GCP credentials) or ADK CLI:
``adk eval bacen_advisor tests/eval/data/bacen_golden.evalset.json
--config_file_path tests/eval/data/test_config.json``.
"""

from pathlib import Path

import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator

DATA = Path(__file__).parent / "data"


@pytest.mark.eval
async def test_golden_dataset():
    await AgentEvaluator.evaluate(
        agent_module="bacen_advisor",
        eval_dataset_file_path_or_dir=str(DATA / "bacen_golden.evalset.json"),
        num_runs=1,
    )
