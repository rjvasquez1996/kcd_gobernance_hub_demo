"""Unit tests for ingress validators."""

import pytest
from validators.ingress import IngressTLSRequired, IngressRuleLimit
from conftest import load_request, make_ingress_request, make_pod_request, make_container


# ---------------------------------------------------------------------------
# IngressTLSRequired
# ---------------------------------------------------------------------------

class TestIngressTLSRequiredApplicable:
    def setup_method(self):
        self.v = IngressTLSRequired()

    def test_applies_to_ingress(self):
        assert self.v.is_applicable(load_request('ingresses/valid')) is True

    def test_does_not_apply_to_pod(self):
        assert self.v.is_applicable(load_request('pods/valid')) is False

    def test_does_not_apply_to_namespace(self):
        assert self.v.is_applicable(load_request('namespaces/create')) is False


class TestIngressTLSRequiredValidate:
    def setup_method(self):
        self.v = IngressTLSRequired()

    def test_allows_ingress_with_tls(self):
        allowed, _ = self.v.validate(load_request('ingresses/valid'))
        assert allowed is True

    def test_denies_ingress_without_tls(self):
        allowed, msg = self.v.validate(load_request('ingresses/no_tls'))
        assert allowed is False
        assert 'tls' in msg.lower()

    def test_allows_multiple_tls_entries(self):
        req = make_ingress_request(tls=[
            {'hosts': ['a.com'], 'secretName': 'a-tls'},
            {'hosts': ['b.com'], 'secretName': 'b-tls'},
        ])
        allowed, _ = self.v.validate(req)
        assert allowed is True

    def test_denies_empty_tls_list(self):
        req = make_ingress_request(tls=[])
        allowed, _ = self.v.validate(req)
        assert allowed is False


# ---------------------------------------------------------------------------
# IngressRuleLimit
# ---------------------------------------------------------------------------

class TestIngressRuleLimitApplicable:
    def setup_method(self):
        self.v = IngressRuleLimit()

    def test_applies_to_ingress(self):
        assert self.v.is_applicable(load_request('ingresses/valid')) is True

    def test_does_not_apply_to_pod(self):
        assert self.v.is_applicable(load_request('pods/valid')) is False


class TestIngressRuleLimitValidate:
    def setup_method(self):
        self.v = IngressRuleLimit()

    def _make_rules(self, count):
        return [{'host': f'host-{i}.example.com'} for i in range(count)]

    def test_allows_ingress_within_default_limit(self):
        allowed, _ = self.v.validate(load_request('ingresses/valid'))
        assert allowed is True

    def test_denies_ingress_over_default_limit(self):
        allowed, msg = self.v.validate(load_request('ingresses/too_many_rules'))
        assert allowed is False
        assert '6' in msg
        assert '5' in msg

    def test_allows_zero_rules(self):
        req = make_ingress_request(rules=[])
        allowed, _ = self.v.validate(req)
        assert allowed is True

    def test_allows_exactly_at_default_limit(self):
        req = make_ingress_request(rules=self._make_rules(5))
        allowed, _ = self.v.validate(req)
        assert allowed is True

    def test_denies_over_default_limit(self):
        req = make_ingress_request(rules=self._make_rules(6))
        allowed, msg = self.v.validate(req)
        assert allowed is False

    def test_custom_max_rules_allows_within_limit(self):
        v = IngressRuleLimit(policy_config={'max_ingress_rules': 2})
        req = make_ingress_request(rules=self._make_rules(2))
        allowed, _ = v.validate(req)
        assert allowed is True

    def test_custom_max_rules_denies_over_limit(self):
        v = IngressRuleLimit(policy_config={'max_ingress_rules': 2})
        req = make_ingress_request(rules=self._make_rules(3))
        allowed, msg = v.validate(req)
        assert allowed is False
        assert '2' in msg
