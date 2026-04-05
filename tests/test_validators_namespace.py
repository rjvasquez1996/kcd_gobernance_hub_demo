"""Unit tests for namespace validators."""

import pytest
from validators.namespace import NoDirectNamespaceCreation, RequiredLabelsCheck
from conftest import load_request, make_namespace_request, make_pod_request, make_container


# ---------------------------------------------------------------------------
# NoDirectNamespaceCreation
# ---------------------------------------------------------------------------

class TestNoDirectNamespaceCreationApplicable:
    def setup_method(self):
        self.v = NoDirectNamespaceCreation()

    def test_applies_to_namespace(self):
        assert self.v.is_applicable(load_request('namespaces/create')) is True

    def test_does_not_apply_to_pod(self):
        assert self.v.is_applicable(load_request('pods/valid')) is False

    def test_does_not_apply_to_ingress(self):
        assert self.v.is_applicable(load_request('ingresses/valid')) is False


class TestNoDirectNamespaceCreationValidate:
    def setup_method(self):
        self.v = NoDirectNamespaceCreation()

    def test_denies_create_operation(self):
        allowed, msg = self.v.validate(load_request('namespaces/create'))
        assert allowed is False
        assert 'namespace' in msg.lower()

    def test_allows_update_operation(self):
        allowed, _ = self.v.validate(load_request('namespaces/update_with_labels'))
        assert allowed is True

    def test_allows_delete_operation(self):
        req = make_namespace_request(operation='DELETE')
        allowed, _ = self.v.validate(req)
        assert allowed is True


# ---------------------------------------------------------------------------
# RequiredLabelsCheck
# ---------------------------------------------------------------------------

class TestRequiredLabelsCheckApplicable:
    def setup_method(self):
        self.v = RequiredLabelsCheck()

    def test_applies_to_namespace(self):
        assert self.v.is_applicable(load_request('namespaces/create')) is True

    def test_does_not_apply_to_pod(self):
        assert self.v.is_applicable(load_request('pods/valid')) is False


class TestRequiredLabelsCheckValidate:
    def setup_method(self):
        self.v = RequiredLabelsCheck()

    def test_allows_namespace_with_required_labels(self):
        allowed, _ = self.v.validate(load_request('namespaces/update_with_labels'))
        assert allowed is True

    def test_denies_namespace_without_labels(self):
        allowed, msg = self.v.validate(load_request('namespaces/update_without_labels'))
        assert allowed is False

    def test_denies_missing_team_label(self):
        req = make_namespace_request(labels={'environment': 'prod'})
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'team' in msg

    def test_denies_missing_environment_label(self):
        req = make_namespace_request(labels={'team': 'platform'})
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'environment' in msg

    def test_allows_namespace_with_extra_labels(self):
        req = make_namespace_request(labels={
            'team': 'platform', 'environment': 'prod', 'extra': 'label',
        })
        allowed, _ = self.v.validate(req)
        assert allowed is True

    def test_denies_empty_labels(self):
        req = make_namespace_request(labels={})
        allowed, _ = self.v.validate(req)
        assert allowed is False

    def test_custom_required_labels_via_policy_config(self):
        v = RequiredLabelsCheck(policy_config={'required_namespace_labels': ['owner']})
        req = make_namespace_request(labels={'owner': 'alice'})
        allowed, _ = v.validate(req)
        assert allowed is True

    def test_custom_required_labels_denies_when_missing(self):
        v = RequiredLabelsCheck(policy_config={'required_namespace_labels': ['owner']})
        req = make_namespace_request(labels={'team': 'platform'})
        allowed, msg = v.validate(req)
        assert allowed is False
        assert 'owner' in msg
