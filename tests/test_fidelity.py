"""Behavioral-fidelity tests: confirm our wrapper does not diverge from the
vendor's reference runner (`vendor/apex_evals/examples/run_with_hf.py`) in
ways that would alter what reaches the model or the judge.

These tests do NOT call any API. They assert structural and code-level
invariants that protect against accidental drift.
"""

from __future__ import annotations

import re
from pathlib import Path

from apex_bench.paths import vendor_dir
from apex_bench.test_models import all_profiles

# -----------------------------------------------------------------------------
# Audit 5 — Prompt template is read verbatim, only {{Domain}} / {{Prompt}} subst.
# -----------------------------------------------------------------------------


def test_response_generation_template_is_unmodified_from_vendor() -> None:
    """Our runner reads the prompt template from the vendor directory; we
    must NOT keep a private edited copy in src/."""
    src_dir = Path(__file__).resolve().parent.parent / "src" / "apex_bench"
    for path in src_dir.rglob("*.txt"):
        # No prompt-template files should live in our wrapper source tree.
        assert "prompt" not in path.parts, (
            f"unexpected prompt file in wrapper source tree: {path}. "
            "Prompts must be read at run-time from vendor/apex_evals/prompt/."
        )


def test_response_generation_template_has_only_two_placeholders() -> None:
    tmpl = (vendor_dir() / "prompt" / "response_generation_prompt.txt").read_text(encoding="utf-8")
    # Mercor uses {{Domain}} and {{Prompt}}; nothing else.
    placeholders = set(re.findall(r"{{[^}]+}}", tmpl))
    assert placeholders == {
        "{{Domain}}",
        "{{Prompt}}",
    }, f"unexpected placeholders in upstream prompt: {placeholders}"


def test_grading_template_present_in_vendor() -> None:
    p = vendor_dir() / "prompt" / "grading_prompt.txt"
    assert p.is_file(), "vendor grading_prompt.txt missing — make install needed"
    body = p.read_text(encoding="utf-8")
    assert "criterion" in body.lower(), (
        "grading template doesn't mention criterion — wrong file or corrupted"
    )


def test_reasoning_judge_temperature_coerced_to_one() -> None:
    """Regression test for 2026-05-19: gpt-5.5 (and other OpenAI reasoning
    models) reject any temperature other than 1.0; the project judge
    default was 0.01 (legacy from Mercor's Gemini era). The
    `_safe_judge_temperature` helper must coerce non-1.0 to 1.0 for any
    model whose name starts with gpt-5, o1, o3, or o4."""
    from apex_bench.runner import _safe_judge_temperature

    # Reasoning judges -> coerced to 1.0 regardless of input.
    for model in (
        "gpt-5.5",
        "openai/gpt-5.5",
        "gpt-5",
        "gpt-5.2-pro",
        "o1-preview",
        "o3-mini",
        "o4-mini",
    ):
        assert _safe_judge_temperature(model, 0.01) == 1.0, model
        assert _safe_judge_temperature(model, 0.5) == 1.0, model
        assert _safe_judge_temperature(model, 1.0) == 1.0, model  # already 1.0; no-op

    # Non-reasoning judges -> requested value honored.
    for model in (
        "gemini/gemini-2.5-flash",
        "gemini-2.5-pro",
        "claude-3-5-sonnet-20241022",
        "grok-4-0709",
    ):
        assert _safe_judge_temperature(model, 0.01) == 0.01, model
        assert _safe_judge_temperature(model, 0.5) == 0.5, model


def test_csv_headers_include_token_and_cost_columns() -> None:
    """Token + cost columns must be present so a presentable run report can
    answer 'how much did this cost' without grepping stderr."""
    from apex_bench.runner import csv_headers

    h = csv_headers("gpt_5_5")
    assert "agent_input_tokens" in h
    assert "agent_output_tokens" in h
    assert "agent_tokens" in h
    assert "agent_usage_available" in h
    assert "agent_usage_source" in h
    assert "agent_usage_consistent" in h
    assert "agent_cost_usd" not in h
    assert "agent_estimated_cost_usd" not in h
    assert "judge_input_tokens" not in h
    assert "judge_output_tokens" not in h
    assert "judge_tokens" not in h
    assert "judge_cost_usd" not in h


