"""Tests for the test-model profile registry."""

from __future__ import annotations

import pytest

from apex_bench.test_models import (
    TestModelProfile,
    all_profiles,
    get_profile,
    profile_names,
    profiles_by_family,
)


def test_registry_has_all_expected_families() -> None:
    """Only currently-runnable families are registered.

    Claude profiles (opus-4.6, sonnet-4.6, haiku-4.5) are deferred until
    Bedrock routing lands in the vendor's LiteLLM client. See
    test_models.py `_DEFERRED_CLAUDE_PROFILES_NOTE`.
    """
    families = {p.family for p in all_profiles()}
    expected = {"gpt-5.5", "grok-4.3"}
    assert families == expected, f"unexpected families: {families ^ expected}"


def test_profile_names_are_unique() -> None:
    names = profile_names()
    assert len(names) == len(set(names)), "duplicate profile name"


def test_gpt55_profiles_cover_four_efforts() -> None:
    names = {p.name for p in all_profiles() if p.family == "gpt-5.5"}
    assert names == {
        "gpt-5.5-low",
        "gpt-5.5-medium",
        "gpt-5.5-high",
        "gpt-5.5-xhigh",
    }


def test_grok_profiles_cover_three_tiers() -> None:
    names = {p.name for p in all_profiles() if p.family == "grok-4.3"}
    assert names == {"grok-4.3-low", "grok-4.3-medium", "grok-4.3-high"}


def test_no_claude_profiles_currently_registered() -> None:
    """Claude/Bedrock is deferred until vendor Bedrock routing lands."""
    for p in all_profiles():
        assert p.provider != "anthropic-bedrock", (
            f"Claude profile {p.name!r} should be deferred — vendor has no "
            "Bedrock routing. See test_models.py _DEFERRED_CLAUDE_PROFILES_NOTE."
        )


def test_to_model_config_kwargs_shape() -> None:
    p = get_profile("gpt-5.5-high")
    kw = p.to_model_config_kwargs()
    assert kw["model_id"] == "gpt-5.5"
    assert kw["number_of_runs"] == 1  # project policy
    assert kw["model_configs"]["reasoning_effort"] == "high"
    # OpenAI reasoning models only accept the provider default temperature.
    assert kw["temperature"] == 1.0


def test_get_profile_unknown_name_helpful_error() -> None:
    with pytest.raises(KeyError, match="Unknown test-model profile"):
        get_profile("does-not-exist")


def test_get_profile_suggests_family_matches() -> None:
    with pytest.raises(KeyError, match="Did you mean"):
        get_profile("gpt-5.5-pro")  # plausible typo, family prefix matches


def test_profiles_by_family_groups_correctly() -> None:
    groups = profiles_by_family()
    assert set(groups.keys()) == {"gpt-5.5", "grok-4.3"}
    assert len(groups["gpt-5.5"]) == 4
    assert len(groups["grok-4.3"]) == 3


def test_every_profile_runs_per_task_eq_1() -> None:
    """Project policy enforcement at profile-construction time."""
    for p in all_profiles():
        kw = p.to_model_config_kwargs()
        assert kw["number_of_runs"] == 1, f"{p.name} violates RUNS_PER_TASK=1"


def test_typeof_returned_object() -> None:
    p = get_profile("grok-4.3-medium")
    assert isinstance(p, TestModelProfile)
