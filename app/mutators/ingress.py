"""Ingress mutators."""

from mutators.base import Mutator, registered_as_mutator


@registered_as_mutator
class IngressClassDefaultMutator(Mutator):
    """Set default ingressClassName if not specified."""

    def is_applicable(self, review_request):
        """Apply only to Ingress resources."""
        return review_request.get('object', {}).get('kind', '').lower() == 'ingress'

    def generate_patch(self, review_request):
        """Set ingressClassName to 'nginx' if not present."""
        spec = review_request.get('object', {}).get('spec', {})

        # Check if ingressClassName is already set
        if 'ingressClassName' not in spec:
            return [{
                'op': 'add',
                'path': '/spec/ingressClassName',
                'value': 'nginx',
            }]

        return []
