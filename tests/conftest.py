"""Shared pytest fixtures, admission review factory helpers, and fixture loaders."""

import json
import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')

# The Flask app import triggers registration of all validators and mutators
from app import app as flask_app

_UNSET = object()  # sentinel for "not provided" in factory functions


# ---------------------------------------------------------------------------
# Fixture file loaders
# ---------------------------------------------------------------------------

def load_fixture(path):
    """Load a full AdmissionReview from a JSON fixture file.

    Args:
        path: relative path inside tests/fixtures/ without the .json extension
              e.g. 'pods/valid', 'namespaces/create', 'ingresses/no_tls'

    Returns:
        dict: full AdmissionReview object (apiVersion, kind, request)
    """
    with open(os.path.join(FIXTURES_DIR, f'{path}.json')) as f:
        return json.load(f)


def load_request(path):
    """Load just the request portion of an AdmissionReview fixture.

    Use this in validator/mutator unit tests that operate on the inner
    request dict directly (review.get('request', {})).
    """
    return load_fixture(path)['request']


# ---------------------------------------------------------------------------
# Flask test client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Programmatic admission review factories
# Used by unit tests that need parametric variations not covered by fixtures.
# ---------------------------------------------------------------------------

def make_container(name='app', image='nginx:1.21.6', privileged=None,
                   allow_privilege_escalation=None, resources=None):
    """Build a container dict for use inside pod specs."""
    container = {'name': name, 'image': image}
    sec_ctx = {}
    if privileged is not None:
        sec_ctx['privileged'] = privileged
    if allow_privilege_escalation is not None:
        sec_ctx['allowPrivilegeEscalation'] = allow_privilege_escalation
    if sec_ctx:
        container['securityContext'] = sec_ctx
    if resources is not None:
        container['resources'] = resources
    return container


def make_pod_request(containers, operation='CREATE', name='test-pod',
                     namespace='default', labels=None, annotations=None,
                     init_containers=None):
    """Build a pod AdmissionReview request dict (inner request, not full envelope)."""
    obj = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {'name': name, 'namespace': namespace},
        'spec': {'containers': containers},
    }
    if labels is not None:
        obj['metadata']['labels'] = labels
    if annotations is not None:
        obj['metadata']['annotations'] = annotations
    if init_containers:
        obj['spec']['initContainers'] = init_containers
    return {'uid': 'test-uid-abc', 'operation': operation, 'object': obj}


def make_namespace_request(name='test-ns', operation='CREATE',
                           labels=None, annotations=None):
    """Build a namespace AdmissionReview request dict."""
    obj = {
        'apiVersion': 'v1',
        'kind': 'Namespace',
        'metadata': {'name': name},
    }
    if labels is not None:
        obj['metadata']['labels'] = labels
    if annotations is not None:
        obj['metadata']['annotations'] = annotations
    return {'uid': 'test-uid-abc', 'operation': operation, 'object': obj}


def make_ingress_request(tls=None, rules=None, ingress_class_name=_UNSET,
                         name='test-ingress', namespace='default', operation='CREATE'):
    """Build an ingress AdmissionReview request dict."""
    spec = {}
    if tls is not None:
        spec['tls'] = tls
    if rules is not None:
        spec['rules'] = rules
    if ingress_class_name is not _UNSET:
        spec['ingressClassName'] = ingress_class_name
    obj = {
        'apiVersion': 'networking.k8s.io/v1',
        'kind': 'Ingress',
        'metadata': {'name': name, 'namespace': namespace},
        'spec': spec,
    }
    return {'uid': 'test-uid-abc', 'operation': operation, 'object': obj}
