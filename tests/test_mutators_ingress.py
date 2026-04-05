"""Unit tests for ingress mutators."""

import pytest
from mutators.ingress import IngressClassDefaultMutator
from conftest import load_request, make_ingress_request, make_pod_request, make_container


class TestIngressClassDefaultMutatorApplicable:
    def setup_method(self):
        self.m = IngressClassDefaultMutator()

    def test_applies_to_ingress(self):
        assert self.m.is_applicable(load_request('ingresses/valid')) is True

    def test_does_not_apply_to_pod(self):
        assert self.m.is_applicable(load_request('pods/valid')) is False

    def test_does_not_apply_to_namespace(self):
        assert self.m.is_applicable(load_request('namespaces/create')) is False


class TestIngressClassDefaultMutatorGeneratePatch:
    def setup_method(self):
        self.m = IngressClassDefaultMutator()

    def test_adds_ingress_class_when_missing(self):
        patches = self.m.generate_patch(load_request('ingresses/no_ingress_class'))
        assert len(patches) == 1
        p = patches[0]
        assert p['op'] == 'add'
        assert p['path'] == '/spec/ingressClassName'
        assert p['value'] == 'nginx'

    def test_no_patch_when_ingress_class_already_set(self):
        patches = self.m.generate_patch(load_request('ingresses/with_ingress_class'))
        assert patches == []

    def test_no_patch_when_ingress_class_is_nginx(self):
        req = make_ingress_request(ingress_class_name='nginx')
        patches = self.m.generate_patch(req)
        assert patches == []
