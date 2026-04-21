import pytest
from openemail.core.connection_status import (
    ConnectionStatus,
    AccountValidationResult,
    get_next_status,
    can_transition,
    should_sync,
    is_savable,
)


class TestConnectionStatus:
    def test_draft_to_validating(self):
        assert can_transition(ConnectionStatus.DRAFT, ConnectionStatus.VALIDATING)

    def test_validating_to_verified(self):
        assert can_transition(ConnectionStatus.VALIDATING, ConnectionStatus.VERIFIED)

    def test_validating_to_auth_failed(self):
        assert can_transition(ConnectionStatus.VALIDATING, ConnectionStatus.AUTH_FAILED)

    def test_verified_to_sync_ready(self):
        assert can_transition(ConnectionStatus.VERIFIED, ConnectionStatus.SYNC_READY)

    def test_any_to_disabled(self):
        for s in ConnectionStatus:
            assert can_transition(s, ConnectionStatus.DISABLED)

    def test_sync_ready_only_to_disabled(self):
        for s in ConnectionStatus:
            if s != ConnectionStatus.DISABLED and s != ConnectionStatus.SYNC_READY:
                assert not can_transition(ConnectionStatus.SYNC_READY, s)

    def test_should_sync(self):
        assert should_sync(ConnectionStatus.VERIFIED)
        assert should_sync(ConnectionStatus.SYNC_READY)
        assert not should_sync(ConnectionStatus.DRAFT)
        assert not should_sync(ConnectionStatus.AUTH_FAILED)

    def test_is_savable_verified(self):
        vr = AccountValidationResult(
            inbound_success=True, test_id="t1", verification_level="auth"
        )
        assert is_savable(ConnectionStatus.VERIFIED, vr)

    def test_is_savable_rejects_precheck(self):
        vr = AccountValidationResult(
            inbound_success=True, test_id="t1", verification_level="precheck"
        )
        assert not is_savable(ConnectionStatus.VERIFIED, vr)

    def test_is_savable_rejects_no_test_id(self):
        vr = AccountValidationResult(inbound_success=True, test_id=None)
        assert not is_savable(ConnectionStatus.VERIFIED, vr)

    def test_is_savable_draft_always(self):
        assert is_savable(ConnectionStatus.DRAFT, None)

    def test_get_next_status_on_auth_error(self):
        vr = AccountValidationResult(inbound_success=False, error_message="auth failed")
        assert (
            get_next_status(ConnectionStatus.VALIDATING, vr)
            == ConnectionStatus.AUTH_FAILED
        )

    def test_get_next_status_on_success(self):
        vr = AccountValidationResult(inbound_success=True, test_id="t1")
        assert (
            get_next_status(ConnectionStatus.VALIDATING, vr)
            == ConnectionStatus.VERIFIED
        )

    def test_validation_result_to_dict_roundtrip(self):
        vr = AccountValidationResult(
            inbound_success=True,
            outbound_success=False,
            test_id="t1",
            verification_level="full",
        )
        d = vr.to_dict()
        vr2 = AccountValidationResult.from_dict(d)
        assert vr2.inbound_success == vr.inbound_success
        assert vr2.verification_level == vr.verification_level
