"""Pod validators."""

from validators.base import Validator, registered_as_validator


def _iter_containers(review_request):
    """Iterate over all containers in a pod/deployment/job."""
    spec = review_request.get('object', {}).get('spec', {})

    # Handle pod templates (for Deployments, StatefulSets, DaemonSets, etc.)
    if 'template' in spec:
        template_spec = spec['template'].get('spec', {})
        containers = template_spec.get('containers', [])
        init_containers = template_spec.get('initContainers', [])
    else:
        # Handle direct Pod resources
        containers = spec.get('containers', [])
        init_containers = spec.get('initContainers', [])

    for container in containers + init_containers:
        yield container


@registered_as_validator
class ForbidPrivilegedMode(Validator):
    """Block privileged containers and privilege escalation."""

    def is_applicable(self, review_request):
        """Apply to pods, deployments, jobs, etc."""
        kind = review_request.get('object', {}).get('kind', '').lower()
        return kind in ('pod', 'deployment', 'statefulset', 'daemonset', 'job', 'cronjob', 'replicaset')

    def validate(self, review_request):
        """Check for privileged mode or privilege escalation."""
        for container in _iter_containers(review_request):
            sec_ctx = container.get('securityContext', {})

            if sec_ctx.get('privileged'):
                return False, f"Container '{container.get('name', 'unknown')}' has privileged: true which is not allowed"

            if sec_ctx.get('allowPrivilegeEscalation'):
                return False, f"Container '{container.get('name', 'unknown')}' has allowPrivilegeEscalation: true which is not allowed"

        return True, None


@registered_as_validator
class RequireResourceLimits(Validator):
    """Require CPU and memory limits on all containers."""

    def is_applicable(self, review_request):
        """Apply to pods and pod templates."""
        kind = review_request.get('object', {}).get('kind', '').lower()
        return kind in ('pod', 'deployment', 'statefulset', 'daemonset', 'job', 'cronjob', 'replicaset')

    def validate(self, review_request):
        """Check that all containers have resource limits."""
        for container in _iter_containers(review_request):
            name = container.get('name', 'unknown')
            limits = container.get('resources', {}).get('limits', {})

            if 'cpu' not in limits:
                return False, f"Container '{name}' missing CPU limit. Set resources.limits.cpu"

            if 'memory' not in limits:
                return False, f"Container '{name}' missing memory limit. Set resources.limits.memory"

        return True, None


@registered_as_validator
class ForbidLatestTag(Validator):
    """Block images using the :latest tag."""

    def is_applicable(self, review_request):
        """Apply to pods and pod templates."""
        kind = review_request.get('object', {}).get('kind', '').lower()
        return kind in ('pod', 'deployment', 'statefulset', 'daemonset', 'job', 'cronjob', 'replicaset')

    def validate(self, review_request):
        """Check that no container uses :latest tag."""
        for container in _iter_containers(review_request):
            image = container.get('image', '')
            name = container.get('name', 'unknown')

            # Check if image ends with :latest or has no tag
            if image.endswith(':latest') or ':' not in image:
                return False, f"Container '{name}' uses untagged or :latest image '{image}'. Use explicit, non-latest tags"

        return True, None
