"""
Scoring Weights — Production Locked (v1)

This file defines all scoring constants.
No magic numbers should exist inside scoring functions.

Design Goals:
- Conservative stability-first weighting
- Deterministic and explainable scoring
- Easy future tuning
- Explicit versioning
"""

# ---------------------------------------------------------
# Score Version
# ---------------------------------------------------------

SCORE_VERSION = 1


# ---------------------------------------------------------
# Core Weight Spine
# ---------------------------------------------------------

# Canonical truth confidence importance
CONFIDENCE_WEIGHT = 0.45

# Stability of truth (reduces volatility)
STABILITY_WEIGHT = 0.25

# Verified source bonus influence
VERIFIED_WEIGHT = 0.15

# Operational signals (is_active, flags, etc.)
OPERATIONAL_WEIGHT = 0.10

# Light local validation signal
LOCAL_VALIDATION_WEIGHT = 0.05


# ---------------------------------------------------------
# Penalty Controls
# ---------------------------------------------------------

# Prevent hype spikes or low-quality bursts
HYPE_PENALTY_WEIGHT = 0.20


# ---------------------------------------------------------
# Score Normalization Controls
# ---------------------------------------------------------

# Clamp bounds to ensure deterministic score range
MIN_SCORE = 0.0
MAX_SCORE = 100.0


# ---------------------------------------------------------
# Safety Thresholds
# ---------------------------------------------------------

# If truth confidence below this, apply heavy dampening
LOW_CONFIDENCE_THRESHOLD = 0.30

# If stability below this, reduce score impact
LOW_STABILITY_THRESHOLD = 0.20