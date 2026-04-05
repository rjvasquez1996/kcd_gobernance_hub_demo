"""Integration tests for all API endpoints using the Flask test client."""

import json
import base64
import pytest
from conftest import load_fixture, load_request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def post_validate(client, fixture_path):
    return client.post('/api/v1/validate', json=load_fixture(fixture_path))


def post_mutate(client, fixture_path):
    return client.post('/api/v1/mutate', json=load_fixture(fixture_path))


def decode_patch(response_json):
    """Decode the base64 JSON Patch from a mutate response."""
    patch_b64 = response_json['response']['patch']
    return json.loads(base64.b64decode(patch_b64))


# ---------------------------------------------------------------------------
# POST /api/v1/validate
# ---------------------------------------------------------------------------

class TestValidateEndpoint:
    def test_valid_pod_is_allowed(self, client):
        resp = post_validate(client, 'pods/valid')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is True

    def test_uid_echoed_from_fixture(self, client):
        resp = post_validate(client, 'pods/valid')
        data = resp.get_json()
        assert data['response']['uid'] == 'test-uid-valid-pod'

    def test_response_has_admission_review_kind(self, client):
        resp = post_validate(client, 'pods/valid')
        data = resp.get_json()
        assert data['kind'] == 'AdmissionReview'
        assert data['apiVersion'] == 'admission.k8s.io/v1'

    def test_privileged_pod_is_denied(self, client):
        resp = post_validate(client, 'pods/privileged')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is False
        assert 'privileged' in data['response']['status']['message'].lower()

    def test_allow_privilege_escalation_pod_is_denied(self, client):
        resp = post_validate(client, 'pods/allow_privilege_escalation')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is False

    def test_pod_with_missing_resource_limits_is_denied(self, client):
        resp = post_validate(client, 'pods/no_resources')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is False
        assert 'limit' in data['response']['status']['message'].lower()

    def test_pod_with_latest_image_is_denied(self, client):
        resp = post_validate(client, 'pods/latest_tag')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is False
        assert 'latest' in data['response']['status']['message'].lower()

    def test_pod_with_untagged_image_is_denied(self, client):
        resp = post_validate(client, 'pods/untagged_image')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is False

    def test_valid_ingress_is_allowed(self, client):
        resp = post_validate(client, 'ingresses/valid')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is True

    def test_ingress_without_tls_is_denied(self, client):
        resp = post_validate(client, 'ingresses/no_tls')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is False
        assert 'tls' in data['response']['status']['message'].lower()

    def test_ingress_exceeding_rule_limit_is_denied(self, client):
        resp = post_validate(client, 'ingresses/too_many_rules')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is False

    def test_namespace_create_is_denied(self, client):
        resp = post_validate(client, 'namespaces/create')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is False
        assert 'namespace' in data['response']['status']['message'].lower()

    def test_namespace_update_with_required_labels_is_allowed(self, client):
        resp = post_validate(client, 'namespaces/update_with_labels')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is True

    def test_namespace_update_without_labels_is_denied(self, client):
        resp = post_validate(client, 'namespaces/update_without_labels')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is False

    def test_null_body_returns_400(self, client):
        # JSON "null" parses to Python None → falsy → app returns 400
        resp = client.post('/api/v1/validate', data=b'null', content_type='application/json')
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/mutate
# ---------------------------------------------------------------------------

