"""Namespace mutators."""

from mutators.base import Mutator, registered_as_mutator


@registered_as_mutator
class RemoveKubectlAnnotationMutator(Mutator):
    """Remove kubectl.kubernetes.io/last-applied-configuration annotation."""

    def is_applicable(self, review_request):
        """Apply only to Namespace resources."""
        kind = review_request.get('object', {}).get('kind', '').lower()
        return kind == 'namespace'

    def generate_patch(self, review_request):
        """Remove the kubectl annotation if present."""
        annotations = review_request.get('object', {}).get('metadata', {}).get('annotations', {})

        if 'kubectl.kubernetes.io/last-applied-configuration' in annotations:
            return [{
                'op': 'remove',
                'path': '/metadata/annotations/kubectl.kubernetes.io~1last-applied-configuration',
            }]

        return []
