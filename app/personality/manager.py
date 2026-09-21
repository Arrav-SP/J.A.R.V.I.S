"""Central manager for personality state, mode switching, and prompt generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

import logging

from app.personality.behavior import BehaviorEngine
from app.personality.models import ModeProfile, OperatingMode, PersonalityTraits
from app.personality.profiles import get_profile, load_mode_profiles

if TYPE_CHECKING:
    from app.config.settings import PersonalityConfig

logger = logging.getLogger("jarvis.personality")


class PersonalityManager:
    """Manages active personality, operating mode transitions, and behavioral prompt generation."""

    def __init__(self, config: Optional[PersonalityConfig] = None) -> None:
        if config is None:
            from app.config.settings import get_settings

            config = get_settings().personality

        self.name: str = config.name
        self.active_mode: OperatingMode = OperatingMode.from_str(config.mode)
        self.base_traits = PersonalityTraits(
            humor=config.humor,
            sarcasm=config.sarcasm,
            formality=config.formality,
            warmth=config.warmth,
            verbosity=config.verbosity,
            confidence=config.confidence,
            proactivity=config.proactivity,
            preferred_address=config.preferred_address,
            response_style=config.response_style,
        )
        self.runtime_overrides: Dict[str, Any] = {}
        self.profiles: Dict[OperatingMode, ModeProfile] = load_mode_profiles()

        logger.info(
            "PersonalityManager initialized (name=%s, mode=%s, address=%s)",
            self.name,
            self.active_mode.value,
            self.base_traits.preferred_address,
        )

    def get_mode(self) -> OperatingMode:
        """Return the current active operating mode."""
        return self.active_mode

    def set_mode(self, mode: OperatingMode | str) -> ModeProfile:
        """Switch the current operating mode and return the newly active profile."""
        if isinstance(mode, str):
            mode = OperatingMode.from_str(mode)

        old_mode = self.active_mode
        self.active_mode = mode
        logger.info("Switched operating mode from '%s' to '%s'", old_mode.value, mode.value)
        return self.get_active_profile()

    def get_active_profile(self) -> ModeProfile:
        """Retrieve the ModeProfile corresponding to the active operating mode."""
        return self.profiles.get(self.active_mode, get_profile(self.active_mode))

    def get_effective_traits(self) -> PersonalityTraits:
        """Compute the effective traits merging baseline, mode overrides, and runtime overrides."""
        profile = self.get_active_profile()

        # Combine mode-specific overrides and any manual runtime overrides
        combined_overrides: Dict[str, Any] = dict(profile.trait_overrides)
        combined_overrides.update(self.runtime_overrides)

        return self.base_traits.copy_with_overrides(combined_overrides)

    def set_trait(self, trait_name: str, value: Any) -> PersonalityTraits:
        """Set a runtime override for a specific trait dimension."""
        clean_name = trait_name.strip().lower()
        if not hasattr(self.base_traits, clean_name):
            raise ValueError(
                f"Unknown trait '{trait_name}'. Valid traits: "
                f"{list(self.base_traits.model_fields.keys())}"
            )

        # Validate by constructing a temporary instance
        test_overrides = dict(self.runtime_overrides)
        test_overrides[clean_name] = value
        effective = self.base_traits.copy_with_overrides(test_overrides)

        self.runtime_overrides[clean_name] = value
        logger.info("Updated trait '%s' to %s", clean_name, value)
        return effective

    def clear_runtime_overrides(self) -> None:
        """Clear manual trait overrides while keeping the active mode."""
        self.runtime_overrides.clear()
        logger.info("Cleared runtime trait overrides.")

    def get_system_instructions(self) -> str:
        """Generate full natural language system prompt instructions for LLM context."""
        effective_traits = self.get_effective_traits()
        active_profile = self.get_active_profile()
        return BehaviorEngine.generate_system_prompt(
            traits=effective_traits,
            profile=active_profile,
            name=self.name,
        )

    def get_status(self) -> Dict[str, Any]:
        """Return a structured summary of active personality settings."""
        effective = self.get_effective_traits()
        profile = self.get_active_profile()
        return {
            "name": self.name,
            "mode": self.active_mode.value,
            "mode_name": profile.name,
            "mode_description": profile.description,
            "traits": effective.model_dump(),
            "has_runtime_overrides": bool(self.runtime_overrides),
        }