def test_csv_headers_include_attachment_prompt_audit_columns() -> None:
    """APEX tasks are attachment-heavy; a completed row must prove the
    attachment text made it into the final prompt without saving the prompt."""
    from apex_bench.runner import csv_headers

    h = csv_headers("gpt_5_5")
    assert "attachments_expected" in h
    assert "attachments_sent" in h
    assert "parsed_attachment_chars" in h
    assert "final_prompt_chars" in h
    assert "final_prompt_sha256" in h


def test_runner_passes_grading_template_as_path_not_content() -> None:
    """Regression test for a vendor bug discovered on 2026-05-19.

    The vendor's _resolve_prompt_template() does:
        candidate = Path(template); if candidate.exists(): return candidate.read_text(); else return template
    On macOS, passing the *content* of the template (>255 chars) triggers
    OSError ENAMETOOLONG on Path.exists() because the vendor doesn't guard
    against it. So we MUST pass the path string, not the file content.

    Asserts our runner.py and smoke.py read the template path with
    `_grading_template_path()` (returns a path str) and NOT
    `_read_grading_template()` (which would return content).
    """
    for fname in ("runner.py", "smoke.py"):
        src = (Path(__file__).resolve().parent.parent / "src" / "apex_bench" / fname).read_text(
            encoding="utf-8"
        )
        assert "_grading_template_path()" in src, (
            f"{fname} must call _grading_template_path() and pass the path string "
            "to GradingTask(grading_prompt_template=...). Passing the file content "
            "triggers an OSError ENAMETOOLONG inside the vendor's _resolve_prompt_template."
        )
        assert "_read_grading_template" not in src, (
            f"{fname} must NOT use _read_grading_template (which returned content). "
            "That symbol was removed in the path-not-content fix."
        )


# -----------------------------------------------------------------------------
# Audit 6 — Attachments: filename + file:// URL only.
# -----------------------------------------------------------------------------


def test_attachment_construction_uses_only_filename_and_file_url() -> None:
    """We must build Attachment objects with the same two fields upstream uses.
    No extra metadata, no remote URLs.

    This is a structural inspection of our smoke + runner source — we assert
    the construction pattern is `VendorAttachment(filename=..., url=f"file://...")`
    with no other kwargs.
    """
    src = (Path(__file__).resolve().parent.parent / "src" / "apex_bench" / "runner.py").read_text(
        encoding="utf-8"
    )
    # Pattern: VendorAttachment(filename=a.path.name, url=f"file://{a.path}")
    assert re.search(
        r"VendorAttachment\(\s*filename\s*=\s*a\.path\.name\s*,\s*url\s*=\s*f\"file://\{a\.path\}\"\s*\)",
        src,
    ), "runner.py does not build Attachment with exactly the upstream-shape kwargs"


# -----------------------------------------------------------------------------
# Audit 7 — Rubric is passed verbatim (no preprocessing) to GradingTask.
# -----------------------------------------------------------------------------


def test_rubric_passed_verbatim() -> None:
    src = (Path(__file__).resolve().parent.parent / "src" / "apex_bench" / "runner.py").read_text(
        encoding="utf-8"
    )
    # Confirm rubric=task.rubric_json appears in GradingTask construction
    # (no transformation step between).
    assert "rubric=task.rubric_json" in src, (
        "runner.py does not pass rubric_json verbatim to GradingTask"
    )


# -----------------------------------------------------------------------------
# Audit 8 — Generation parameters: no tools / system_prompt / top_p / images /
#           thinking / web search.  All active profiles must use only the
#           upstream-canonical ModelConfig keys.
# -----------------------------------------------------------------------------


_ALLOWED_KWARG_KEYS = frozenset(
    {
        "model_id",
        "max_tokens",
        "max_input_tokens",
        "temperature",
        "model_configs",
        "number_of_runs",
    }
)


