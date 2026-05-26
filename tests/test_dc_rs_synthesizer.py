"""Unit tests for the synthesizer LiteLLM call.

The synthesizer must:
  - Send the rendered prompt as a SINGLE user message (no system
    message), matching Suzgun's reference (``dc_rs.py:144-161``).
  - Use the kwargs-build-then-update pattern, NOT a ``**extra`` splat
    (which raises ``TypeError`` when the profile's extras share keys
    with the explicit kwargs — a previously-fixed bug class).
  - Substitute the three placeholders into the user message.
  - Apply ``extract_cheatsheet`` (with fallback) to the response.
"""

from __future__ import annotations

import sys
import types

import pytest

from apex_bench.dc_rs.config import DCRSConfig
from apex_bench.dc_rs.synthesizer import synthesize


class _FakeMsg:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMsg(content)


class _FakeUsage:
    def __init__(self, p: int, c: int) -> None:
        self.prompt_tokens = p
        self.completion_tokens = c


class _FakeResp:
    def __init__(self, content: str, p: int, c: int) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(p, c)


def _install_fake_litellm(monkeypatch: pytest.MonkeyPatch, content: str, capture: dict) -> None:
    """Replace ``litellm.completion`` with a fake that records its kwargs."""

    def fake_completion(**kwargs):
        capture.update(kwargs)
        return _FakeResp(content, p=42, c=7)

    fake_litellm = types.SimpleNamespace(completion=fake_completion)
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)


def test_synthesizer_sends_single_user_message_no_system(monkeypatch: pytest.MonkeyPatch) -> None:
    """Suzgun's reference sends one user message with ``system=None``.
    Match that exactly."""
    capture: dict = {}
    _install_fake_litellm(
        monkeypatch,
        content="<cheatsheet>x</cheatsheet>",
        capture=capture,
    )
    cfg = DCRSConfig(enabled=True, synthesizer_model="xai/grok-4.3")
    synthesize(
        current_cheatsheet="(empty)",
        retrieved_entries_block="(empty)",
        task_prompt="task",
        task_id="task_999",
        cfg=cfg,
    )
    msgs = capture["messages"]
    assert len(msgs) == 1, f"expected exactly one message, got {len(msgs)}: {msgs}"
    assert msgs[0]["role"] == "user"


def test_synthesize_substitutes_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict = {}
    _install_fake_litellm(
        monkeypatch,
        content="<cheatsheet>the synthesized notes</cheatsheet>",
        capture=capture,
    )
    cfg = DCRSConfig(enabled=True, synthesizer_model="xai/grok-4.3")
    result = synthesize(
        current_cheatsheet="PREV-CHEAT",
        retrieved_entries_block="RETRIEVED-BLOCK",
        task_prompt="THE CURRENT TASK PROMPT",
        task_id="task_4242",
        cfg=cfg,
    )
    user_msg = capture["messages"][0]["content"]
    assert "PREV-CHEAT" in user_msg
    assert "RETRIEVED-BLOCK" in user_msg
    assert "THE CURRENT TASK PROMPT" in user_msg
    assert "task_4242" in user_msg
    assert result.cheatsheet == "the synthesized notes"
    assert result.used_fallback is False
    assert result.prompt_tokens == 42
    assert result.completion_tokens == 7


def test_synthesize_falls_back_when_wrapper_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict = {}
    _install_fake_litellm(
        monkeypatch,
        content="forgot the wrapper",
        capture=capture,
    )
    cfg = DCRSConfig(enabled=True, synthesizer_model="xai/grok-4.3")
    result = synthesize(
        current_cheatsheet="(empty)",
        retrieved_entries_block="THE RAW RETRIEVED BLOCK",
        task_prompt="task",
        task_id="task_999",
        cfg=cfg,
    )
    assert result.used_fallback is True
    assert result.cheatsheet == "THE RAW RETRIEVED BLOCK"


def test_synthesize_extra_args_override_defaults_without_kwarg_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the profile's extra args carry a `temperature` or `timeout`,
    the synthesizer must merge them via dict.update (so the profile
    wins) rather than splat them as ``**extra`` alongside the explicit
    defaults — which would raise ``TypeError: got multiple values for
    keyword argument``."""
    capture: dict = {}
    _install_fake_litellm(
        monkeypatch,
        content="<cheatsheet>x</cheatsheet>",
        capture=capture,
    )
    cfg = DCRSConfig(
        enabled=True,
        synthesizer_model="xai/grok-4.3",
        synthesizer_extra_args={
            "temperature": 0.7,
            "timeout": 600,
            "reasoning_effort": "high",
        },
        synthesizer_temperature=1.0,
        synthesizer_timeout_seconds=1800,
    )
    result = synthesize(
        current_cheatsheet="(empty)",
        retrieved_entries_block="(empty)",
        task_prompt="task",
        task_id="task_999",
        cfg=cfg,
    )
    assert capture["temperature"] == 0.7
    assert capture["timeout"] == 600
    assert capture["reasoning_effort"] == "high"
    assert result.cheatsheet == "x"


def test_synthesize_signature_has_no_grading_inputs() -> None:
    """Load-bearing fidelity: the synthesizer must accept exactly five
    keyword arguments. The added ``task_id`` is for provenance tagging
    only — not a grading signal. No ``criteria``, no ``score``, no
    ``gt_correct``, no ``expected_answer``, no ``judge_rationale``."""
    import inspect

    sig = inspect.signature(synthesize)
    assert list(sig.parameters.keys()) == [
        "current_cheatsheet",
        "retrieved_entries_block",
        "task_prompt",
        "task_id",
        "cfg",
    ]
