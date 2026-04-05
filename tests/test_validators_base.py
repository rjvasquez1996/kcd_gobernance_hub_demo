"""Unit tests for the validator registry and ENABLED_VALIDATORS filtering."""

import os
import pytest
from validators.base import get_validators, _validators


ALL_VALIDATOR_NAMES = {v.__name__ for v in _validators}


class TestGetValidatorsNoEnvVar:
    def test_returns_all_validators_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv('ENABLED_VALIDATORS', raising=False)
        result = get_validators()
        assert set(v.__name__ for v in result) == ALL_VALIDATOR_NAMES

    def test_returns_all_validators_when_env_var_is_empty_string(self, monkeypatch):
        monkeypatch.setenv('ENABLED_VALIDATORS', '')
        result = get_validators()
        assert set(v.__name__ for v in result) == ALL_VALIDATOR_NAMES


class TestGetValidatorsFiltering:
    def test_returns_only_named_validator(self, monkeypatch):
        monkeypatch.setenv('ENABLED_VALIDATORS', 'ForbidPrivilegedMode')
        result = get_validators()
        assert [v.__name__ for v in result] == ['ForbidPrivilegedMode']

    def test_returns_multiple_named_validators(self, monkeypatch):
        monkeypatch.setenv('ENABLED_VALIDATORS', 'ForbidPrivilegedMode,RequireResourceLimits')
        result = get_validators()
        names = {v.__name__ for v in result}
        assert names == {'ForbidPrivilegedMode', 'RequireResourceLimits'}

    def test_excludes_disabled_validator(self, monkeypatch):
        enabled = ','.join(ALL_VALIDATOR_NAMES - {'NoDirectNamespaceCreation'})
        monkeypatch.setenv('ENABLED_VALIDATORS', enabled)
        result = get_validators()
        names = {v.__name__ for v in result}
        assert 'NoDirectNamespaceCreation' not in names

    def test_returns_empty_list_for_unknown_name(self, monkeypatch):
        monkeypatch.setenv('ENABLED_VALIDATORS', 'NonExistentValidator')
        result = get_validators()
        assert result == []

    def test_ignores_whitespace_around_names(self, monkeypatch):
        monkeypatch.setenv('ENABLED_VALIDATORS', ' ForbidPrivilegedMode , RequireResourceLimits ')
        result = get_validators()
        names = {v.__name__ for v in result}
        assert names == {'ForbidPrivilegedMode', 'RequireResourceLimits'}

    def test_all_known_validators_are_registered(self):
        expected = {
            'ForbidPrivilegedMode',
            'RequireResourceLimits',
            'ForbidLatestTag',
            'NoDirectNamespaceCreation',
            'RequiredLabelsCheck',
            'IngressTLSRequired',
            'IngressRuleLimit',
        }
        assert expected.issubset(ALL_VALIDATOR_NAMES)
