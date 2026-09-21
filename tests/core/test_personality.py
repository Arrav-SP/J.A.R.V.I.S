"""Unit and integration tests for the JARVIS personality subsystem."""

import pytest
from pydantic import ValidationError

from app.config.settings import PersonalityConfig, Settings
from app.core.orchestrator import Orchestrator
from app.personality.behavior import BehaviorEngine
from app.personality.manager import PersonalityManager
from app.personality.models import ModeProfile, OperatingMode, PersonalityTraits
from app.personality.profiles import DEFAULT_PROFILES, get_profile, load_mode_profiles


def test_default_personality_traits() -> None:
    """Verify default personality traits initialization."""
    traits = PersonalityTraits()
    assert traits.humor == 0.6
    assert traits.sarcasm == 0.4
    assert traits.formality == 0.7
    assert traits.warmth == 0.6
    assert traits.verbosity == 0.4
    assert traits.confidence == 0.8
    assert traits.proactivity == 0.5
    assert traits.preferred_address == "sir"
    assert traits.response_style == "concise"


def test_personality_config_parsing() -> None:
    """Verify PersonalityConfig loads and validates config fields."""
    cfg = PersonalityConfig(
        name="JARVIS",
        mode="coding",
        humor=0.2,
        formality=0.9,
        preferred_address="Captain",
    )
    assert cfg.mode == "coding"
    assert cfg.humor == 0.2
    assert cfg.preferred_address == "Captain"


