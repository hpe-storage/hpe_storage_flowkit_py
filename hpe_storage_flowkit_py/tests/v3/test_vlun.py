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

from hpe_storage_flowkit_py.v3.src.workflows.vlun import VLunWorkflow
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.rest_client import RESTClient


class TestVLunWorkflow(unittest.TestCase):
	"""Unit tests for VLunWorkflow class using a simple Mock REST client.
	
	Tests cover all methods with positive and negative scenarios including edge cases.
	"""

	def setUp(self):
		"""Set up test fixtures before each test method."""
		self.session_mgr = Mock()
		self.session_mgr.rest_client = Mock(spec=RESTClient)
		# Default canned responses (no state tracking)
		self.session_mgr.rest_client.get.return_value = {"members": {}}
		self.session_mgr.rest_client.post.return_value = {"status": "created"}
		self.session_mgr.rest_client.delete.return_value = {"status": "deleted"}
		self.workflow = VLunWorkflow(self.session_mgr)

	def _simulate_exists(self, volname, hostname, lun, members=None):
		"""Helper to simulate existing VLUNs."""
		members = members or []
		self.session_mgr.rest_client.get.return_value = [
			{
				"uid": "d8fa72eae2e4ff2df7e750ded911f0ec",
				"lun": lun,
				"volumeName": volname,
				"hostName": hostname,
				"portPos": {"node": 0, "slot": 4, "port": 1}
			},
			{
				"uid": "bd8a0990c5b1393d54737ae5ac9592be",
				"lun": lun,
				"volumeName": volname,
				"hostName": hostname,
				"portPos": {"node": 1, "slot": 4, "port": 1}
			},
			{
				"uid": "94706a930d3c2e5d12266fd5cffaa411",
				"lun": lun,
				"volumeName": volname,
				"hostName": hostname,
			}
		]

	# ===================================================================
	# CREATE VLUN TESTS
	# ===================================================================
	
	def test_create_vlun_success(self):
		"""Test successful vlun creation with mandatory params."""
		result = self.workflow.create_vlun("vol1", "host1")
		self.session_mgr.rest_client.post.assert_called_once()
		call_args = self.session_mgr.rest_client.post.call_args
		self.assertEqual(call_args[0][0], "/vluns")
		payload = call_args[0][1]
		self.assertEqual(payload["volumeName"], "vol1")
		self.assertEqual(payload["hostName"], "host1")

	def test_create_vlun_with_optional_params(self):
		"""Test vlun creation with optional parameters."""
		result = self.workflow.create_vlun("vol2", "host2", autoLun=True, lun=5)
		self.session_mgr.rest_client.post.assert_called_once()
		call_args = self.session_mgr.rest_client.post.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["volumeName"], "vol2")
		self.assertEqual(payload["hostName"], "host2")
		self.assertEqual(payload["autoLun"], True)
		self.assertEqual(payload["lun"], 5)

	def test_create_vlun_with_all_optional_params(self):
		"""Test vlun creation with all optional parameters."""
		result = self.workflow.create_vlun(
			"vol3", "host3",
			autoLun=False,
			lun=10,
			maxAutoLun=20,
			noVcn=True,
			overrideLowerPriority=False,
			portPos="1:2:3"
		)
		call_args = self.session_mgr.rest_client.post.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["autoLun"], False)
		self.assertEqual(payload["lun"], 10)
		self.assertEqual(payload["maxAutoLun"], 20)
		self.assertEqual(payload["noVcn"], True)
		self.assertEqual(payload["overrideLowerPriority"], False)
		self.assertEqual(payload["portPos"], "1:2:3")
	
	def test_create_vlun_invalid_volname_empty(self):
		"""Test vlun creation with empty volume name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("", "host")
		self.assertIn("non-empty string", str(context.exception))

	def test_create_vlun_invalid_volname_whitespace(self):
		"""Test vlun creation with whitespace-only volume name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("   ", "host")
		self.assertIn("non-empty string", str(context.exception))

	def test_create_vlun_invalid_hostname_empty(self):
		"""Test vlun creation with empty hostname."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol", "")
		self.assertIn("non-empty string", str(context.exception))

	def test_create_vlun_invalid_hostname_whitespace(self):
		"""Test vlun creation with whitespace-only hostname."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol", "   ")
		self.assertIn("non-empty string", str(context.exception))

	def test_create_vlun_invalid_volname_non_string(self):
		"""Test vlun creation with non-string volume name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun(123, "host")
		self.assertIn("non-empty string", str(context.exception))

	def test_create_vlun_invalid_hostname_non_string(self):
		"""Test vlun creation with non-string hostname."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol", 456)
		self.assertIn("non-empty string", str(context.exception))
	
	def test_create_vlun_invalid_lun_type(self):
		"""Test vlun creation with invalid lun type."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol3", "host3", lun="1")
		self.assertIn("'lun' must be an integer", str(context.exception))

	def test_create_vlun_invalid_maxAutoLun_type(self):
		"""Test vlun creation with invalid maxAutoLun type."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol4", "host4", maxAutoLun="20")
		self.assertIn("'maxAutoLun' must be an integer", str(context.exception))

	def test_create_vlun_invalid_autoLun_type(self):
		"""Test vlun creation with invalid autoLun type."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol5", "host5", autoLun="true")
		self.assertIn("'autoLun' must be a boolean", str(context.exception))

	def test_create_vlun_invalid_noVcn_type(self):
		"""Test vlun creation with invalid noVcn type."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol6", "host6", noVcn="false")
		self.assertIn("'noVcn' must be a boolean", str(context.exception))

	def test_create_vlun_invalid_overrideLowerPriority_type(self):
		"""Test vlun creation with invalid overrideLowerPriority type."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol7", "host7", overrideLowerPriority="yes")
		self.assertIn("'overrideLowerPriority' must be a boolean", str(context.exception))

	def test_create_vlun_invalid_portPos_type(self):
		"""Test vlun creation with invalid portPos type."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol8", "host8", portPos=123)
		self.assertIn("'portPos' must be a string", str(context.exception))

	def test_create_vlun_invalid_portPos_format(self):
		"""Test vlun creation with invalid portPos format."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol9", "host9", portPos="1:2")  # Missing third part
		self.assertIn("must be in the format 'N:S:P'", str(context.exception))

	def test_create_vlun_invalid_portPos_non_numeric(self):
		"""Test vlun creation with non-numeric portPos values."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol10", "host10", portPos="a:b:c")
		self.assertIn("must be in the format 'N:S:P'", str(context.exception))
	
	def test_create_vlun_invalid_unsupported_param(self):
		"""Test vlun creation with unsupported parameter."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_vlun("vol4", "host4", unsupported_param="value")
		self.assertIn("Invalid optional parameter: unsupported_param", str(context.exception))

	def test_create_vlun_none_optional_params_filtered(self):
		"""Test that None optional parameters are filtered out."""
		result = self.workflow.create_vlun("vol11", "host11", lun=None, autoLun=None)
		call_args = self.session_mgr.rest_client.post.call_args
		payload = call_args[0][1]
		# None values should be filtered out
		self.assertNotIn("lun", payload)
		self.assertNotIn("autoLun", payload)

	def test_create_vlun_exception_propagated(self):
		"""Test that exceptions during creation are propagated."""
		self.session_mgr.rest_client.post.side_effect = Exception("Create failed")
		with self.assertRaises(Exception) as context:
			self.workflow.create_vlun("vol12", "host12")
		self.assertIn("Create failed", str(context.exception))

	# ===================================================================
	# DELETE VLUN TESTS
	# ===================================================================
	
	def test_delete_vlun_success(self):
		"""Test successful vlun deletion."""
		self._simulate_exists("vol4", "host4", 1)
		result = self.workflow.delete_vlun("vol4", 1, "host4")
		
		self.assertEqual(len(result), 3)  # 3 VLUNs deleted
		self.assertEqual(self.session_mgr.rest_client.delete.call_count, 3)

	def test_delete_vlun_with_port(self):
		"""Test vlun deletion with port specified."""
		self._simulate_exists("vol5", "host5", 2)
		result = self.workflow.delete_vlun("vol5", 2, "host5", port="0:4:1")
		
		# Should add portPos to query
		self.assertIsNotNone(result)

	def test_delete_vlun_without_hostname(self):
		"""Test vlun deletion without hostname."""
		self._simulate_exists("vol6", None, 3)
		result = self.workflow.delete_vlun("vol6", 3)
		
		# Should still work without hostname
		self.assertIsNotNone(result)

	def test_delete_vlun_not_found(self):
		"""Test vlun deletion when VLUNs are not found."""
		self.session_mgr.rest_client.get.return_value = []
		result = self.workflow.delete_vlun("vol7", 4, "host7")
		
		# Returns None when no VLUNs found
		self.assertIsNone(result)

	def test_delete_vlun_none_volname(self):
		"""Test vlun deletion with None volume name."""
		result = self.workflow.delete_vlun(None, 5, "host8")
		self.assertIsNone(result)

	def test_delete_vlun_none_lun(self):
		"""Test vlun deletion with None LUN."""
		result = self.workflow.delete_vlun("vol9", None, "host9")
		self.assertIsNone(result)

	def test_delete_vlun_exception_during_delete(self):
		"""Test exception handling during vlun deletion."""
		self._simulate_exists("vol10", "host10", 6)
		self.session_mgr.rest_client.delete.side_effect = Exception("Delete failed")
		
		with self.assertRaises(Exception) as context:
			self.workflow.delete_vlun("vol10", 6, "host10")
		self.assertIn("Delete failed", str(context.exception))

	def test_delete_vlun_exception_during_get(self):
		"""Test exception handling during UID retrieval."""
		self.session_mgr.rest_client.get.side_effect = Exception("Get failed")
		
		with self.assertRaises(Exception) as context:
			self.workflow.delete_vlun("vol11", 7, "host11")
		self.assertIn("Get failed", str(context.exception))

	# ===================================================================
	# GET VLUN TESTS
	# ===================================================================

	def test_get_vlun_by_volumename(self):
		"""Test get vlun by volume name."""
		self.session_mgr.rest_client.get.return_value = [
			{"uid": "uid1", "volumeName": "vol1", "lun": 0}
		]
		result = self.workflow.get_vlun("volumeName", "vol1")
		
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["volumeName"], "vol1")
		self.session_mgr.rest_client.get.assert_called_once()

	def test_get_vlun_by_hostname(self):
		"""Test get vlun by hostname."""
		self.session_mgr.rest_client.get.return_value = [
			{"uid": "uid2", "hostName": "host1", "lun": 1}
		]
		result = self.workflow.get_vlun("hostName", "host1")
		
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["hostName"], "host1")

	def test_get_vlun_by_lun(self):
		"""Test get vlun by LUN."""
		self.session_mgr.rest_client.get.return_value = [
			{"uid": "uid3", "lun": 5}
		]
		result = self.workflow.get_vlun("lun", "5")
		
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["lun"], 5)

	def test_get_vlun_none_key(self):
		"""Test get vlun with None key."""
		result = self.workflow.get_vlun(None, "value")
		self.assertIsNone(result)

	def test_get_vlun_none_value(self):
		"""Test get vlun with None value."""
		result = self.workflow.get_vlun("key", None)
		self.assertIsNone(result)

	def test_get_vlun_empty_response(self):
		"""Test get vlun with empty response."""
		self.session_mgr.rest_client.get.return_value = []
		with self.assertRaises(ValueError) as context:
			self.workflow.get_vlun("volumeName", "vol_empty")
		self.assertIn("Invalid vlun response format", str(context.exception))

	def test_get_vlun_invalid_response_dict(self):
		"""Test get vlun with invalid response format (dict without members)."""
		self.session_mgr.rest_client.get.return_value = {"data": "invalid"}
		with self.assertRaises(ValueError) as context:
			self.workflow.get_vlun("volumeName", "vol_invalid")
		self.assertIn("Invalid vlun response format", str(context.exception))

	def test_get_vlun_uses_experimental_filter_header(self):
		"""Test that get_vlun uses experimentalfilter header."""
		self.session_mgr.rest_client.get.return_value = [{"uid": "uid1", "volumeName": "vol1"}]
		self.workflow.get_vlun("volumeName", "vol1")
		
		call_args = self.session_mgr.rest_client.get.call_args
		headers = call_args[1].get('headers', call_args[0][1] if len(call_args[0]) > 1 else None)
		self.assertEqual(headers, {'experimentalfilter': 'true'})

	def test_get_vlun_exception(self):
		"""Test get vlun with REST exception."""
		self.session_mgr.rest_client.get.side_effect = Exception("API error")
		with self.assertRaises(Exception) as context:
			self.workflow.get_vlun("volumeName", "vol_error")
		self.assertIn("API error", str(context.exception))

	# ===================================================================
	# GET VLUNS TESTS
	# ===================================================================

	def test_get_vluns_success(self):
		"""Test successful retrieval of all vluns."""
		self.session_mgr.rest_client.get.return_value = [
			{"uid": "uid1", "volumeName": "vol1", "lun": 0},
			{"uid": "uid2", "volumeName": "vol2", "lun": 1}
		]
		result = self.workflow.get_vluns()
		
		self.assertEqual(len(result), 2)
		self.session_mgr.rest_client.get.assert_called_once_with("/vluns")

	def test_get_vluns_empty(self):
		"""Test get_vluns with empty response."""
		self.session_mgr.rest_client.get.return_value = []
		with self.assertRaises(ValueError) as context:
			self.workflow.get_vluns()
		self.assertIn("Invalid vluns response format", str(context.exception))

	def test_get_vluns_invalid_response(self):
		"""Test get_vluns with invalid response format."""
		self.session_mgr.rest_client.get.return_value = {"error": "invalid"}
		with self.assertRaises(ValueError) as context:
			self.workflow.get_vluns()
		self.assertIn("Invalid vluns response format", str(context.exception))

	def test_get_vluns_exception(self):
		"""Test get_vluns with REST exception."""
		self.session_mgr.rest_client.get.side_effect = Exception("Connection error")
		with self.assertRaises(Exception) as context:
			self.workflow.get_vluns()
		self.assertIn("Connection error", str(context.exception))

	# ===================================================================
	# NORMALIZE_MEMBERS TESTS
	# ===================================================================

	def test_normalize_members_dict_with_dict_members(self):
		"""Test normalize_members with dict containing dict members."""
		response = {
			"members": {
				"uid1": {"name": "item1"},
				"uid2": {"name": "item2"}
			}
		}
		result = VLunWorkflow.normalize_members(response)
		self.assertEqual(len(result), 2)
		self.assertIsInstance(result, list)

	def test_normalize_members_dict_with_list_members(self):
		"""Test normalize_members with dict containing list members."""
		response = {
			"members": [
				{"name": "item1"},
				{"name": "item2"}
			]
		}
		result = VLunWorkflow.normalize_members(response)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["name"], "item1")

	def test_normalize_members_plain_list(self):
		"""Test normalize_members with plain list."""
		response = [
			{"name": "item1"},
			{"name": "item2"}
		]
		result = VLunWorkflow.normalize_members(response)
		self.assertEqual(len(result), 2)
		self.assertEqual(result, response)

	def test_normalize_members_dict_without_members(self):
		"""Test normalize_members with dict without members key."""
		response = {"data": "something"}
		result = VLunWorkflow.normalize_members(response)
		self.assertEqual(result, [])

	def test_normalize_members_empty_dict(self):
		"""Test normalize_members with empty dict."""
		response = {}
		result = VLunWorkflow.normalize_members(response)
		self.assertEqual(result, [])

	def test_normalize_members_empty_list(self):
		"""Test normalize_members with empty list."""
		response = []
		result = VLunWorkflow.normalize_members(response)
		self.assertEqual(result, [])

	def test_normalize_members_none(self):
		"""Test normalize_members with None."""
		result = VLunWorkflow.normalize_members(None)
		self.assertEqual(result, [])

	def test_normalize_members_string(self):
		"""Test normalize_members with string (invalid type)."""
		result = VLunWorkflow.normalize_members("invalid")
		self.assertEqual(result, [])

	def test_normalize_members_int(self):
		"""Test normalize_members with integer (invalid type)."""
		result = VLunWorkflow.normalize_members(123)
		self.assertEqual(result, [])

	# ===================================================================
	# GET VLUN UIDS TESTS
	# ===================================================================

	def test_get_vlun_uids_success(self):
		"""Test successful UID retrieval."""
		self._simulate_exists("vol_uid", "host_uid", 8)
		result = self.workflow._get_vlun_uids("vol_uid", 8, "host_uid", None)
		
		self.assertEqual(len(result), 3)
		self.assertIn("d8fa72eae2e4ff2df7e750ded911f0ec", result)

	def test_get_vlun_uids_with_port(self):
		"""Test UID retrieval with port specified."""
		self._simulate_exists("vol_port", "host_port", 9)
		result = self.workflow._get_vlun_uids("vol_port", 9, "host_port", "0:4:1")
		
		# Should include portPos in query
		call_args = self.session_mgr.rest_client.get.call_args
		self.assertIn("portPos", call_args[0][0])

	def test_get_vlun_uids_without_hostname(self):
		"""Test UID retrieval without hostname."""
		self._simulate_exists("vol_no_host", None, 10)
		result = self.workflow._get_vlun_uids("vol_no_host", 10, None, None)
		
		# Should not include hostName in query
		call_args = self.session_mgr.rest_client.get.call_args
		self.assertNotIn("hostName", call_args[0][0])

	def test_get_vlun_uids_without_port(self):
		"""Test UID retrieval without port."""
		self._simulate_exists("vol_no_port", "host_no_port", 11)
		result = self.workflow._get_vlun_uids("vol_no_port", 11, "host_no_port", None)
		
		# Should not include portPos in query
		call_args = self.session_mgr.rest_client.get.call_args
		self.assertNotIn("portPos", call_args[0][0])

	def test_get_vlun_uids_none_volname(self):
		"""Test UID retrieval with None volume name."""
		result = self.workflow._get_vlun_uids(None, 12, "host", None)
		self.assertIsNone(result)

	def test_get_vlun_uids_none_lun(self):
		"""Test UID retrieval with None LUN."""
		result = self.workflow._get_vlun_uids("vol", None, "host", None)
		self.assertIsNone(result)

	def test_get_vlun_uids_empty_response(self):
		"""Test UID retrieval with empty response."""
		self.session_mgr.rest_client.get.return_value = []
		result = self.workflow._get_vlun_uids("vol_empty", 13, "host_empty", None)
		
		# Empty response means no members, should return None
		self.assertIsNone(result)

	def test_get_vlun_uids_response_without_uid(self):
		"""Test UID retrieval when response items lack uid field."""
		self.session_mgr.rest_client.get.return_value = [
			{"volumeName": "vol1", "lun": 0}  # Missing uid
		]
		result = self.workflow._get_vlun_uids("vol1", 0, "host1", None)
		
		# Items without uid should be skipped
		self.assertEqual(result, [])

	def test_get_vlun_uids_exception(self):
		"""Test UID retrieval with REST exception."""
		self.session_mgr.rest_client.get.side_effect = Exception("Fetch failed")
		with self.assertRaises(Exception) as context:
			self.workflow._get_vlun_uids("vol_error", 14, "host_error", None)
		self.assertIn("Fetch failed", str(context.exception))


if __name__ == "__main__":
	unittest.main()