class TestMutateEndpoint:
    def test_pod_without_labels_receives_governance_labels(self, client):
        resp = post_mutate(client, 'pods/no_labels')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is True
        patches = decode_patch(data)
        label_patches = [p for p in patches if 'labels' in p['path']]
        assert len(label_patches) > 0

    def test_pod_without_resources_receives_default_resources(self, client):
        resp = post_mutate(client, 'pods/no_resources')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is True
        patches = decode_patch(data)
        resource_patches = [p for p in patches if 'resources' in p['path']]
        assert len(resource_patches) > 0

    def test_pod_mutation_response_includes_json_patch_type(self, client):
        resp = post_mutate(client, 'pods/no_labels')
        data = resp.get_json()
        assert data['response'].get('patchType') == 'JSONPatch'

    def test_pod_with_all_labels_and_resources_has_no_patches(self, client):
        resp = post_mutate(client, 'pods/governance_labels_and_resources')
        data = resp.get_json()
        assert data['response']['allowed'] is True
        assert 'patch' not in data['response']

    def test_namespace_with_kubectl_annotation_receives_remove_patch(self, client):
        resp = post_mutate(client, 'namespaces/with_kubectl_annotation')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is True
        patches = decode_patch(data)
        remove_patches = [p for p in patches if p['op'] == 'remove']
        assert len(remove_patches) == 1
        assert 'last-applied-configuration' in remove_patches[0]['path'].replace('~1', '/')

    def test_namespace_without_kubectl_annotation_has_no_patches(self, client):
        resp = post_mutate(client, 'namespaces/no_annotation')
        data = resp.get_json()
        assert data['response']['allowed'] is True
        assert 'patch' not in data['response']

    def test_ingress_without_class_receives_default_class(self, client):
        resp = post_mutate(client, 'ingresses/no_ingress_class')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is True
        patches = decode_patch(data)
        class_patches = [p for p in patches if p['path'] == '/spec/ingressClassName']
        assert len(class_patches) == 1
        assert class_patches[0]['value'] == 'nginx'

    def test_ingress_with_existing_class_has_no_class_patch(self, client):
        resp = post_mutate(client, 'ingresses/with_ingress_class')
        data = resp.get_json()
        patches = decode_patch(data) if 'patch' in data['response'] else []
        class_patches = [p for p in patches if p['path'] == '/spec/ingressClassName']
        assert class_patches == []

    def test_mutate_always_returns_allowed_true(self, client):
        """Mutators never deny — they only patch."""
        resp = post_mutate(client, 'pods/latest_tag')
        assert resp.get_json()['response']['allowed'] is True

    def test_uid_echoed_from_fixture(self, client):
        resp = post_mutate(client, 'pods/no_labels')
        assert resp.get_json()['response']['uid'] == 'test-uid-no-labels-pod'

    def test_null_body_returns_400(self, client):
        resp = client.post('/api/v1/mutate', data=b'null', content_type='application/json')
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/v1/policies
# ---------------------------------------------------------------------------

class TestPoliciesEndpoint:
    def test_returns_200(self, client):
        resp = client.get('/api/v1/policies')
        assert resp.status_code == 200

    def test_response_has_validators_and_mutators(self, client):
        data = client.get('/api/v1/policies').get_json()
        assert 'validators' in data
        assert 'mutators' in data

    def test_validators_list_is_non_empty(self, client):
        data = client.get('/api/v1/policies').get_json()
        assert len(data['validators']) > 0

    def test_mutators_list_is_non_empty(self, client):
        data = client.get('/api/v1/policies').get_json()
        assert len(data['mutators']) > 0

    def test_total_counts_match_list_lengths(self, client):
        data = client.get('/api/v1/policies').get_json()
        assert data['total_validators'] == len(data['validators'])
        assert data['total_mutators'] == len(data['mutators'])

    def test_each_policy_has_name_type_description(self, client):
        data = client.get('/api/v1/policies').get_json()
        for policy in data['validators'] + data['mutators']:
            assert 'name' in policy
            assert 'type' in policy
            assert 'description' in policy

    def test_known_validators_are_present(self, client):
        data = client.get('/api/v1/policies').get_json()
        names = {v['name'] for v in data['validators']}
        assert 'ForbidPrivilegedMode' in names
        assert 'RequireResourceLimits' in names
        assert 'ForbidLatestTag' in names
        assert 'NoDirectNamespaceCreation' in names
        assert 'RequiredLabelsCheck' in names
        assert 'IngressTLSRequired' in names
        assert 'IngressRuleLimit' in names

    def test_known_mutators_are_present(self, client):
        data = client.get('/api/v1/policies').get_json()
        names = {m['name'] for m in data['mutators']}
        assert 'CommonLabelsMutator' in names
        assert 'DefaultResourcesMutator' in names
        assert 'RemoveKubectlAnnotationMutator' in names
        assert 'IngressClassDefaultMutator' in names

    def test_validator_type_field_is_validator(self, client):
        data = client.get('/api/v1/policies').get_json()
        for v in data['validators']:
            assert v['type'] == 'validator'

    def test_mutator_type_field_is_mutator(self, client):
        data = client.get('/api/v1/policies').get_json()
        for m in data['mutators']:
            assert m['type'] == 'mutator'


