"""Base mutator class and registration mechanism."""

_mutators = []


def registered_as_mutator(mutator_class):
    """Decorator to register a mutator class."""
    _mutators.append(mutator_class)
    return mutator_class


def get_mutators():
    """Get all registered mutators."""
    return _mutators


class Mutator:
    """Base class for all mutators."""

    def __init__(self, policy_config=None):
        """Initialize mutator with optional policy config."""
        self.policy_config = policy_config or {}

    def is_applicable(self, review_request):
        """Check if this mutator applies to the given review request.

        Args:
            review_request: dict from AdmissionReview.request

        Returns:
            bool: True if mutator should run
        """
        raise NotImplementedError()

    def generate_patch(self, review_request):
        """Generate JSON Patch operations for this resource.

        Args:
            review_request: dict from AdmissionReview.request

        Returns:
            list: List of RFC 6902 JSON Patch operations
                  Each operation should be a dict with 'op', 'path', and 'value'
        """
        raise NotImplementedError()

    @staticmethod
    def _mutate_metadata_field(review_request, field, data, override_existing=True):
        """Helper to generate JSON Patch ops for metadata field changes.

        Args:
            review_request: The admission review request
            field: metadata field name ('labels' or 'annotations')
            data: dict of key-value pairs to add/update
            override_existing: whether to replace existing values

        Returns:
            list: JSON Patch operations
        """
        existing_data = review_request.get('object', {}).get('metadata', {}).get(field) or {}
        patch = []

        # If field doesn't exist, create it first
        if field not in review_request.get('object', {}).get('metadata', {}):
            patch.append({
                'op': 'add',
                'path': f'/metadata/{field}',
                'value': data,
            })
            return patch

        for name, value in data.items():
            # Escape '/' characters in key names for JSON Patch
            escaped_name = name.replace('/', '~1')

            if name in existing_data:
                if override_existing:
                    patch.append({
                        'op': 'replace',
                        'path': f'/metadata/{field}/{escaped_name}',
                        'value': value,
                    })
            else:
                patch.append({
                    'op': 'add',
                    'path': f'/metadata/{field}/{escaped_name}',
                    'value': value,
                })

        return patch
