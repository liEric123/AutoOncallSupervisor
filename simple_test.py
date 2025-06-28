#!/usr/bin/env python3
"""
Simple Tests for AutoOncallSupervisor

Basic test suite covering core functionality.
Run with: python simple_test.py
"""

import json
import logging
from unittest.mock import patch, mock_open, MagicMock
from send_lark import send_agent_lost_notification, send_lark_card
from auto_oncall_supervisor import load_config, validate_context_fields, filter_failed_builds, process_and_retry_builds, main

# Suppress warnings for cleaner test output
logging.getLogger().setLevel(logging.CRITICAL)

def test_config_loading():
    """Test configuration loading works correctly"""
    print("Testing config loading...")

    # Test valid config
    test_config = {"buildkite_token": "test", "org_slug": "test_org"}
    with patch('os.path.exists', return_value=True):
        with patch('builtins.open', mock_open(read_data=json.dumps(test_config))):
            config = load_config()
            assert config is not None
            assert config["buildkite_token"] == "test"
            print("Config loading test passed")

def test_context_validation():
    """Test context field validation"""
    print("Testing context validation...")

    # Test with all required fields
    context = {"field1": "value1", "field2": "value2"}
    result = validate_context_fields(context, ["field1", "field2"], "test")
    assert result is True

    # Test with missing fields
    context = {"field1": "value1"}
    result = validate_context_fields(context, ["field1", "field2"], "test")
    assert result is False

    print("Context validation test passed")

def test_build_filtering():
    """Test build filtering logic"""
    print("Testing build filtering...")

    builds = [
        {"number": 1, "state": "passed"},
        {"number": 2, "state": "failed"},
        {"number": 3, "state": "failed"}
    ]
    context = {"target_branch": "main"}

    failed_builds = filter_failed_builds(builds, context)
    assert len(failed_builds) == 2
    assert all(build["state"] == "failed" for build in failed_builds)

    print("Build filtering test passed")

def test_agent_lost_detection():
    """Test Agent Lost detection and notification logic"""
    print("Testing Agent Lost detection...")

    # Mock send_lark_card to verify Lark notifications
    with patch('send_lark.send_lark_card', return_value=True) as mock_send_lark_card:
        with patch('auto_oncall_supervisor.retry_job') as mock_retry:

            # Test Scenario 1: Build WITH Agent Lost (exit_status == -1)
            failed_builds_with_agent_lost = [
                {
                    "number": 123,
                    "jobs": [
                        {"id": "job-1", "exit_status": 0},
                        {"id": "job-2", "exit_status": -1}  # Agent Lost
                    ]
                }
            ]

            context = {
                "org_slug": "test", 
                "pipeline_slug": "test",
                "lark_webhook_url": "https://webhook.test.com"
            }

            process_and_retry_builds(failed_builds_with_agent_lost, context)

            # Verify Lark notification was called for Agent Lost
            assert mock_send_lark_card.called, "Lark notification should be sent for Agent Lost"

            # Verify the webhook URL and payload structure
            call_args = mock_send_lark_card.call_args
            webhook_url = call_args[0][0]
            card_payload = call_args[0][1]

            assert webhook_url == "https://webhook.test.com"
            assert card_payload["msg_type"] == "interactive"
            assert "Agent Lost - Exit Status -1" in str(card_payload)

            # Verify retry was attempted
            mock_retry.assert_called_once()

            # Reset mocks for next test
            mock_send_lark_card.reset_mock()
            mock_retry.reset_mock()

            # Test Scenario 2: Build WITHOUT Agent Lost (normal failure)
            failed_builds_normal = [
                {
                    "number": 124,
                    "jobs": [
                        {"id": "job-1", "exit_status": 0},
                        {"id": "job-2", "exit_status": 1}  # Normal failure, not Agent Lost
                    ]
                }
            ]

            process_and_retry_builds(failed_builds_normal, context)

            # Verify NO Lark notification for normal failures
            assert not mock_send_lark_card.called, "Lark notification should NOT be sent for normal failures"

            # Verify NO retry for normal failures
            mock_retry.assert_not_called()

    print("Agent Lost detection test passed")

