"""Ground-truth response model.

Used by the generator's history period and by the 12-week simulator. It reads hidden latent
parameters and `simulation.yaml: response_model`. Wiqaya's models never call this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

CHANNEL_NEEDS = {"whatsapp": {"smartphone"}, "sms": {"smartphone", "basic"},
                 "call_script": {"smartphone", "basic"}, "chw_script": {"smartphone", "basic", "none"}}  # fmt: skip


@dataclass(frozen=True)
class Contact:
    channel: str
    language: str
    distance_km: float
    bundled: bool = False
    van: bool = False
    touch_index: int = 0  # previous non-responses
    generic: bool = False


def reachable(phone_type: str, channel: str) -> bool:
    return phone_type in CHANNEL_NEEDS[channel]


def p_attend(person: Any, latent: dict[str, Any], contact: Contact, params: dict[str, Any]) -> float:
    """Probability that this contact leads to a booked AND attended visit."""
    return p_book(person, latent, contact, params) * float(params["show_given_booked"])


def p_book(person: Any, latent: dict[str, Any], contact: Contact, params: dict[str, Any]) -> float:
    """Probability that this contact leads to a booking."""
    if not reachable(person.phone_type, contact.channel):
        return 0.0
    x = params["base_logit_by_channel"][contact.channel]
    x += latent["response_propensity_by_channel"][contact.channel]
    if contact.language == person.preferred_language:
        x += params["language_match"] * latent["language_sensitivity"]
    if person.literacy_proxy == "low" and contact.channel in ("whatsapp", "sms"):
        x += params["literacy_low_text_penalty"]
    dist = 1.0 if contact.van else contact.distance_km
    x += params["distance_per_km"] * dist * latent["distance_sensitivity"]
    if contact.bundled:
        x += params["bundle_effect"] * latent["bundle_effect"]
    if contact.van:
        x += params["van_effect"]
    x += params["repeat_touch_decay"] * contact.touch_index
    if contact.generic:
        x += params["generic_reminder_penalty"]
    return 1.0 / (1.0 + math.exp(-x))
