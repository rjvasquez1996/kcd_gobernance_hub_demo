"""Namespace validators."""

from validators.base import Validator, registered_as_validator


@registered_as_validator
class NoDirectNamespaceCreation(Validator):
    """Block direct creation of namespaces."""

    def is_applicable(self, review_request):
        """Apply only to Namespace resources."""
        return review_request.get('object', {}).get('kind', '').lower() == 'namespace'

    def validate(self, review_request):
        """Block all CREATE operations on namespaces."""
        if review_request.get('operation') == 'CREATE':
            return False, 'Direct namespace creation is not allowed. Please contact the governance team to create a namespace'

        return True, None


@registered_as_validator
class RequiredLabelsCheck(Validator):
    """Require specific labels on namespaces."""

    def is_applicable(self, review_request):
        """Apply only to Namespace resources."""
        return review_request.get('object', {}).get('kind', '').lower() == 'namespace'

    def validate(self, review_request):
        """Check that required labels are present."""
        labels = review_request.get('object', {}).get('metadata', {}).get('labels', {})

        required_labels = self.policy_config.get('required_namespace_labels', ['team', 'environment'])

        for required_label in required_labels:
            if required_label not in labels:
                return False, f"Namespace missing required label '{required_label}'. Required labels: {', '.join(required_labels)}"

        return True, None
