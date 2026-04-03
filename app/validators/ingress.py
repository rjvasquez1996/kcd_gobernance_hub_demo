"""Ingress validators."""

from validators.base import Validator, registered_as_validator


@registered_as_validator
class IngressTLSRequired(Validator):
    """Require TLS configuration on all ingresses."""

    def is_applicable(self, review_request):
        """Apply only to Ingress resources."""
        return review_request.get('object', {}).get('kind', '').lower() == 'ingress'

    def validate(self, review_request):
        """Check that TLS is configured."""
        tls = review_request.get('object', {}).get('spec', {}).get('tls', [])

        if not tls:
            return False, 'Ingress must have TLS configured. Add spec.tls[] with at least one host and secretName'

        return True, None


@registered_as_validator
class IngressRuleLimit(Validator):
    """Limit the number of rules in an Ingress."""

    def is_applicable(self, review_request):
        """Apply only to Ingress resources."""
        return review_request.get('object', {}).get('kind', '').lower() == 'ingress'

    def validate(self, review_request):
        """Check that ingress doesn't exceed rule limit."""
        rules = review_request.get('object', {}).get('spec', {}).get('rules', [])
        max_rules = self.policy_config.get('max_ingress_rules', 5)

        if len(rules) > max_rules:
            return False, f'Ingress has {len(rules)} rules, maximum allowed is {max_rules}'

        return True, None
