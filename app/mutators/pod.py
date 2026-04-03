"""Pod mutators."""

from mutators.base import Mutator, registered_as_mutator


def _iter_containers(review_request):
    """Iterate over all containers in a pod/deployment/job with their paths."""
    spec = review_request.get('object', {}).get('spec', {})

    # Handle pod templates (for Deployments, StatefulSets, DaemonSets, etc.)
    if 'template' in spec:
        template_spec = spec['template'].get('spec', {})
        containers = template_spec.get('containers', [])
        init_containers = template_spec.get('initContainers', [])
        base_path = '/spec/template/spec'
    else:
        # Handle direct Pod resources
        containers = spec.get('containers', [])
        init_containers = spec.get('initContainers', [])
        base_path = '/spec'

    for i, container in enumerate(containers):
        yield f'{base_path}/containers/{i}', container

    for i, container in enumerate(init_containers):
        yield f'{base_path}/initContainers/{i}', container


@registered_as_mutator
class CommonLabelsMutator(Mutator):
    """Inject common governance labels."""

    def is_applicable(self, review_request):
        """Apply to pods and pod templates."""
        kind = review_request.get('object', {}).get('kind', '').lower()
        return kind in ('pod', 'deployment', 'statefulset', 'daemonset', 'job', 'cronjob', 'replicaset')

    def generate_patch(self, review_request):
        """Add governance labels."""
        labels = {
            'app.kubernetes.io/managed-by': 'governance-hub-demo',
            'governance/policy-version': 'v1',
        }

        return self._mutate_metadata_field(review_request, 'labels', labels, override_existing=False)


@registered_as_mutator
class DefaultResourcesMutator(Mutator):
    """Inject default resource requests if missing."""

    def is_applicable(self, review_request):
        """Apply to pods and pod templates."""
        kind = review_request.get('object', {}).get('kind', '').lower()
        return kind in ('pod', 'deployment', 'statefulset', 'daemonset', 'job', 'cronjob', 'replicaset')

    def generate_patch(self, review_request):
        """Add default resources if they don't exist."""
        patch = []
        default_cpu = '100m'
        default_memory = '128Mi'

        for container_path, container in _iter_containers(review_request):
            if 'resources' not in container:
                # Create the entire resources object
                patch.append({
                    'op': 'add',
                    'path': f'{container_path}/resources',
                    'value': {
                        'requests': {
                            'cpu': default_cpu,
                            'memory': default_memory,
                        },
                        'limits': {
                            'cpu': default_cpu,
                            'memory': default_memory,
                        }
                    }
                })
            else:
                resources = container.get('resources', {})

                # Add requests if missing
                if 'requests' not in resources:
                    patch.append({
                        'op': 'add',
                        'path': f'{container_path}/resources/requests',
                        'value': {
                            'cpu': default_cpu,
                            'memory': default_memory,
                        }
                    })

                # Add limits if missing
                if 'limits' not in resources:
                    patch.append({
                        'op': 'add',
                        'path': f'{container_path}/resources/limits',
                        'value': {
                            'cpu': default_cpu,
                            'memory': default_memory,
                        }
                    })

        return patch