def test_lark_notifications():
    """Test Lark notification functionality with proper request mocking"""
    print("Testing Lark notifications...")

    # Test 1: No webhook URL configured (should not crash)
    context_no_webhook = {"build_number": "123"}
    build_url = "https://example.com/build/123"

    with patch('requests.post') as mock_requests_post:
        send_agent_lost_notification(context_no_webhook, build_url)

        # Should not make any HTTP requests when no webhook URL
        mock_requests_post.assert_not_called()

    # Test 2: With webhook URL - verify correct payload sent
    context_with_webhook = {
        "build_number": "456",
        "lark_webhook_url": "https://webhook.lark.com/test"
    }

    # Mock successful HTTP response
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch('requests.post', return_value=mock_response) as mock_requests_post:
        send_agent_lost_notification(context_with_webhook, build_url)

        # Verify HTTP request was made
        mock_requests_post.assert_called_once()

        # Check the call arguments
        call_args = mock_requests_post.call_args
        webhook_url = call_args[0][0]

        # Verify correct webhook URL
        assert webhook_url == "https://webhook.lark.com/test"

        # Verify payload structure
        assert 'json' in call_args[1]
        payload = call_args[1]['json']

        assert payload["msg_type"] == "interactive"
        assert "card" in payload
        assert "BUILD-456" in str(payload)  # Should contain build number
        assert "Agent Lost - Exit Status -1" in str(payload)  # Should contain failure reason

        # Verify timeout is set
        assert call_args[1]['timeout'] == 10

    # Test 3: Direct send_lark_card function
    test_payload = {
        "msg_type": "interactive",
        "card": {"test": "data"}
    }

    with patch('requests.post', return_value=mock_response) as mock_requests_post:
        result = send_lark_card("https://test.webhook.com", test_payload)

        # Verify function returns True for success
        assert result is True

        # Verify the exact payload was sent
        call_args = mock_requests_post.call_args
        assert call_args[0][0] == "https://test.webhook.com"
        assert call_args[1]['json'] == test_payload
        assert call_args[1]['timeout'] == 10

    print("Lark notification test passed")

def test_main_workflow():
    """Test the main application workflow"""
    print("Testing main workflow...")

    # Mock all external dependencies
    with patch('auto_oncall_supervisor.load_config') as mock_config:
        with patch('auto_oncall_supervisor.fetch_recent_builds') as mock_fetch:
            with patch('auto_oncall_supervisor.filter_failed_builds') as mock_filter:
                with patch('auto_oncall_supervisor.process_and_retry_builds') as _mock_process:

                    # Setup mocks
                    mock_config.return_value = {"buildkite_token": "test"}
                    mock_fetch.return_value = [{"state": "failed"}]
                    mock_filter.return_value = [{"state": "failed"}]

                    # Run main function
                    try:
                        main()
                        print("Main workflow test passed")
                    except (ImportError, AttributeError, KeyError, TypeError, ValueError) as e:
                        print(f"Main workflow test failed: {e}")
                        return False

    return True

def run_all_tests():
    """Run all tests"""
    print("Running AutoOncallSupervisor Simple Tests")
    print("=" * 50)

    tests = [
        test_config_loading,
        test_context_validation,
        test_build_filtering,
        test_agent_lost_detection,
        test_lark_notifications,
        test_main_workflow
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            test()
            passed += 1
        except (AssertionError, ImportError, AttributeError, KeyError, TypeError, ValueError) as e:
            print(f"Test {test.__name__} failed: {e}")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Test {test.__name__} failed with unexpected error: {e}")

    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("All tests passed!")
        return True
    print("Some tests failed")
    return False

if __name__ == "__main__":
    import sys
    sys.exit(0 if run_all_tests() else 1)
