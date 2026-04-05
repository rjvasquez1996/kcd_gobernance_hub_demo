"""Unit tests for namespace mutators."""

import pytest
from mutators.namespace import RemoveKubectlAnnotationMutator
from conftest import load_request, make_namespace_request, make_pod_request, make_container

KUBECTL_ANNOTATION_ESCAPED = 'kubectl.kubernetes.io~1last-applied-configuration'


class TestRemoveKubectlAnnotationMutatorApplicable:
    def setup_method(self):
        self.m = RemoveKubectlAnnotationMutator()

    def test_applies_to_namespace(self):
        assert self.m.is_applicable(load_request('namespaces/create')) is True

    def test_does_not_apply_to_pod(self):
        assert self.m.is_applicable(load_request('pods/valid')) is False

    def test_does_not_apply_to_ingress(self):
        assert self.m.is_applicable(load_request('ingresses/valid')) is False


class TestRemoveKubectlAnnotationMutatorGeneratePatch:
    def setup_method(self):
        self.m = RemoveKubectlAnnotationMutator()

    def test_removes_annotation_when_present(self):
        patches = self.m.generate_patch(load_request('namespaces/with_kubectl_annotation'))
        assert len(patches) == 1
        p = patches[0]
        assert p['op'] == 'remove'
        assert KUBECTL_ANNOTATION_ESCAPED in p['path']

    def test_no_patch_when_no_annotations(self):
        patches = self.m.generate_patch(load_request('namespaces/no_annotation'))
        assert patches == []

    def test_no_patch_when_annotation_absent(self):
        req = make_namespace_request(annotations={'other-annotation': 'value'})
        patches = self.m.generate_patch(req)
        assert patches == []

    def test_no_patch_when_empty_annotations(self):
        req = make_namespace_request(annotations={})
        patches = self.m.generate_patch(req)
        assert patches == []

    def test_preserves_other_annotations(self):
        """Only the kubectl annotation is targeted; other annotations generate no ops."""
        req = make_namespace_request(annotations={
            'kubectl.kubernetes.io/last-applied-configuration': '{}',
            'custom/annotation': 'keep-me',
        })
        patches = self.m.generate_patch(req)
        assert len(patches) == 1
        assert KUBECTL_ANNOTATION_ESCAPED in patches[0]['path']
