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

from hpe_storage_flowkit_py.v3.src.workflows.dns import DNSWorkflow
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.rest_client import RESTClient
from hpe_storage_flowkit_py.v3.src.validators.dns_validator import validate_dns_addresses, validate_dns_network_params, validate_ipv4_address, validate_ipv4_subnet_mask, validate_ipv6_address, validate_ipv6_prefix_length, validate_proxy_parameters


class TestDNSWorkflow(unittest.TestCase):
    """Unit tests for DNSWorkflow class using a simple Mock REST client."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        from unittest.mock import Mock
        self.session_mgr = Mock()
        self.session_mgr.rest_client = Mock(spec=RESTClient)
        self.task_manager = Mock()
        # Default canned responses
        self.session_mgr.rest_client.get.return_value = {"uid": "system-123", "serialNumber": "1234567"}
        self.session_mgr.rest_client.post.return_value = {"status": "success"}
        self.workflow = DNSWorkflow(self.session_mgr, self.task_manager)

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

    def test_build_configure_network_payload_dns_only(self):
        """Test payload building with DNS addresses only."""
        payload = self.workflow._build_configure_network_payload(
            dns_addresses=["8.8.8.8", "8.8.4.4"]
        )
        
        expected = {
            "action": "CONFIGURENETWORK",
            "parameters": {
                "dnsAddresses": ["8.8.8.8", "8.8.4.4"]
            }
        }
        self.assertEqual(payload, expected)

    def test_build_configure_network_payload_dns_with_ipv4(self):
        """Test payload building with DNS and IPv4 parameters."""
        payload = self.workflow._build_configure_network_payload(
            dns_addresses=["1.1.1.1", "1.0.0.1"],
            ipv4_address="192.168.1.100",
            ipv4_gateway="192.168.1.1",
            ipv4_subnet_mask="255.255.255.0"
        )
        
        expected = {
            "action": "CONFIGURENETWORK",
            "parameters": {
                "dnsAddresses": ["1.1.1.1", "1.0.0.1"],
                "ipv4Address": "192.168.1.100",
                "ipv4Gateway": "192.168.1.1",
                "ipv4SubnetMask": "255.255.255.0"
            }
        }
        self.assertEqual(payload, expected)

    def test_build_configure_network_payload_dns_with_ipv6(self):
        """Test payload building with DNS and IPv6 parameters."""
        payload = self.workflow._build_configure_network_payload(
            dns_addresses=["2001:4860:4860::8888"],
            ipv6_address="2001:db8::1",
            ipv6_gateway="2001:db8::fe",
            ipv6_prefix_len=64
        )
        
        expected = {
            "action": "CONFIGURENETWORK",
            "parameters": {
                "dnsAddresses": ["2001:4860:4860::8888"],
                "ipv6Address": "2001:db8::1",
                "ipv6Gateway": "2001:db8::fe",
                "ipv6PrefixLen": "64"
            }
        }
        self.assertEqual(payload, expected)

    def test_build_configure_network_payload_with_proxy(self):
        """Test payload building with proxy parameters."""
        proxy_params = {
            "proxyServer": "proxy.example.com",
            "proxyPort": 8080,
            "proxyProtocol": "HTTP",
            "authenticationRequired": "enabled",
            "proxyUser": "user1",
            "proxyPassword": "pass123"
        }
        
        payload = self.workflow._build_configure_network_payload(
            dns_addresses=["8.8.8.8"],
            proxy_params=proxy_params,
            commit_change=True,
            slaac_enable=False
        )
        
        expected = {
            "action": "CONFIGURENETWORK",
            "parameters": {
                "dnsAddresses": ["8.8.8.8"],
                "proxyParams": proxy_params,
                "commitChange": True,
                "slaacEnable": False
            }
        }
        self.assertEqual(payload, expected)

    def test_build_configure_network_payload_full(self):
        """Test payload building with all parameters."""
        proxy_params = {"proxyServer": "proxy.test.com", "proxyPort": 3128}
        
        payload = self.workflow._build_configure_network_payload(
            dns_addresses=["8.8.8.8", "8.8.4.4"],
            ipv4_address="10.0.0.100",
            ipv4_gateway="10.0.0.1",
            ipv4_subnet_mask="255.255.255.0",
            ipv6_address="2001:db8::100",
            ipv6_gateway="2001:db8::1",
            ipv6_prefix_len=64,
            proxy_params=proxy_params,
            commit_change=True,
            slaac_enable=True
        )
        
        self.assertEqual(payload["action"], "CONFIGURENETWORK")
        self.assertEqual(payload["parameters"]["dnsAddresses"], ["8.8.8.8", "8.8.4.4"])
        self.assertEqual(payload["parameters"]["ipv4Address"], "10.0.0.100")
        self.assertEqual(payload["parameters"]["ipv6Address"], "2001:db8::100")
        self.assertEqual(payload["parameters"]["proxyParams"], proxy_params)
        self.assertTrue(payload["parameters"]["commitChange"])
        self.assertTrue(payload["parameters"]["slaacEnable"])

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

    def test_configure_network_success_dns_only_with_ipv4(self):
        """Test successful network configuration with DNS and minimal IPv4."""
        self._simulate_system_response("system-123")
        
        result = self.workflow.configure_network(
            dns_addresses=["8.8.8.8", "8.8.4.4"],
            ipv4_address="192.168.1.100",
            ipv4_gateway="192.168.1.1",
            ipv4_subnet_mask="255.255.255.0"
        )
        
        # Verify get_system_info was called for UID
        get_calls = self.session_mgr.rest_client.get.call_args_list
        self.assertTrue(any("/systems" in str(call) for call in get_calls))
        
        # Verify configure network API call
        self.session_mgr.rest_client.post.assert_called_once()
        call_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(call_args[0][0], "/systems/system-123")
        
        payload = call_args[0][1]
        self.assertEqual(payload["action"], "CONFIGURENETWORK")
        self.assertEqual(payload["parameters"]["dnsAddresses"], ["8.8.8.8", "8.8.4.4"])
        self.assertEqual(payload["parameters"]["ipv4Address"], "192.168.1.100")

    def test_configure_network_success_dns_with_ipv6(self):
        """Test successful network configuration with DNS and IPv6."""
        self._simulate_system_response("system-456")
        
        result = self.workflow.configure_network(
            dns_addresses=["2001:4860:4860::8888"],
            ipv6_address="2001:db8::1",
            ipv6_gateway="2001:db8::fe",
            ipv6_prefix_len=64
        )
        
        # Verify configure network API call
        self.session_mgr.rest_client.post.assert_called_once()
        call_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(call_args[0][0], "/systems/system-456")
        
        payload = call_args[0][1]
        self.assertEqual(payload["action"], "CONFIGURENETWORK")
        self.assertEqual(payload["parameters"]["dnsAddresses"], ["2001:4860:4860::8888"])
        self.assertEqual(payload["parameters"]["ipv6Address"], "2001:db8::1")

    def test_configure_network_success_with_members_response(self):
        """Test configure network with systems members response format."""
        self._simulate_systems_members_response([{"uid": "system-789"}])
        
        result = self.workflow.configure_network(
            dns_addresses=["1.1.1.1"],
            ipv4_address="10.0.0.50",
            ipv4_gateway="10.0.0.1",
            ipv4_subnet_mask="255.255.255.0"
        )
        
        # Should use the first member's UID
        call_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(call_args[0][0], "/systems/system-789")

    def test_configure_network_validation_error_no_ip(self):
        """Test configure network with validation error - no IP addresses."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"]
                # Missing both IPv4 and IPv6
            )
        self.assertIn("At least IPv4 or IPv6 address must be provided", str(context.exception))

    def test_configure_network_system_uid_fetch_error(self):
        """Test configure network when system UID fetch fails."""
        self.session_mgr.rest_client.get.side_effect = Exception("Connection timeout")
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("Failed to fetch system UID", str(context.exception))

    def test_configure_network_api_not_found_error(self):
        """Test configure network when API endpoint returns 404."""
        self._simulate_system_response("system-404")
        self.session_mgr.rest_client.post.side_effect = Exception("404 System not found")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("404", str(context.exception))

    def test_configure_network_api_bad_request_error(self):
        """Test configure network with API 400 error."""
        self._simulate_system_response("system-123")
        self.session_mgr.rest_client.post.side_effect = Exception("400 Bad Request")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("400", str(context.exception))

    def test_configure_network_api_unauthorized_error(self):
        """Test configure network with API 401 error."""
        self._simulate_system_response("system-123")
        self.session_mgr.rest_client.post.side_effect = Exception("401 Unauthorized")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("401", str(context.exception))

    def test_configure_network_api_forbidden_error(self):
        """Test configure network with API 403 error."""
        self._simulate_system_response("system-123")
        self.session_mgr.rest_client.post.side_effect = Exception("403 Forbidden")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("403", str(context.exception))

    def test_configure_network_api_generic_error(self):
        """Test configure network with generic API error."""
        self._simulate_system_response("system-123")
        self.session_mgr.rest_client.post.side_effect = Exception("500 Internal Server Error")
        
        with self.assertRaises(Exception) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("500", str(context.exception))

    def test_configure_network_with_list_system_response(self):
        """Test configure network with list response format."""
        self.session_mgr.rest_client.get.return_value = [
            {"uid": "system-list-1", "serialNumber": "111"},
            {"uid": "system-list-2", "serialNumber": "222"}
        ]
        
        result = self.workflow.configure_network(
            dns_addresses=["9.9.9.9"],
            ipv4_address="172.16.1.10",
            ipv4_gateway="172.16.1.1",
            ipv4_subnet_mask="255.255.255.0"
        )
        
        # Should use the first system's UID
        call_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(call_args[0][0], "/systems/system-list-1")

    def test_configure_network_empty_members_response(self):
        """Test configure network with empty members response."""
        self.session_mgr.rest_client.get.return_value = {"members": {}}
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("Could not determine system UID", str(context.exception))

    def test_configure_network_empty_list_response(self):
        """Test configure network with empty list response."""
        self.session_mgr.rest_client.get.return_value = []
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("Could not determine system UID", str(context.exception))

    def test_configure_network_invalid_system_response(self):
        """Test configure network with invalid system response format."""
        self.session_mgr.rest_client.get.return_value = {"invalid": "response"}
        
        with self.assertRaises(exceptions.HPEStorageException) as context:
            self.workflow.configure_network(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0"
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
    # DNS VALIDATOR TESTS
    # ===================================================================

    def test_validate_ipv4_address_valid(self):
        """Test IPv4 address validation with valid address."""
        validate_ipv4_address("192.168.1.1")  # Should not raise

    def test_validate_ipv4_address_invalid_format(self):
        """Test IPv4 address validation with invalid format."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv4_address("999.999.999.999")
        self.assertIn("Invalid IPv4 address format", str(context.exception))

    def test_validate_ipv4_address_not_string(self):
        """Test IPv4 address validation with non-string type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv4_address(123)
        self.assertIn("must be a string", str(context.exception))

    def test_validate_ipv4_address_none(self):
        """Test IPv4 address validation with None."""
        validate_ipv4_address(None)  # Should not raise

    def test_validate_ipv6_address_valid(self):
        """Test IPv6 address validation with valid address."""
        validate_ipv6_address("2001:db8::1")  # Should not raise

    def test_validate_ipv6_address_invalid_format(self):
        """Test IPv6 address validation with invalid format."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv6_address("invalid:ipv6")
        self.assertIn("Invalid IPv6 address format", str(context.exception))

    def test_validate_ipv6_address_not_string(self):
        """Test IPv6 address validation with non-string type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv6_address(123)
        self.assertIn("must be a string", str(context.exception))

    def test_validate_ipv6_address_none(self):
        """Test IPv6 address validation with None."""
        validate_ipv6_address(None)  # Should not raise

    def test_validate_ipv4_subnet_mask_valid(self):
        """Test subnet mask validation with valid mask."""
        validate_ipv4_subnet_mask("255.255.255.0")  # Should not raise

    def test_validate_ipv4_subnet_mask_invalid_pattern(self):
        """Test subnet mask validation with invalid pattern."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv4_subnet_mask("255.255.0.255")  # Invalid pattern: 0 followed by 1
        self.assertIn("Invalid subnet mask format", str(context.exception))

    def test_validate_ipv4_subnet_mask_invalid_format(self):
        """Test subnet mask validation with invalid format."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv4_subnet_mask("999.999.999.999")
        self.assertIn("Invalid IPv4 subnet mask format", str(context.exception))

    def test_validate_ipv4_subnet_mask_not_string(self):
        """Test subnet mask validation with non-string type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv4_subnet_mask(123)
        self.assertIn("must be a string", str(context.exception))

    def test_validate_ipv4_subnet_mask_none(self):
        """Test subnet mask validation with None."""
        validate_ipv4_subnet_mask(None)  # Should not raise

    def test_validate_ipv6_prefix_length_valid(self):
        """Test IPv6 prefix length validation with valid value."""
        validate_ipv6_prefix_length(64)  # Should not raise
        validate_ipv6_prefix_length("64")  # Should not raise

    def test_validate_ipv6_prefix_length_out_of_range_high(self):
        """Test IPv6 prefix length validation with value too high."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv6_prefix_length(129)
        self.assertIn("must be between 0 and 128", str(context.exception))

    def test_validate_ipv6_prefix_length_out_of_range_low(self):
        """Test IPv6 prefix length validation with negative value."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv6_prefix_length(-1)
        self.assertIn("must be between 0 and 128", str(context.exception))

    def test_validate_ipv6_prefix_length_invalid_type(self):
        """Test IPv6 prefix length validation with invalid type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_ipv6_prefix_length("invalid")
        self.assertIn("must be a valid integer", str(context.exception))

    def test_validate_ipv6_prefix_length_none(self):
        """Test IPv6 prefix length validation with None."""
        validate_ipv6_prefix_length(None)  # Should not raise

    def test_validate_dns_addresses_valid(self):
        """Test DNS addresses validation with valid list."""
        validate_dns_addresses(["8.8.8.8", "8.8.4.4"])  # Should not raise

    def test_validate_dns_addresses_none(self):
        """Test DNS addresses validation with None."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_addresses(None)
        self.assertIn("DNS addresses are required", str(context.exception))

    def test_validate_dns_addresses_not_list(self):
        """Test DNS addresses validation with non-list type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_addresses("8.8.8.8")
        self.assertIn("must be a list", str(context.exception))

    def test_validate_dns_addresses_empty_list(self):
        """Test DNS addresses validation with empty list."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_addresses([])
        self.assertIn("DNS addresses are required", str(context.exception))

    def test_validate_dns_addresses_too_many(self):
        """Test DNS addresses validation with more than 3 addresses."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_addresses(["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"])
        self.assertIn("Maximum of 3 DNS addresses", str(context.exception))

    def test_validate_dns_addresses_non_string_element(self):
        """Test DNS addresses validation with non-string element."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_addresses(["8.8.8.8", 123])
        self.assertIn("must be non-empty strings", str(context.exception))

    def test_validate_dns_addresses_empty_string(self):
        """Test DNS addresses validation with empty string element."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_addresses(["8.8.8.8", "   "])
        self.assertIn("must be non-empty strings", str(context.exception))

    def test_validate_proxy_parameters_valid_http(self):
        """Test proxy parameters validation with valid HTTP proxy."""
        proxy = {
            "proxyServer": "proxy.example.com",
            "proxyPort": 8080,
            "proxyProtocol": "HTTP",
            "authenticationRequired": "enabled",
            "proxyUser": "user1",
            "proxyPassword": "pass123"
        }
        validate_proxy_parameters(proxy)  # Should not raise

    def test_validate_proxy_parameters_valid_ntlm(self):
        """Test proxy parameters validation with valid NTLM proxy."""
        proxy = {
            "proxyServer": "proxy.example.com",
            "proxyPort": 8080,
            "proxyProtocol": "NTLM",
            "authenticationRequired": "enabled",
            "proxyUser": "user1",
            "proxyPassword": "pass123",
            "proxyUserDomain": "DOMAIN"
        }
        validate_proxy_parameters(proxy)  # Should not raise

    def test_validate_proxy_parameters_none(self):
        """Test proxy parameters validation with None."""
        validate_proxy_parameters(None)  # Should not raise

    def test_validate_proxy_parameters_not_dict(self):
        """Test proxy parameters validation with non-dict type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters("not-a-dict")
        self.assertIn("must be a dictionary", str(context.exception))

    def test_validate_proxy_parameters_invalid_auth_required(self):
        """Test proxy parameters validation with invalid authenticationRequired."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({"authenticationRequired": "invalid"})
        self.assertIn("must be 'enabled' or 'disabled'", str(context.exception))

    def test_validate_proxy_parameters_invalid_port_high(self):
        """Test proxy parameters validation with port too high."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({"proxyPort": 99999})
        self.assertIn("must be between 1 and 65535", str(context.exception))

    def test_validate_proxy_parameters_invalid_port_low(self):
        """Test proxy parameters validation with port too low."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({"proxyPort": 0})
        self.assertIn("must be between 1 and 65535", str(context.exception))

    def test_validate_proxy_parameters_invalid_port_type(self):
        """Test proxy parameters validation with invalid port type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({"proxyPort": "not-a-number"})
        self.assertIn("must be a valid integer", str(context.exception))

    def test_validate_proxy_parameters_invalid_protocol(self):
        """Test proxy parameters validation with invalid protocol."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({"proxyProtocol": "FTP"})
        self.assertIn("must be 'HTTP' or 'NTLM'", str(context.exception))

    def test_validate_proxy_parameters_invalid_server_type(self):
        """Test proxy parameters validation with invalid server type."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({"proxyServer": 123})
        self.assertIn("must be a string", str(context.exception))

    def test_validate_proxy_parameters_auth_enabled_no_user(self):
        """Test proxy parameters validation with auth enabled but no user."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({
                "authenticationRequired": "enabled",
                "proxyPassword": "pass"
            })
        self.assertIn("proxyUser is required", str(context.exception))

    def test_validate_proxy_parameters_auth_enabled_no_password(self):
        """Test proxy parameters validation with auth enabled but no password."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({
                "authenticationRequired": "enabled",
                "proxyUser": "user"
            })
        self.assertIn("proxyPassword is required", str(context.exception))

    def test_validate_proxy_parameters_ntlm_no_domain(self):
        """Test proxy parameters validation with NTLM but no domain."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({
                "authenticationRequired": "enabled",
                "proxyProtocol": "NTLM",
                "proxyUser": "user",
                "proxyPassword": "pass"
            })
        self.assertIn("proxyUserDomain is required for NTLM", str(context.exception))

    def test_validate_proxy_parameters_http_with_domain(self):
        """Test proxy parameters validation with HTTP and domain."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_proxy_parameters({
                "authenticationRequired": "enabled",
                "proxyProtocol": "HTTP",
                "proxyUser": "user",
                "proxyPassword": "pass",
                "proxyUserDomain": "DOMAIN"
            })
        self.assertIn("must not be provided for HTTP proxy", str(context.exception))

    def test_validate_dns_network_params_no_ip(self):
        """Test DNS network params validation with no IP addresses."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_network_params(dns_addresses=["8.8.8.8"])
        self.assertIn("At least IPv4 or IPv6 address must be provided", str(context.exception))

    def test_validate_dns_network_params_ipv4_no_gateway(self):
        """Test DNS network params validation with IPv4 but no gateway."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_network_params(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_subnet_mask="255.255.255.0"
            )
        self.assertIn("IPv4 gateway is required", str(context.exception))

    def test_validate_dns_network_params_ipv4_no_subnet(self):
        """Test DNS network params validation with IPv4 but no subnet mask."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_network_params(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1"
            )
        self.assertIn("IPv4 subnet mask is required", str(context.exception))

    def test_validate_dns_network_params_ipv6_no_gateway(self):
        """Test DNS network params validation with IPv6 but no gateway."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_network_params(
                dns_addresses=["8.8.8.8"],
                ipv6_address="2001:db8::1",
                ipv6_prefix_len=64
            )
        self.assertIn("IPv6 gateway is required", str(context.exception))

    def test_validate_dns_network_params_ipv6_no_prefix(self):
        """Test DNS network params validation with IPv6 but no prefix length."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_network_params(
                dns_addresses=["8.8.8.8"],
                ipv6_address="2001:db8::1",
                ipv6_gateway="2001:db8::fe"
            )
        self.assertIn("IPv6 prefix length is required", str(context.exception))

    def test_validate_dns_network_params_invalid_commit_change(self):
        """Test DNS network params validation with invalid commitChange."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_network_params(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0",
                commit_change="invalid"
            )
        self.assertIn("commitChange must be a boolean", str(context.exception))

    def test_validate_dns_network_params_invalid_slaac_enable(self):
        """Test DNS network params validation with invalid slaacEnable."""
        with self.assertRaises(exceptions.InvalidInput) as context:
            validate_dns_network_params(
                dns_addresses=["8.8.8.8"],
                ipv4_address="192.168.1.100",
                ipv4_gateway="192.168.1.1",
                ipv4_subnet_mask="255.255.255.0",
                slaac_enable="invalid"
            )
        self.assertIn("slaacEnable must be a boolean", str(context.exception))

    def test_build_payload_proxy_auth_disabled(self):
        """Test payload building removes auth fields when auth is disabled."""
        proxy_params = {
            "proxyServer": "proxy.example.com",
            "proxyPort": 8080,
            "authenticationRequired": "disabled",
            "proxyUser": "should_be_removed",
            "proxyPassword": "should_be_removed",
            "proxyUserDomain": "should_be_removed"
        }
        
        payload = self.workflow._build_configure_network_payload(
            dns_addresses=["8.8.8.8"],
            proxy_params=proxy_params
        )
        
        # Auth fields should be removed
        proxy_in_payload = payload["parameters"]["proxyParams"]
        self.assertNotIn("proxyUser", proxy_in_payload)
        self.assertNotIn("proxyPassword", proxy_in_payload)
        self.assertNotIn("proxyUserDomain", proxy_in_payload)


if __name__ == '__main__':
    unittest.main()