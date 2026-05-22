"""Unit tests for the generator-prompt injector (cheatsheet prepend)."""

from __future__ import annotations

from apex_bench.dc_rs.injector import augment_user_prompt


def test_augment_prepends_block_and_preserves_prompt() -> None:
    out = augment_user_prompt("the task prompt body", cheatsheet="LINE A\nLINE B")
    # The wrapper text mentions a senior partner reviewing earlier work.
    assert "senior partner" in out.lower()
    # The cheatsheet body is present.
    assert "LINE A" in out
    assert "LINE B" in out
    # The task prompt body is preserved verbatim and comes AFTER the wrapper.
    assert out.endswith("the task prompt body")
    assert out.index("the task prompt body") > out.index("LINE A")


def test_augment_empty_cheatsheet_returns_prompt_unchanged() -> None:
    assert augment_user_prompt("the task prompt body", cheatsheet="") == "the task prompt body"
    assert augment_user_prompt("the task prompt body", cheatsheet="   \n") == "the task prompt body"


def test_augment_wrapper_is_domain_neutral() -> None:
    """The wrapper must not mention any specific professional branch."""
    out = augment_user_prompt("task", cheatsheet="x")
    lowered = out.lower()
    # The wrapper itself (everything before the task body) should not
    # mention domain-specific occupations.
    wrapper, _, _ = lowered.partition("\n\ntask")
    for forbidden in ("lawyer", "doctor", "consultant", "analyst", "engineer"):
        assert forbidden not in wrapper, (
            f"wrapper leaks domain-specific term '{forbidden}': {wrapper!r}"
        )
