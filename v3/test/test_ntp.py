#    (c) Copyright 2026 Hewlett Packard Enterprise Development LP
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
import unittest
from unittest.mock import MagicMock, Mock
import sys
import os

# Ensure src is on sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hpe_storage_flowkit_py.v3.src.workflows.ntp import NTPWorkflow
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.rest_client import RESTClient
from hpe_storage_flowkit_py.v3.src.validators.ntp_validator import validate_datetime_format, validate_ntp_addresses, validate_ntp_params, validate_timezone


class TestNTPWorkflow(unittest.TestCase):
    """Unit tests for NTPWorkflow class using a simple Mock REST client."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        from unittest.mock import Mock
        self.session_mgr = Mock()
        self.session_mgr.rest_client = Mock(spec=RESTClient)
        self.task_manager = Mock()
        # Default canned responses
        self.session_mgr.rest_client.get.return_value = {"uid": "system-123", "serialNumber": "1234567"}
        self.session_mgr.rest_client.post.return_value = {"status": "success"}
        self.workflow = NTPWorkflow(self.session_mgr, self.task_manager)

    def _simulate_system_response(self, uid="system-123", serial_number="1234567", name="HPE-3PAR"):
        """Helper to simulate system info response."""
        self.session_mgr.rest_client.get.return_value = {
            "uid": uid,
            "serialNumber": serial_number,
            "name": name
        }

    def _simulate_systems_members_response(self, systems=None):
        """Helper to simulate multiple systems response."""
        if systems is None:
            systems = [{"uid": "system-123", "serialNumber": "1234567", "name": "HPE-3PAR"}]
        
        members = {}
        for i, system in enumerate(systems):
            members[f"member-{i}"] = system
            
        self.session_mgr.rest_client.get.return_value = {"members": members}

    # ===================================================================
    # BUILD PAYLOAD TESTS
    # ===================================================================

    def test_build_configure_datetime_payload_with_datetime(self):
        """Test payload building with datetime parameter."""
        payload = self.workflow._build_configure_datetime_payload(
            date_time="01/15/2026 10:30:00",
            timezone="America/New_York"
        )
        
        expected = {
            "action": "CONFIGUREDATETIME",
            "parameters": {
                "dateTime": "01/15/2026 10:30:00",
                "timezone": "America/New_York"
            }
        }
        self.assertEqual(payload, expected)

    def test_build_configure_datetime_payload_with_ntp_addresses(self):
        """Test payload building with NTP addresses parameter."""
        payload = self.workflow._build_configure_datetime_payload(
            ntp_addresses=["pool.ntp.org", "time.google.com"],
            timezone="America/New_York"
        )
        
        expected = {
            "action": "CONFIGUREDATETIME",
            "parameters": {
                "ntpAddresses": ["pool.ntp.org", "time.google.com"],
                "timezone": "America/New_York"
            }
        }
        self.assertEqual(payload, expected)

    def test_build_configure_datetime_payload_with_single_ntp_string(self):
        """Test payload building with single NTP address as string."""
        payload = self.workflow._build_configure_datetime_payload(
            ntp_addresses="pool.ntp.org",
            timezone="UTC"
        )
        
        expected = {
            "action": "CONFIGUREDATETIME",
            "parameters": {
                "ntpAddresses": ["pool.ntp.org"],
                "timezone": "UTC"
            }
        }
        self.assertEqual(payload, expected)

    def test_build_configure_datetime_payload_empty(self):
        """Test payload building with no optional parameters."""
        payload = self.workflow._build_configure_datetime_payload()
        
        expected = {
            "action": "CONFIGUREDATETIME",
            "parameters": {}
        }
        self.assertEqual(payload, expected)

    # ===================================================================
    # PARAMETER VALIDATION TESTS
    # ===================================================================

    def test_validate_configure_datetime_params_success_with_datetime(self):
        """Test successful validation with datetime."""
        # Should not raise any exception
        self.workflow._validate_configure_datetime_params(
            "01/15/2026 10:30:00", None, "America/New_York"
        )

    def test_validate_configure_datetime_params_success_with_ntp(self):
        """Test successful validation with NTP addresses."""
        # Should not raise any exception
        self.workflow._validate_configure_datetime_params(
            None, ["pool.ntp.org", "time.google.com"], "UTC"
        )

    def test_validate_configure_datetime_params_missing_timezone(self):
        """Test validation failure when timezone is missing."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow._validate_configure_datetime_params(
                "01/15/2026 10:30:00", None, None
            )
        self.assertIn("timezone is required", str(context.exception))

    def test_validate_configure_datetime_params_both_datetime_and_ntp(self):
        """Test validation failure when both datetime and NTP are provided."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow._validate_configure_datetime_params(
                "01/15/2026 10:30:00", ["pool.ntp.org"], "UTC"
            )
        self.assertIn("Cannot specify both date_time and ntp_addresses", str(context.exception))

    def test_validate_configure_datetime_params_neither_datetime_nor_ntp(self):
        """Test validation failure when neither datetime nor NTP is provided."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow._validate_configure_datetime_params(None, None, "UTC")
        self.assertIn("Must specify either date_time or ntp_addresses", str(context.exception))

    def test_validate_configure_datetime_params_invalid_datetime_format(self):
        """Test validation failure with invalid datetime format."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow._validate_configure_datetime_params(
                "2026-01-15 10:30:00", None, "UTC"  # Wrong format
            )
        self.assertIn("date_time must be in format 'MM/dd/yyyy HH:mm:ss'", str(context.exception))

    def test_validate_configure_datetime_params_invalid_datetime_type(self):
        """Test validation failure with non-string datetime."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow._validate_configure_datetime_params(
                12345, None, "UTC"  # Wrong type
            )
        self.assertIn("date_time must be a string", str(context.exception))

    def test_validate_configure_datetime_params_invalid_ntp_type(self):
        """Test validation failure with invalid NTP addresses type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow._validate_configure_datetime_params(
                None, 12345, "UTC"  # Wrong type
            )
        self.assertIn("ntp_addresses must be a string or list", str(context.exception))

    def test_validate_configure_datetime_params_empty_ntp_address(self):
        """Test validation failure with empty NTP address in list."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow._validate_configure_datetime_params(
                None, ["pool.ntp.org", ""], "UTC"
            )
        self.assertIn("All NTP addresses must be non-empty strings", str(context.exception))

    # ===================================================================
    # GET SYSTEM INFO TESTS
    # ===================================================================

    def test_get_system_info_success_single_system(self):
        """Test successful system info retrieval for specific system."""
        self._simulate_system_response("system-456", "7654321", "HPE-Alletra")
        
        result = self.workflow.get_system_info("system-456")
        
        self.session_mgr.rest_client.get.assert_called_once_with("/systems/system-456")
        self.assertEqual(result["uid"], "system-456")
        self.assertEqual(result["serialNumber"], "7654321")

    def test_get_system_info_success_all_systems(self):
        """Test successful retrieval of all systems info."""
        self._simulate_systems_members_response([
            {"uid": "system-123", "serialNumber": "1234567"},
            {"uid": "system-456", "serialNumber": "7654321"}
        ])
        
        result = self.workflow.get_system_info()
        
        self.session_mgr.rest_client.get.assert_called_once_with("/systems")
        self.assertIn("members", result)
        self.assertEqual(len(result["members"]), 2)

    def test_get_system_info_system_not_found(self):
        """Test system info retrieval when system is not found."""
        # Simulate 404 error
        self.session_mgr.rest_client.get.side_effect = Exception("404 Not Found")
        
        with self.assertRaises(Exception) as context:
            self.workflow.get_system_info("nonexistent-system")
        
        self.assertIn("404", str(context.exception))

    def test_get_system_info_unauthorized(self):
        """Test system info retrieval with authentication error."""
        self.session_mgr.rest_client.get.side_effect = Exception("401 Unauthorized")
        
        with self.assertRaises(Exception) as context:
            self.workflow.get_system_info()
        
        self.assertIn("401", str(context.exception))

    def test_get_system_info_generic_error(self):
        """Test system info retrieval with generic error."""
        self.session_mgr.rest_client.get.side_effect = Exception("Internal server error")
        
        with self.assertRaises(Exception) as context:
            self.workflow.get_system_info()
        
        self.assertIn("Internal server error", str(context.exception))

    # ===================================================================
    # CONFIGURE DATETIME TESTS
    # ===================================================================

    def test_configure_datetime_success_with_datetime(self):
        """Test successful datetime configuration with specific datetime."""
        self._simulate_system_response("system-123")
        
        result = self.workflow.configure_datetime(
            date_time="01/15/2026 10:30:00",
            timezone="America/New_York"
        )
        
        # Verify get_system_info was called
        get_calls = self.session_mgr.rest_client.get.call_args_list
        self.assertTrue(any("/systems" in str(call) for call in get_calls))
        
        # Verify configure_datetime API call
        self.session_mgr.rest_client.post.assert_called_once()
        call_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(call_args[0][0], "/systems/system-123")
        
        payload = call_args[0][1]
        self.assertEqual(payload["action"], "CONFIGUREDATETIME")
        self.assertEqual(payload["parameters"]["dateTime"], "01/15/2026 10:30:00")
        self.assertEqual(payload["parameters"]["timezone"], "America/New_York")
        self.assertNotIn("ntpAddresses", payload["parameters"])

    def test_configure_datetime_success_with_ntp_addresses(self):
        """Test successful datetime configuration with NTP addresses."""
        self._simulate_system_response("system-456")
        
        result = self.workflow.configure_datetime(
            ntp_addresses=["pool.ntp.org", "time.google.com"],
            timezone="UTC"
        )
        
        # Verify configure_datetime API call
        self.session_mgr.rest_client.post.assert_called_once()
        call_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(call_args[0][0], "/systems/system-456")
        
        payload = call_args[0][1]
        self.assertEqual(payload["action"], "CONFIGUREDATETIME")
        self.assertEqual(payload["parameters"]["ntpAddresses"], ["pool.ntp.org", "time.google.com"])
        self.assertEqual(payload["parameters"]["timezone"], "UTC")
        self.assertNotIn("dateTime", payload["parameters"])

    def test_configure_datetime_success_with_members_response(self):
        """Test configure datetime with systems members response format."""
        self._simulate_systems_members_response([{"uid": "system-789"}])
        
        result = self.workflow.configure_datetime(
            date_time="01/15/2026 15:45:30",
            timezone="Europe/London"
        )
        
        # Should use the first member's UID
        call_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(call_args[0][0], "/systems/system-789")

    def test_configure_datetime_validation_error(self):
        """Test configure datetime with validation error."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                ntp_addresses=["pool.ntp.org"],
                timezone="UTC"
            )
        self.assertIn("Cannot specify both date_time and ntp_addresses", str(context.exception))

    def test_configure_datetime_system_uid_fetch_error(self):
        """Test configure datetime when system UID fetch fails."""
        self.session_mgr.rest_client.get.side_effect = Exception("Connection timeout")
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("Failed to fetch system UID", str(context.exception))

    def test_configure_datetime_invalid_system_response(self):
        """Test configure datetime with invalid system response format."""
        self.session_mgr.rest_client.get.return_value = {"invalid": "response"}
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("Could not determine system UID", str(context.exception))

    def test_configure_datetime_api_not_found_error(self):
        """Test configure datetime when API endpoint returns 404."""
        self._simulate_system_response("system-404")
        self.session_mgr.rest_client.post.side_effect = Exception("404 System not found")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("404", str(context.exception))

    def test_configure_datetime_api_bad_request_error(self):
        """Test configure datetime with API 400 error."""
        self._simulate_system_response("system-123")
        self.session_mgr.rest_client.post.side_effect = Exception("400 Bad Request")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("400", str(context.exception))

    def test_configure_datetime_api_unauthorized_error(self):
        """Test configure datetime with API 401 error."""
        self._simulate_system_response("system-123")
        self.session_mgr.rest_client.post.side_effect = Exception("401 Unauthorized")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("401", str(context.exception))

    def test_configure_datetime_api_forbidden_error(self):
        """Test configure datetime with API 403 error."""
        self._simulate_system_response("system-123")
        self.session_mgr.rest_client.post.side_effect = Exception("403 Forbidden")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("403", str(context.exception))

    def test_configure_datetime_api_generic_error(self):
        """Test configure datetime with generic API error."""
        self._simulate_system_response("system-123")
        self.session_mgr.rest_client.post.side_effect = Exception("500 Internal Server Error")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("500", str(context.exception))

    # ===================================================================
    # EDGE CASE TESTS
    # ===================================================================

    def test_configure_datetime_with_list_system_response(self):
        """Test configure datetime with list response format."""
        self.session_mgr.rest_client.get.return_value = [
            {"uid": "system-list-1", "serialNumber": "111"},
            {"uid": "system-list-2", "serialNumber": "222"}
        ]
        
        result = self.workflow.configure_datetime(
            ntp_addresses=["ntp.example.com"],
            timezone="Asia/Tokyo"
        )
        
        # Should use the first system's UID
        call_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(call_args[0][0], "/systems/system-list-1")

    def test_configure_datetime_empty_members_response(self):
        """Test configure datetime with empty members response."""
        self.session_mgr.rest_client.get.return_value = {"members": {}}
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("Could not determine system UID", str(context.exception))

    def test_configure_datetime_empty_list_response(self):
        """Test configure datetime with empty list response."""
        self.session_mgr.rest_client.get.return_value = []
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("Could not determine system UID", str(context.exception))

    def test_configure_datetime_invalid_system_response(self):
        """Test configure datetime with invalid system response."""
        self.session_mgr.rest_client.get.return_value = {"invalid": "response"}
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_datetime(
                date_time="01/15/2026 10:30:00",
                timezone="UTC"
            )
        self.assertIn("Could not determine system UID", str(context.exception))

    def test_fetch_system_uid_single_system_response(self):
        """Test _fetch_system_uid with single system response."""
        self._simulate_system_response("single-uid-123")
        
        uid = self.workflow._fetch_system_uid()
        
        self.assertEqual(uid, "single-uid-123")

    def test_fetch_system_uid_members_response(self):
        """Test _fetch_system_uid with members response."""
        self._simulate_systems_members_response([{"uid": "member-uid-456"}])
        
        uid = self.workflow._fetch_system_uid()
        
        self.assertEqual(uid, "member-uid-456")

    def test_fetch_system_uid_list_response(self):
        """Test _fetch_system_uid with list response."""
        self.session_mgr.rest_client.get.return_value = [
            {"uid": "list-uid-789", "serialNumber": "789"}
        ]
        
        uid = self.workflow._fetch_system_uid()
        
        self.assertEqual(uid, "list-uid-789")

    # ===================================================================
    # NTP VALIDATOR TESTS
    # ===================================================================

    def test_validate_ntp_addresses_valid_list(self):
        """Test NTP addresses validation with valid list."""
        validate_ntp_addresses(["pool.ntp.org", "time.google.com"])  # Should not raise

    def test_validate_ntp_addresses_valid_string(self):
        """Test NTP addresses validation with valid string."""
        validate_ntp_addresses("pool.ntp.org")  # Should not raise

    def test_validate_ntp_addresses_none(self):
        """Test NTP addresses validation with None."""
        validate_ntp_addresses(None)  # Should not raise

    def test_validate_ntp_addresses_invalid_type(self):
        """Test NTP addresses validation with invalid type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ntp_addresses(123)
        self.assertIn("must be a string or list of strings", str(context.exception))

    def test_validate_ntp_addresses_empty_string(self):
        """Test NTP addresses validation with empty string."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ntp_addresses("   ")
        self.assertIn("NTP address cannot be empty", str(context.exception))

    def test_validate_ntp_addresses_list_with_empty_string(self):
        """Test NTP addresses validation with list containing empty string."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ntp_addresses(["pool.ntp.org", "   "])
        self.assertIn("must be non-empty strings", str(context.exception))

    def test_validate_ntp_addresses_list_with_non_string(self):
        """Test NTP addresses validation with list containing non-string."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ntp_addresses(["pool.ntp.org", 123])
        self.assertIn("must be non-empty strings", str(context.exception))

    def test_validate_datetime_format_valid(self):
        """Test datetime format validation with valid format."""
        validate_datetime_format("01/15/2026 10:30:00")  # Should not raise

    def test_validate_datetime_format_none(self):
        """Test datetime format validation with None."""
        validate_datetime_format(None)  # Should not raise

    def test_validate_datetime_format_not_string(self):
        """Test datetime format validation with non-string type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_datetime_format(123)
        self.assertIn("must be a string", str(context.exception))

    def test_validate_datetime_format_invalid_format(self):
        """Test datetime format validation with invalid format."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_datetime_format("2026-01-15 10:30:00")  # Wrong format
        self.assertIn("must be in format 'MM/dd/yyyy HH:mm:ss'", str(context.exception))

    def test_validate_datetime_format_invalid_month(self):
        """Test datetime format validation with invalid month."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_datetime_format("13/15/2026 10:30:00")
        self.assertIn("must be in format 'MM/dd/yyyy HH:mm:ss'", str(context.exception))

    def test_validate_datetime_format_invalid_day(self):
        """Test datetime format validation with invalid day."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_datetime_format("01/32/2026 10:30:00")
        self.assertIn("must be in format 'MM/dd/yyyy HH:mm:ss'", str(context.exception))

    def test_validate_datetime_format_invalid_hour(self):
        """Test datetime format validation with invalid hour."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_datetime_format("01/15/2026 25:30:00")
        self.assertIn("must be in format 'MM/dd/yyyy HH:mm:ss'", str(context.exception))

    def test_validate_datetime_format_invalid_minute(self):
        """Test datetime format validation with invalid minute."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_datetime_format("01/15/2026 10:60:00")
        self.assertIn("must be in format 'MM/dd/yyyy HH:mm:ss'", str(context.exception))

    def test_validate_datetime_format_invalid_second(self):
        """Test datetime format validation with invalid second."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_datetime_format("01/15/2026 10:30:60")
        self.assertIn("must be in format 'MM/dd/yyyy HH:mm:ss'", str(context.exception))

    def test_validate_timezone_valid(self):
        """Test timezone validation with valid timezone."""
        validate_timezone("America/New_York")  # Should not raise

    def test_validate_timezone_none(self):
        """Test timezone validation with None."""
        validate_timezone(None)  # Should not raise

    def test_validate_timezone_not_string(self):
        """Test timezone validation with non-string type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_timezone(123)
        self.assertIn("must be a string", str(context.exception))

    def test_validate_timezone_empty_string(self):
        """Test timezone validation with empty string."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_timezone("   ")
        self.assertIn("timezone cannot be empty", str(context.exception))

    def test_validate_ntp_params_valid_with_datetime(self):
        """Test NTP params validation with valid datetime."""
        validate_ntp_params(
            date_time="01/15/2026 10:30:00",
            timezone="America/New_York"
        )  # Should not raise

    def test_validate_ntp_params_valid_with_ntp(self):
        """Test NTP params validation with valid NTP addresses."""
        validate_ntp_params(
            ntp_addresses=["pool.ntp.org"],
            timezone="UTC"
        )  # Should not raise

    def test_validate_ntp_params_missing_timezone(self):
        """Test NTP params validation with missing timezone."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ntp_params(date_time="01/15/2026 10:30:00")
        self.assertIn("timezone is required", str(context.exception))

    def test_validate_ntp_params_both_datetime_and_ntp(self):
        """Test NTP params validation with both datetime and NTP."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ntp_params(
                date_time="01/15/2026 10:30:00",
                ntp_addresses=["pool.ntp.org"],
                timezone="UTC"
            )
        self.assertIn("Cannot specify both", str(context.exception))

    def test_validate_ntp_params_neither_datetime_nor_ntp(self):
        """Test NTP params validation with neither datetime nor NTP."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ntp_params(timezone="UTC")
        self.assertIn("Must specify either", str(context.exception))


if __name__ == '__main__':
    unittest.main()