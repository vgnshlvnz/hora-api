"""Scoring configuration: weights and quality values are settings, not constants.

Override with environment variables prefixed HORA_SCORING_ (e.g. HORA_SCORING_WEIGHT_HORA=60).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HORA_SCORING_", frozen=True)

    # Component weights. The final score is normalised over the active components, so the
    # weights need not sum to 100.
    weight_tara: float = 25.0
    weight_chandra: float = 25.0
    weight_hora: float = 50.0
    # Used only when the profile has dasha periods; otherwise the dasha weight is 0.
    weight_dasha_when_given: float = 20.0

    # Value (0-1) of each quality class.
    value_good: float = 1.0
    value_bad: float = 0.0
    value_neutral: float = 0.5
    # Tara 1 (Janma) and chandrabala houses 2, 5, 9 are configurable.
    tara_janma_value: float = 0.5
    # Houses 2, 5 and 9 depend on paksha (some traditions allow them in shukla paksha): one value
    # per paksha, judged at the start of the hora. Turn it off to use the single value below.
    chandra_paksha: bool = True
    chandra_conditional_shukla_value: float = 1.0
    chandra_conditional_krishna_value: float = 0.5
    chandra_conditional_value: float = 0.5  # used when chandra_paksha is off
    # Dasha match: hora lord is the running dasha/bhukti lord, or a natural friend of one.
    dasha_match_value: float = 1.0
    dasha_friend_value: float = 0.5

    # Rasi matrix: chandrabala only, plus an optional generic hora-lord term (off by default).
    rasi_hora_generic: bool = False
    rasi_weight_chandra: float = 50.0
    rasi_weight_hora: float = 50.0
