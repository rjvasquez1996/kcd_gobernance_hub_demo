"""Unit tests for pod mutators."""

import pytest
from mutators.pod import CommonLabelsMutator, DefaultResourcesMutator
from conftest import load_request, make_pod_request, make_container, make_namespace_request


GOVERNANCE_LABELS = {
    'app.kubernetes.io/managed-by': 'governance-hub-demo',
    'governance/policy-version': 'v1',
}


# ---------------------------------------------------------------------------
# CommonLabelsMutator
# ---------------------------------------------------------------------------

class TestCommonLabelsMutatorApplicable:
    def setup_method(self):
        self.m = CommonLabelsMutator()

    def test_applies_to_pod(self):
        assert self.m.is_applicable(load_request('pods/valid')) is True

    def test_applies_to_deployment(self):
        req = load_request('pods/valid')
        req['object']['kind'] = 'Deployment'
        assert self.m.is_applicable(req) is True

    def test_does_not_apply_to_namespace(self):
        assert self.m.is_applicable(load_request('namespaces/create')) is False

    def test_does_not_apply_to_ingress(self):
        assert self.m.is_applicable(load_request('ingresses/valid')) is False


class TestCommonLabelsMutatorGeneratePatch:
    def setup_method(self):
        self.m = CommonLabelsMutator()

    def test_adds_labels_field_when_missing(self):
        # pods/no_labels has no metadata.labels key
        patches = self.m.generate_patch(load_request('pods/no_labels'))
        assert len(patches) == 1
        assert patches[0]['op'] == 'add'
        assert patches[0]['path'] == '/metadata/labels'
        assert patches[0]['value'] == GOVERNANCE_LABELS

    def test_no_patches_when_governance_labels_already_present(self):
        # pods/governance_labels_and_resources already has both governance labels
        patches = self.m.generate_patch(load_request('pods/governance_labels_and_resources'))
        assert patches == []

    def test_adds_individual_labels_when_labels_field_exists(self):
        req = make_pod_request([make_container()], labels={'app': 'my-app'})
        patches = self.m.generate_patch(req)
        paths = {p['path'] for p in patches}
        assert '/metadata/labels/app.kubernetes.io~1managed-by' in paths
        assert '/metadata/labels/governance~1policy-version' in paths
        assert all(p['op'] == 'add' for p in patches)

    def test_does_not_override_existing_governance_label(self):
        existing_labels = {
            'app.kubernetes.io/managed-by': 'something-else',
            'governance/policy-version': 'v1',
        }
        req = make_pod_request([make_container()], labels=existing_labels)
        patches = self.m.generate_patch(req)
        assert patches == []

    def test_adds_only_missing_governance_label(self):
        req = make_pod_request([make_container()], labels={'app.kubernetes.io/managed-by': 'other'})
        patches = self.m.generate_patch(req)
        assert len(patches) == 1
        assert 'governance~1policy-version' in patches[0]['path']
        assert patches[0]['op'] == 'add'


# ---------------------------------------------------------------------------
# DefaultResourcesMutator
# ---------------------------------------------------------------------------

class TestDefaultResourcesMutatorApplicable:
    def setup_method(self):
        self.m = DefaultResourcesMutator()

    def test_applies_to_pod(self):
        assert self.m.is_applicable(load_request('pods/valid')) is True

    def test_does_not_apply_to_ingress(self):
        assert self.m.is_applicable(load_request('ingresses/valid')) is False


class TestDefaultResourcesMutatorGeneratePatch:
    def setup_method(self):
        self.m = DefaultResourcesMutator()

    DEFAULT_RESOURCES = {
        'requests': {'cpu': '100m', 'memory': '128Mi'},
        'limits': {'cpu': '100m', 'memory': '128Mi'},
    }

    def test_adds_full_resources_block_when_missing(self):
        patches = self.m.generate_patch(load_request('pods/no_resources'))
        assert len(patches) == 1
        p = patches[0]
        assert p['op'] == 'add'
        assert p['path'] == '/spec/containers/0/resources'
        assert p['value'] == self.DEFAULT_RESOURCES

    def test_no_patches_when_requests_and_limits_both_present(self):
        patches = self.m.generate_patch(load_request('pods/governance_labels_and_resources'))
        assert patches == []

    def test_adds_requests_when_only_limits_present(self):
        c = make_container(resources={'limits': {'cpu': '500m', 'memory': '256Mi'}})
        req = make_pod_request([c])
        patches = self.m.generate_patch(req)
        assert len(patches) == 1
        assert 'requests' in patches[0]['path']

    def test_adds_limits_when_only_requests_present(self):
        c = make_container(resources={'requests': {'cpu': '100m', 'memory': '64Mi'}})
        req = make_pod_request([c])
        patches = self.m.generate_patch(req)
        assert len(patches) == 1
        assert 'limits' in patches[0]['path']

    def test_patches_multiple_containers(self):
        containers = [make_container(name='a'), make_container(name='b')]
        req = make_pod_request(containers)
        patches = self.m.generate_patch(req)
        paths = [p['path'] for p in patches]
        assert '/spec/containers/0/resources' in paths
        assert '/spec/containers/1/resources' in paths

    def test_patches_init_container(self):
        req = make_pod_request(
            containers=[make_container(resources={
                'requests': {'cpu': '100m', 'memory': '64Mi'},
                'limits': {'cpu': '100m', 'memory': '64Mi'},
            })],
            init_containers=[make_container(name='init')],
        )
        patches = self.m.generate_patch(req)
        assert len(patches) == 1
        assert '/spec/initContainers/0/resources' in patches[0]['path']

    def test_uses_pod_template_path_for_deployment_style(self):
        req = {
            'uid': 'test',
            'object': {
                'kind': 'Deployment',
                'metadata': {'name': 'my-deploy'},
                'spec': {
                    'template': {
                        'spec': {
                            'containers': [{'name': 'app', 'image': 'nginx:1.21'}],
                        }
                    }
                }
            }
        }
        patches = self.m.generate_patch(req)
        assert len(patches) == 1
        assert patches[0]['path'].startswith('/spec/template/spec/containers/0')
