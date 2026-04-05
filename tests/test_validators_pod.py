"""Unit tests for pod validators."""

import pytest
from validators.pod import ForbidPrivilegedMode, RequireResourceLimits, ForbidLatestTag
from conftest import load_request, make_pod_request, make_container, make_namespace_request


# ---------------------------------------------------------------------------
# ForbidPrivilegedMode
# ---------------------------------------------------------------------------

class TestForbidPrivilegedModeApplicable:
    def setup_method(self):
        self.v = ForbidPrivilegedMode()

    def test_applies_to_pod(self):
        assert self.v.is_applicable(load_request('pods/valid')) is True

    def test_applies_to_deployment(self):
        req = load_request('pods/valid')
        req['object']['kind'] = 'Deployment'
        assert self.v.is_applicable(req) is True

    def test_applies_to_statefulset(self):
        req = load_request('pods/valid')
        req['object']['kind'] = 'StatefulSet'
        assert self.v.is_applicable(req) is True

    def test_does_not_apply_to_namespace(self):
        assert self.v.is_applicable(load_request('namespaces/create')) is False

    def test_does_not_apply_to_ingress(self):
        assert self.v.is_applicable(load_request('ingresses/valid')) is False


class TestForbidPrivilegedModeValidate:
    def setup_method(self):
        self.v = ForbidPrivilegedMode()

    def test_allows_clean_pod(self):
        allowed, msg = self.v.validate(load_request('pods/valid'))
        assert allowed is True
        assert msg is None

    def test_denies_privileged_true(self):
        allowed, msg = self.v.validate(load_request('pods/privileged'))
        assert allowed is False
        assert 'privileged' in msg.lower()

    def test_denies_allow_privilege_escalation(self):
        allowed, msg = self.v.validate(load_request('pods/allow_privilege_escalation'))
        assert allowed is False
        assert 'allowPrivilegeEscalation' in msg

    def test_allows_privileged_false(self):
        req = make_pod_request([make_container(privileged=False)])
        assert self.v.validate(req) == (True, None)

    def test_allows_allow_privilege_escalation_false(self):
        req = make_pod_request([make_container(allow_privilege_escalation=False)])
        assert self.v.validate(req) == (True, None)

    def test_denies_first_bad_container_in_multi_container_pod(self):
        req = make_pod_request([
            make_container(name='good'),
            make_container(name='bad', privileged=True),
        ])
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'bad' in msg

    def test_denies_privileged_init_container(self):
        req = make_pod_request(
            containers=[make_container()],
            init_containers=[make_container(name='init', privileged=True)],
        )
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'init' in msg

    def test_allows_pod_with_no_containers(self):
        req = make_pod_request([])
        allowed, _ = self.v.validate(req)
        assert allowed is True


# ---------------------------------------------------------------------------
# RequireResourceLimits
# ---------------------------------------------------------------------------

class TestRequireResourceLimitsApplicable:
    def setup_method(self):
        self.v = RequireResourceLimits()

    def test_applies_to_pod(self):
        assert self.v.is_applicable(load_request('pods/valid')) is True

    def test_does_not_apply_to_ingress(self):
        assert self.v.is_applicable(load_request('ingresses/valid')) is False


class TestRequireResourceLimitsValidate:
    def setup_method(self):
        self.v = RequireResourceLimits()

    def test_allows_pod_with_cpu_and_memory_limits(self):
        allowed, msg = self.v.validate(load_request('pods/valid'))
        assert allowed is True

    def test_denies_pod_with_no_resources(self):
        allowed, msg = self.v.validate(load_request('pods/no_resources'))
        assert allowed is False
        assert 'cpu' in msg.lower()

    def test_denies_missing_cpu_limit(self):
        c = make_container(resources={'limits': {'memory': '256Mi'}})
        req = make_pod_request([c])
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'cpu' in msg.lower()

    def test_denies_missing_memory_limit(self):
        c = make_container(resources={'limits': {'cpu': '500m'}})
        req = make_pod_request([c])
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'memory' in msg.lower()

    def test_denies_empty_limits(self):
        c = make_container(resources={'limits': {}})
        req = make_pod_request([c])
        allowed, _ = self.v.validate(req)
        assert allowed is False

    def test_denies_init_container_missing_limits(self):
        good = make_container(resources={'limits': {'cpu': '100m', 'memory': '64Mi'}})
        bad_init = make_container(name='init')
        req = make_pod_request(containers=[good], init_containers=[bad_init])
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'init' in msg

    def test_allows_multiple_containers_all_valid(self):
        limits = {'limits': {'cpu': '100m', 'memory': '64Mi'}}
        req = make_pod_request([
            make_container(name='a', resources=limits),
            make_container(name='b', resources=limits),
        ])
        allowed, _ = self.v.validate(req)
        assert allowed is True


# ---------------------------------------------------------------------------
# ForbidLatestTag
# ---------------------------------------------------------------------------

class TestForbidLatestTagApplicable:
    def setup_method(self):
        self.v = ForbidLatestTag()

    def test_applies_to_pod(self):
        assert self.v.is_applicable(load_request('pods/valid')) is True

    def test_does_not_apply_to_namespace(self):
        assert self.v.is_applicable(load_request('namespaces/create')) is False


class TestForbidLatestTagValidate:
    def setup_method(self):
        self.v = ForbidLatestTag()

    def test_allows_explicit_version_tag(self):
        allowed, _ = self.v.validate(load_request('pods/valid'))
        assert allowed is True

    def test_denies_latest_tag(self):
        allowed, msg = self.v.validate(load_request('pods/latest_tag'))
        assert allowed is False
        assert 'latest' in msg.lower()

    def test_denies_untagged_image(self):
        allowed, _ = self.v.validate(load_request('pods/untagged_image'))
        assert allowed is False

    def test_allows_sha_digest(self):
        req = make_pod_request([make_container(image='nginx@sha256:abc123def456')])
        allowed, _ = self.v.validate(req)
        assert allowed is True

    def test_allows_semver_tag(self):
        req = make_pod_request([make_container(image='python:3.11.4-slim')])
        allowed, _ = self.v.validate(req)
        assert allowed is True

    def test_denies_init_container_with_latest(self):
        req = make_pod_request(
            containers=[make_container(image='nginx:1.21')],
            init_containers=[make_container(name='init', image='busybox:latest')],
        )
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'init' in msg

    def test_denies_second_container_with_latest(self):
        req = make_pod_request([
            make_container(name='a', image='nginx:1.21'),
            make_container(name='b', image='alpine:latest'),
        ])
        allowed, msg = self.v.validate(req)
        assert allowed is False
        assert 'b' in msg