# ---------------------------------------------------------------------------
# GET /api/v1/health
# ---------------------------------------------------------------------------

class TestApiHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get('/api/v1/health')
        assert resp.status_code == 200

    def test_status_is_ok(self, client):
        data = client.get('/api/v1/health').get_json()
        assert data['status'] == 'ok'

    def test_includes_validator_and_mutator_counts(self, client):
        data = client.get('/api/v1/health').get_json()
        assert 'validators_loaded' in data
        assert 'mutators_loaded' in data
        assert data['validators_loaded'] > 0
        assert data['mutators_loaded'] > 0


# ---------------------------------------------------------------------------
# GET /health (root)
# ---------------------------------------------------------------------------

class TestRootHealthEndpoint:
    def test_returns_200(self, client):
        assert client.get('/health').status_code == 200

    def test_status_is_ok(self, client):
        assert client.get('/health').get_json()['status'] == 'ok'

    def test_identifies_service(self, client):
        assert 'service' in client.get('/health').get_json()


# ---------------------------------------------------------------------------
# ENABLED_VALIDATORS env var — endpoint behaviour when validators are toggled
# ---------------------------------------------------------------------------

class TestValidateWithDisabledValidators:
    """Verify that disabling a validator via ENABLED_VALIDATORS actually allows
    requests that would otherwise be denied.  These tests catch the class of
    bug where values.yaml sets a policy to false but the app ignores the env var."""

    def test_namespace_create_allowed_when_no_direct_namespace_creation_disabled(
        self, client, monkeypatch
    ):
        # All validators on except NoDirectNamespaceCreation.
        # Fixture has required labels so RequiredLabelsCheck also passes.
        # Result must be allowed=True — not just "denied for a different reason".
        enabled = ','.join([
            'ForbidPrivilegedMode', 'RequireResourceLimits', 'ForbidLatestTag',
            'RequiredLabelsCheck', 'IngressTLSRequired', 'IngressRuleLimit',
        ])
        monkeypatch.setenv('ENABLED_VALIDATORS', enabled)
        resp = post_validate(client, 'namespaces/create_with_labels')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is True

    def test_namespace_create_denied_when_no_direct_namespace_creation_enabled(
        self, client, monkeypatch
    ):
        monkeypatch.setenv('ENABLED_VALIDATORS', 'NoDirectNamespaceCreation')
        resp = post_validate(client, 'namespaces/create')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['response']['allowed'] is False
        assert 'namespace' in data['response']['status']['message'].lower()

    def test_privileged_pod_allowed_when_forbid_privileged_disabled(
        self, client, monkeypatch
    ):
        enabled = ','.join([
            'RequireResourceLimits', 'ForbidLatestTag',
            'NoDirectNamespaceCreation', 'RequiredLabelsCheck',
            'IngressTLSRequired', 'IngressRuleLimit',
        ])
        monkeypatch.setenv('ENABLED_VALIDATORS', enabled)
        resp = post_validate(client, 'pods/privileged')
        assert resp.status_code == 200
        data = resp.get_json()
        if not data['response']['allowed']:
            assert 'privileged' not in data['response']['status']['message'].lower()

    def test_all_validators_disabled_allows_any_request(self, client, monkeypatch):
        monkeypatch.setenv('ENABLED_VALIDATORS', 'NonExistentValidator')
        resp = post_validate(client, 'pods/privileged')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is True

    def test_no_env_var_preserves_default_deny_behaviour(self, client, monkeypatch):
        monkeypatch.delenv('ENABLED_VALIDATORS', raising=False)
        resp = post_validate(client, 'namespaces/create')
        assert resp.status_code == 200
        assert resp.get_json()['response']['allowed'] is False


# ---------------------------------------------------------------------------
# 404 handling
# ---------------------------------------------------------------------------

class TestNotFound:
    def test_unknown_path_returns_404(self, client):
        assert client.get('/api/v1/does-not-exist').status_code == 404

    def test_404_response_is_json(self, client):
        resp = client.get('/nonexistent')
        assert resp.status_code == 404
        assert 'error' in resp.get_json()
