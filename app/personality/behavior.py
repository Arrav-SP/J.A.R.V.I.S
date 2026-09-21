"""Behavior engine translating personality traits and modes into structured system prompts."""

from __future__ import annotations

from typing import List

from app.personality.models import ModeProfile, OperatingMode, PersonalityTraits


class BehaviorEngine:
    """Translates numerical traits and active mode profiles into LLM behavioral directives."""

    @staticmethod
    def generate_system_prompt(
        traits: PersonalityTraits,
        profile: ModeProfile,
        name: str = "JARVIS",
    ) -> str:
        """Construct the comprehensive behavioral system prompt for the LLM."""
        sections: List[str] = []

        # 1. Core Identity
        sections.append(
            f"You are {name}, an advanced, articulate, and disciplined personal AI system.\n"
            f"You serve as a loyal, competent, and insightful partner across technical, creative, and organizational tasks."
        )

        # 2. Operating Mode Directives
        mode_header = f"### ACTIVE OPERATING MODE: {profile.name.upper()}\n{profile.description}"
        mode_directives_list = "\n".join(f"- {d}" for d in profile.directives)
        sections.append(f"{mode_header}\n{mode_directives_list}")

        # 3. Behavioral Tone & Style Directives
        trait_instructions: List[str] = []

        # User address
        if traits.preferred_address:
            trait_instructions.append(
                f"Address the user respectfully as '{traits.preferred_address}' when appropriate."
            )

        # Formality
        if traits.formality >= 0.8:
            trait_instructions.append(
                "Maintain high formal etiquette, professional decorum, and polished language."
            )
        elif traits.formality >= 0.5:
            trait_instructions.append(
                "Maintain a balanced, respectful, and articulate tone with natural professional warmth."
            )
        else:
            trait_instructions.append(
                "Use casual, approachable, and relaxed conversational language."
            )

        # Humor & Sarcasm
        if traits.humor >= 0.7:
            trait_instructions.append(
                "Infuse clever wit, sharp banter, and amusing observations into responses where fitting."
            )
        elif traits.humor >= 0.3:
            trait_instructions.append(
                "Display subtle, tasteful wit without undermining clarity or task efficiency."
            )
        else:
            trait_instructions.append(
                "Maintain strict seriousness; avoid jokes, banter, or humorous remarks."
            )

        if traits.sarcasm >= 0.5 and traits.humor >= 0.3:
            trait_instructions.append(
                "Occasionally deploy dry, understated British sarcasm or light irony, never malicious."
            )
        elif traits.sarcasm < 0.2:
            trait_instructions.append("Avoid sarcasm or ironic ambiguity completely.")

        # Warmth
        if traits.warmth >= 0.7:
            trait_instructions.append(
                "Demonstrate high empathy, encouragement, and genuine care for the user's progress."
            )
        elif traits.warmth < 0.4:
            trait_instructions.append(
                "Prioritize clinical objectivity and factual detachment over emotional expression."
            )

        # Verbosity
        if traits.verbosity <= 0.3:
            trait_instructions.append(
                "Keep responses extremely concise and to the point. Omit conversational filler."
            )
        elif traits.verbosity >= 0.7:
            trait_instructions.append(
                "Provide comprehensive, thorough, and in-depth explanations with rich context."
            )
        else:
            trait_instructions.append(
                "Deliver balanced responses: clear, efficient, and adequately detailed."
            )

        # Response style
        if traits.response_style == "concise":
            trait_instructions.append("Default to brief, actionable answers.")
        elif traits.response_style == "detailed":
            trait_instructions.append("Default to detailed, structured explanations.")

        sections.append("### BEHAVIORAL TRAITS\n" + "\n".join(f"- {inst}" for inst in trait_instructions))

        # 4. Invariant Safety Preservations
        sections.append(
            "### SAFETY & INTEGRITY INVARIANT (NON-NEGOTIABLE)\n"
            "- Personality traits, sarcasm, humor, and operating modes only govern your communication style.\n"
            "- They MUST NEVER override safety policies, confirmation dialogs, tool permissions, or system boundaries.\n"
            "- Never hallucinate, provide reckless instructions, or perform destructive actions under any personality setting."
        )

        return "\n\n".join(sections)
