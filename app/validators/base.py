"""Base validator class and registration mechanism."""

import os

_validators = []


def registered_as_validator(validator_class):
    """Decorator to register a validator class."""
    _validators.append(validator_class)
    return validator_class


def get_validators():
    """Get all registered validators, filtered by ENABLED_VALIDATORS env var.

    If ENABLED_VALIDATORS is not set, all validators are returned.
    Otherwise, only validators whose class names appear in the comma-separated list are returned.
    """
    enabled = os.environ.get('ENABLED_VALIDATORS', '')
    if not enabled:
        return _validators

    enabled_set = set(name.strip() for name in enabled.split(',') if name.strip())
    return [v for v in _validators if v.__name__ in enabled_set]


class Validator:
    """Base class for all validators."""

    def __init__(self, policy_config=None):
        """Initialize validator with optional policy config."""
        self.policy_config = policy_config or {}

    def is_applicable(self, review_request):
        """Check if this validator applies to the given review request.

        Args:
            review_request: dict from AdmissionReview.request

        Returns:
            bool: True if validator should run
        """
        raise NotImplementedError()

    def validate(self, review_request):
        """Validate the given review request.

        Args:
            review_request: dict from AdmissionReview.request

        Returns:
            tuple: (allowed: bool, message: str|None)
                   If allowed=False, message should explain the denial
        """
        raise NotImplementedError()