def test_invalid_mode_validation() -> None:
    """Verify invalid operating mode string raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        PersonalityConfig(mode="hyperdrive")
    assert "Invalid personality mode" in str(exc_info.value)


def test_invalid_trait_bounds() -> None:
    """Verify trait values outside [0.0, 1.0] raise ValidationError."""
    with pytest.raises(ValidationError):
        PersonalityTraits(humor=1.5)

    with pytest.raises(ValidationError):
        PersonalityTraits(verbosity=-0.1)


def test_all_operating_modes_profiles() -> None:
    """Verify all 6 standard operating modes have defined profiles."""
    expected_modes = [
        OperatingMode.NORMAL,
        OperatingMode.CODING,
        OperatingMode.STUDY,
        OperatingMode.RESEARCH,
        OperatingMode.PROFESSIONAL,
        OperatingMode.EMERGENCY,
    ]
    profiles = load_mode_profiles()
    for mode in expected_modes:
        assert mode in profiles
        profile = profiles[mode]
        assert profile.name
        assert profile.description
        assert len(profile.directives) > 0


def test_mode_specific_overrides() -> None:
    """Verify switching modes applies mode-specific trait overrides."""
    manager = PersonalityManager()
    assert manager.get_mode() == OperatingMode.NORMAL
    normal_traits = manager.get_effective_traits()
    assert normal_traits.humor == 0.6

    # Switch to CODING mode
    manager.set_mode(OperatingMode.CODING)
    coding_traits = manager.get_effective_traits()
    assert coding_traits.humor == 0.1  # Overridden lower for coding
    assert coding_traits.verbosity == 0.2  # Overridden concise
    assert coding_traits.formality == 0.8

    # Switch to STUDY mode
    manager.set_mode(OperatingMode.STUDY)
    study_traits = manager.get_effective_traits()
    assert study_traits.warmth == 0.9  # Supportive tutor
    assert study_traits.verbosity == 0.7  # Explanatory detail


def test_behavior_engine_prompt_generation() -> None:
    """Verify system prompt generation contains identity, mode directives, and traits."""
    traits = PersonalityTraits(humor=0.8, verbosity=0.2, preferred_address="sir")
    profile = get_profile(OperatingMode.NORMAL)
    prompt = BehaviorEngine.generate_system_prompt(traits=traits, profile=profile, name="JARVIS")

    assert "You are JARVIS" in prompt
    assert "ACTIVE OPERATING MODE: NORMAL" in prompt
    assert "Address the user respectfully as 'sir'" in prompt
    assert "clever wit, sharp banter" in prompt
    assert "extremely concise" in prompt


def test_humor_trait_changes_behavior_prompt() -> None:
    """Verify adjusting humor changes generated behavioral instructions."""
    profile = get_profile(OperatingMode.NORMAL)

    high_humor_prompt = BehaviorEngine.generate_system_prompt(
        traits=PersonalityTraits(humor=0.9), profile=profile
    )
    assert "clever wit, sharp banter" in high_humor_prompt

    low_humor_prompt = BehaviorEngine.generate_system_prompt(
        traits=PersonalityTraits(humor=0.1), profile=profile
    )
    assert "Maintain strict seriousness" in low_humor_prompt


def test_verbosity_trait_changes_behavior_prompt() -> None:
    """Verify adjusting verbosity changes generated behavioral instructions."""
    profile = get_profile(OperatingMode.NORMAL)

    terse_prompt = BehaviorEngine.generate_system_prompt(
        traits=PersonalityTraits(verbosity=0.1), profile=profile
    )
    assert "extremely concise" in terse_prompt

    verbose_prompt = BehaviorEngine.generate_system_prompt(
        traits=PersonalityTraits(verbosity=0.9), profile=profile
    )
    assert "comprehensive, thorough" in verbose_prompt


def test_safety_invariant_always_present() -> None:
    """Verify safety invariant directive is unconditionally embedded regardless of traits or mode."""
    # Test extreme sarcasm, zero formality, emergency mode
    extreme_traits = PersonalityTraits(humor=1.0, sarcasm=1.0, formality=0.0)
    emergency_profile = get_profile(OperatingMode.EMERGENCY)

    prompt = BehaviorEngine.generate_system_prompt(
        traits=extreme_traits,
        profile=emergency_profile,
    )

    assert "SAFETY & INTEGRITY INVARIANT (NON-NEGOTIABLE)" in prompt
    assert "MUST NEVER override safety policies" in prompt
    assert "Never hallucinate, provide reckless instructions, or perform destructive actions" in prompt


def test_runtime_trait_overrides() -> None:
    """Verify setting and clearing runtime trait overrides on PersonalityManager."""
    manager = PersonalityManager()
    manager.set_trait("humor", 0.95)
    assert manager.get_effective_traits().humor == 0.95

    manager.clear_runtime_overrides()
    assert manager.get_effective_traits().humor == 0.6  # Back to baseline


def test_orchestrator_mode_switching() -> None:
    """Verify Orchestrator switches mode and adapts responses dynamically."""
    settings = Settings()
    orchestrator = Orchestrator(settings=settings)

    # Initial mode is NORMAL
    assert orchestrator.get_mode() == "normal"
    resp_normal = orchestrator.process_message("Explain recursion.")
    assert "programming concept" in resp_normal

    # Switch to CODING mode
    switch_msg = orchestrator.set_mode("coding")
    assert "CODING" in switch_msg
    assert orchestrator.get_mode() == "coding"
    resp_coding = orchestrator.process_message("Explain recursion.")
    assert "```python" in resp_coding
    assert "def recurse" in resp_coding

    # Switch to STUDY mode
    orchestrator.set_mode("study")
    assert orchestrator.get_mode() == "study"
    resp_study = orchestrator.process_message("Explain recursion.")
    assert "Russian nesting dolls" in resp_study

    # Switch to EMERGENCY mode
    orchestrator.set_mode("emergency")
    assert orchestrator.get_mode() == "emergency"
    resp_emergency = orchestrator.process_message("Explain recursion.")
    assert "EMERGENCY" in resp_emergency or "CRITICAL" in resp_emergency


def test_orchestrator_personality_status() -> None:
    """Verify Orchestrator returns structured personality status."""
    orchestrator = Orchestrator()
    status = orchestrator.get_personality_status()
    assert status["name"] == "JARVIS"
    assert status["mode"] == "normal"
    assert "traits" in status
    assert status["traits"]["preferred_address"] == "sir"


def test_personality_clean_independent_import_no_circular_dependencies() -> None:
    """Verify app.personality and its models can be imported in isolation without circular import errors."""
    import subprocess
    import sys

    # Test importing app.personality in a clean interpreter process
    res1 = subprocess.run(
        [sys.executable, "-c", "import app.personality"],
        capture_output=True,
        text=True,
    )
    assert res1.returncode == 0, f"import app.personality failed: {res1.stderr}"

    # Test importing app.personality.models in a clean interpreter process
    res2 = subprocess.run(
        [sys.executable, "-c", "from app.personality.models import PersonalityTraits, ModeProfile"],
        capture_output=True,
        text=True,
    )
    assert res2.returncode == 0, f"import models failed: {res2.stderr}"

