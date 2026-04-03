"""Base validator class and registration mechanism."""

_validators = []


def registered_as_validator(validator_class):
    """Decorator to register a validator class."""
    _validators.append(validator_class)
    return validator_class


def get_validators():
    """Get all registered validators."""
    return _validators


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