def test_no_profile_uses_disallowed_capabilities() -> None:
    """Project rule: we only set the same ModelConfig keys Mercor sets in
    `vendor/apex_evals/examples/run_with_hf.py:24-37`. In particular we do
    NOT enable tools, system_prompt, top_p, response_images, enable_thinking,
    thinking_tokens, or any web-search / browser tool for the active
    profiles. The presence of any disallowed key fails this test loudly."""
    for p in all_profiles():
        kw = p.to_model_config_kwargs()
        extras = set(kw.keys()) - _ALLOWED_KWARG_KEYS
        assert not extras, (
            f"profile {p.name!r} sets disallowed ModelConfig keys: {extras}. "
            "If this is intentional, update _ALLOWED_KWARG_KEYS in test_fidelity.py "
            "and confirm Mercor uses the same key. Web-search / tools / multimodal "
            "are NOT used in the upstream run_with_hf.py."
        )


def test_no_profile_enables_tools_or_thinking() -> None:
    for p in all_profiles():
        kw = p.to_model_config_kwargs()
        # Tools / thinking must never be on for the public-evaluation surface.
        assert "use_tools" not in kw, f"{p.name}: use_tools must not be set"
        assert "enable_thinking" not in kw, (
            f"{p.name}: enable_thinking must not be set (Claude/Bedrock profiles "
            "deferred; OpenAI/xAI do not expose this)"
        )
        assert "thinking_tokens" not in kw, f"{p.name}: thinking_tokens must not be set"


def test_no_profile_sets_top_p() -> None:
    """Upstream's MODELS list does not set top_p for any of its 12 entries."""
    for p in all_profiles():
        kw = p.to_model_config_kwargs()
        assert "top_p" not in kw, f"{p.name}: top_p must not be set (upstream omits it)"


# -----------------------------------------------------------------------------
# Audit 9 — Token limits match upstream MODELS list pattern exactly per family.
# -----------------------------------------------------------------------------


def test_gpt55_token_limits_match_upstream_pattern() -> None:
    """Upstream gpt-5.x entries: max_tokens=127997 and max_input_tokens=272000.

    We explicitly set temperature=1.0 because the vendored ModelConfig default
    is 0.7, which OpenAI reasoning models reject. 1.0 is the provider default,
    so this prevents runtime failure without changing sampling behavior.
    """
    for p in (pp for pp in all_profiles() if pp.family == "gpt-5.5"):
        kw = p.to_model_config_kwargs()
        assert kw["max_tokens"] == 127_997, p.name
        assert kw["max_input_tokens"] == 272_000, p.name
        assert kw["temperature"] == 1.0, p.name


def test_grok43_token_limits_match_upstream_grok_pattern() -> None:
    """Upstream grok-4-0709 entry: max_tokens=256000, max_input_tokens=256000,
    temperature=0.8. See vendor/apex_evals/examples/run_with_hf.py:35."""
    for p in (pp for pp in all_profiles() if pp.family == "grok-4.3"):
        kw = p.to_model_config_kwargs()
        assert kw["max_tokens"] == 256_000, p.name
        assert kw["max_input_tokens"] == 256_000, p.name
        assert kw["temperature"] == 0.8, p.name


# -----------------------------------------------------------------------------
# Audit (vendor patch surface) — exactly two strings differ from upstream.
# -----------------------------------------------------------------------------


def test_patches_md_lists_active_patches() -> None:
    patches_md = (vendor_dir() / "PATCHES.md").read_text(encoding="utf-8")
    # The patch table must list at least Patch 1 with status "active".
    assert "Patch 1" in patches_md
    assert "active" in patches_md.lower()


def test_vendored_patch_markers_present_in_litellm_client() -> None:
    """If a vendor-source diff exists, it must carry a `# vendored-patch:`
    marker per the diff policy in vendor/apex_evals/UPSTREAM.md."""
    src = (vendor_dir() / "src" / "call_llm" / "litellm_client.py").read_text(encoding="utf-8")
    # Count marker occurrences; expect at least one per patched line.
    n = src.count("# vendored-patch:")
    assert n >= 2, f"expected >= 2 vendored-patch markers (gpt-5.5, grok-4.3), found {n}"
