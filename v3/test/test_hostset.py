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
from unittest.mock import MagicMock, Mock, patch
import sys
import os

# Ensure src is on sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hpe_storage_flowkit_py.v3.src.workflows.hostset import HostSetWorkflow
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.rest_client import RESTClient


class TestHostSetWorkflow(unittest.TestCase):
	"""Unit tests for HostSetWorkflow class using a simple Mock REST client.

	Tests cover all methods with positive and negative scenarios including edge cases.
	"""

	def setUp(self):
		"""Set up test fixtures before each test method."""
		self.session_client = Mock()
		self.session_client.rest_client = Mock(spec=RESTClient)
		# Default canned responses (no state tracking)
		self.session_client.rest_client.get.return_value = {"members": {}}
		self.session_client.rest_client.post.return_value = {"status": "created"}
		self.session_client.rest_client.delete.return_value = {"status": "deleted"}
		self.session_client.rest_client.patch.return_value = {"status": "modified"}
		self.task_manager = Mock()
		self.task_manager.waitForTaskToEnd.return_value = {"status": "completed"}
		self.workflow = HostSetWorkflow(self.session_client, self.task_manager)

	def _simulate_exists(self, name, uid="uid_x", members=None, domain=None, comment=None):
		"""Helper to simulate an existing host set with given properties."""
		members = members or []
		hostset_data = {
			"uid": uid,
			"name": name,
			"members": members
		}
		if domain:
			hostset_data["domain"] = domain
		if comment:
			hostset_data["comment"] = comment
		
		self.session_client.rest_client.get.return_value = {
			"members": {
				uid: hostset_data
			}
		}
	
	# ===================================================================
	# CREATE HOSTSET TESTS
	# ===================================================================
	
	def test_create_hostset_success_minimal(self):
		"""Test successful hostset creation with only required name parameter."""
		self.workflow.create_hostset("hostset1")
		self.session_client.rest_client.post.assert_called_once()
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(call_args[0][0], "/hostsets")
		self.assertEqual(call_args[0][1]["name"], "hostset1")
	
	def test_create_hostset_success_with_all_optional_params(self):
		"""Test hostset creation with all optional parameters."""
		self.workflow.create_hostset(
			"hostset2",
			domain="production",
			comment="Production host set",
			setmembers=["host1", "host2", "host3"]
		)
		call_args = self.session_client.rest_client.post.call_args
		payload = call_args[0][1]  # Second positional argument
		self.assertEqual(payload["name"], "hostset2")
		self.assertEqual(payload["domain"], "production")
		self.assertEqual(payload["comment"], "Production host set")
		self.assertEqual(payload["members"], ["host1", "host2", "host3"])
	
	def test_create_hostset_success_with_domain_only(self):
		"""Test hostset creation with only domain parameter."""
		self.workflow.create_hostset("hostset3", domain="test_domain")
		call_args = self.session_client.rest_client.post.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["name"], "hostset3")
		self.assertEqual(payload["domain"], "test_domain")
	
	def test_create_hostset_success_with_comment_only(self):
		"""Test hostset creation with only comment parameter."""
		self.workflow.create_hostset("hostset4", comment="Test comment")
		call_args = self.session_client.rest_client.post.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["name"], "hostset4")
		self.assertEqual(payload["comment"], "Test comment")
	
	def test_create_hostset_success_with_members_only(self):
		"""Test hostset creation with only members parameter."""
		self.workflow.create_hostset("hostset5", setmembers=["host1", "host2"])
		call_args = self.session_client.rest_client.post.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["name"], "hostset5")
		self.assertEqual(payload["members"], ["host1", "host2"])
	
	def test_create_hostset_async_task_202(self):
		"""Test hostset creation with async task (202 response)."""
		# Mock 202 response with resourceUri
		self.session_client.rest_client.post.return_value = {
			"message": "Started task to execute create Host Set",
			"resourceUri": "/api/v3/tasks/abc123"
		}
		# Mock task manager wait_for_task_to_end
		with patch.object(self.workflow.task_manager, 'wait_for_task_to_end', return_value={"status": "completed"}):
			self.workflow.create_hostset("hostset_async")
			self.workflow.task_manager.wait_for_task_to_end.assert_called_once_with(
				"/api/v3/tasks/abc123"
			)
	
	def test_create_hostset_invalid_name_empty(self):
		"""Test hostset creation with empty name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("")
		self.assertIn("non-empty string", str(context.exception))
	
	def test_create_hostset_invalid_name_none(self):
		"""Test hostset creation with None name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset(None)
		self.assertIn("cannot be null", str(context.exception))
	
	def test_create_hostset_invalid_name_whitespace_only(self):
		"""Test hostset creation with whitespace-only name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("   ")
		self.assertIn("non-empty string", str(context.exception))
	
	def test_create_hostset_invalid_name_too_long(self):
		"""Test hostset creation with name exceeding max length of 27 characters."""
		long_name = "a" * 28  # Exceeds NAME_MAX of 27
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset(long_name)
		self.assertIn("27 characters", str(context.exception))
	
	def test_create_hostset_invalid_name_below_min(self):
		"""Test hostset creation with name less than min length."""
		# Empty string is handled by non-empty check, but test boundary
		with self.assertRaises(ValueError):
			self.workflow.create_hostset("")
	
	def test_create_hostset_invalid_domain_not_string(self):
		"""Test hostset creation with non-string domain."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset6", domain=123)
		self.assertIn("must be a string", str(context.exception).lower())
	
	def test_create_hostset_invalid_domain_empty(self):
		"""Test hostset creation with empty domain string."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset7", domain="")
		self.assertIn("cannot be empty", str(context.exception).lower())
	
	def test_create_hostset_invalid_domain_whitespace_only(self):
		"""Test hostset creation with whitespace-only domain."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset8", domain="   ")
		self.assertIn("cannot be empty", str(context.exception).lower())
	
	def test_create_hostset_invalid_comment_not_string(self):
		"""Test hostset creation with non-string comment."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset9", comment=456)
		self.assertIn("must be a string", str(context.exception).lower())
	
	def test_create_hostset_invalid_members_not_list(self):
		"""Test hostset creation with members not being a list."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset10", setmembers="host1")
		self.assertIn("must be a list", str(context.exception).lower())
	
	def test_create_hostset_invalid_members_empty_string(self):
		"""Test hostset creation with empty string in members list."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset11", setmembers=["host1", ""])
		self.assertIn("non-empty string", str(context.exception))
	
	def test_create_hostset_invalid_members_non_string_element(self):
		"""Test hostset creation with non-string element in members list."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset12", setmembers=["host1", 123])
		self.assertIn("non-empty string", str(context.exception))
	
	def test_create_hostset_invalid_members_whitespace_element(self):
		"""Test hostset creation with whitespace-only element in members."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset13", setmembers=["host1", "   "])
		self.assertIn("non-empty string", str(context.exception))
	
	def test_create_hostset_invalid_unsupported_param(self):
		"""Test hostset creation with unsupported parameter."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_hostset("hostset14", invalid_param="value")
		self.assertIn("Unsupported parameter", str(context.exception))
	
	def test_create_hostset_already_exists(self):
		"""Test hostset creation when hostset already exists."""
		self._simulate_exists("hostset_dup")
		with self.assertRaises(exceptions.HostSetAlreadyExists):
			self.workflow.create_hostset("hostset_dup")
	
	def test_create_hostset_with_none_optional_params(self):
		"""Test hostset creation with None values for optional params (should be ignored)."""
		self.workflow.create_hostset("hostset15", domain=None, comment=None, setmembers=None)
		call_args = self.session_client.rest_client.post.call_args
		payload = call_args[0][1]
		# None values should not be added to payload
		self.assertNotIn("domain", payload)
		self.assertNotIn("comment", payload)
		self.assertNotIn("members", payload)
	
	# ===================================================================
	# DELETE HOSTSET TESTS
	# ===================================================================
	
	def test_delete_hostset_success(self):
		"""Test successful hostset deletion."""
		self._simulate_exists("hostset_del", uid="uid_del")
		self.workflow.delete_hostset("hostset_del")
		self.session_client.rest_client.delete.assert_called_once_with("/hostsets/uid_del")
	
	def test_delete_hostset_not_exists(self):
		"""Test hostset deletion when hostset does not exist."""
		with self.assertRaises(exceptions.HostSetDoesNotExist):
			self.workflow.delete_hostset("nonexistent_hostset")
	
	def test_delete_hostset_invalid_name_empty(self):
		"""Test hostset deletion with empty name."""
		with self.assertRaises(ValueError):
			self.workflow.delete_hostset("")
	
	def test_delete_hostset_invalid_name_none(self):
		"""Test hostset deletion with None name."""
		with self.assertRaises(ValueError):
			self.workflow.delete_hostset(None)
	
	def test_delete_hostset_uses_uid(self):
		"""Test that delete operation uses UID in the URL, not name."""
		self._simulate_exists("hostset_uid_test", uid="unique_uid_123")
		self.workflow.delete_hostset("hostset_uid_test")
		# Verify the UID is used in the delete URL
		call_args = self.session_client.rest_client.delete.call_args
		self.assertIn("unique_uid_123", call_args[0][0])
	
	# ===================================================================
	# GET HOSTSET TESTS
	# ===================================================================
	
	def test_get_hostset_success(self):
		"""Test successful retrieval of hostset information."""
		self._simulate_exists("hostset_get", uid="uid_get", members=["host1", "host2"])
		result = self.workflow.get_hostset("hostset_get")
		self.assertEqual(result["name"], "hostset_get")
		self.assertEqual(result["uid"], "uid_get")
		self.assertEqual(result["members"], ["host1", "host2"])
	
	def test_get_hostset_with_all_properties(self):
		"""Test get hostset returns all properties."""
		self._simulate_exists("hostset_full", uid="uid_full", members=["host1"], 
							 domain="prod", comment="Production hosts")
		result = self.workflow.get_hostset("hostset_full")
		self.assertEqual(result["name"], "hostset_full")
		self.assertEqual(result["domain"], "prod")
		self.assertEqual(result["comment"], "Production hosts")
	
	def test_get_hostset_not_exists(self):
		"""Test get hostset when it doesn't exist returns empty list."""
		result = self.workflow.get_hostset("nonexistent")
		self.assertEqual(result, [])
	
	def test_get_hostset_invalid_name_empty(self):
		"""Test get hostset with empty name."""
		with self.assertRaises(ValueError):
			self.workflow.get_hostset("")
	
	def test_get_hostset_invalid_name_none(self):
		"""Test get hostset with None name."""
		with self.assertRaises(ValueError):
			self.workflow.get_hostset(None)
	
	# ===================================================================
	# HOSTSET EXISTS TESTS
	# ===================================================================
	
	def test_hostset_exists_true(self):
		"""Test hostset_exists returns True for existing hostset."""
		self._simulate_exists("hostset_exists")
		exists = self.workflow.hostset_exists("hostset_exists")
		self.assertTrue(exists)
	
	def test_hostset_exists_false(self):
		"""Test hostset_exists returns False for non-existing hostset."""
		exists = self.workflow.hostset_exists("hostset_notexists")
		self.assertFalse(exists)
	
	def test_hostset_exists_invalid_name_empty(self):
		"""Test hostset_exists with empty name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.hostset_exists("")
		self.assertIn("non-empty string", str(context.exception))
	
	def test_hostset_exists_invalid_name_none(self):
		"""Test hostset_exists with None name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.hostset_exists(None)
		self.assertIn("non-empty string", str(context.exception))
	
	def test_hostset_exists_invalid_name_not_string(self):
		"""Test hostset_exists with non-string name."""
		with self.assertRaises(ValueError):
			self.workflow.hostset_exists(123)
	
	def test_hostset_exists_whitespace_only(self):
		"""Test hostset_exists with whitespace-only name."""
		with self.assertRaises(ValueError):
			self.workflow.hostset_exists("   ")
	
	# ===================================================================
	# ADD HOSTS TO HOSTSET TESTS
	# ===================================================================
	
	def test_add_hosts_to_hostset_success(self):
		"""Test successfully adding hosts to hostset."""
		self._simulate_exists("hostset_add", uid="uid_add", members=["host1"])
		result = self.workflow.add_hosts_to_hostset("hostset_add", ["host2", "host3"])
		self.assertEqual(result["status"], "modified")
		# Verify PATCH was called with combined members
		call_args = self.session_client.rest_client.patch.call_args
		self.assertIn("uid_add", call_args[0][0])
		payload = call_args[1]["payload"]
		self.assertIn("host1", payload["members"])  # existing
		self.assertIn("host2", payload["members"])  # new
		self.assertIn("host3", payload["members"])  # new
	
	def test_add_hosts_to_hostset_empty_initial(self):
		"""Test adding hosts to hostset with no existing members."""
		self._simulate_exists("hostset_add2", uid="uid_add2", members=[])
		result = self.workflow.add_hosts_to_hostset("hostset_add2", ["host1"])
		self.assertEqual(result["status"], "modified")
	
	def test_add_hosts_to_hostset_single_host(self):
		"""Test adding single host to hostset."""
		self._simulate_exists("hostset_add3", uid="uid_add3", members=["host1"])
		result = self.workflow.add_hosts_to_hostset("hostset_add3", ["host2"])
		self.assertEqual(result["status"], "modified")
	
	def test_add_hosts_to_hostset_all_duplicates(self):
		"""Test adding hosts that are all already members."""
		self._simulate_exists("hostset_add4", members=["host1", "host2"])
		with self.assertRaises(exceptions.HostSetMembersAlreadyPresent):
			self.workflow.add_hosts_to_hostset("hostset_add4", ["host1", "host2"])
	
	def test_add_hosts_to_hostset_partial_duplicates(self):
		"""Test adding hosts with some duplicates (only new ones should be added)."""
		self._simulate_exists("hostset_add5", uid="uid_add5", members=["host1"])
		result = self.workflow.add_hosts_to_hostset("hostset_add5", ["host1", "host2", "host3"])
		self.assertEqual(result["status"], "modified")
		# Verify only new members are added
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[1]["payload"]
		self.assertEqual(len(payload["members"]), 3)  # host1, host2, host3
	
	def test_add_hosts_to_hostset_not_exists(self):
		"""Test adding hosts to non-existing hostset."""
		with self.assertRaises(exceptions.HostSetDoesNotExist):
			self.workflow.add_hosts_to_hostset("nonexistent", ["host1"])
	
	def test_add_hosts_to_hostset_null_setmembers(self):
		"""Test adding null setmembers to hostset."""
		self._simulate_exists("hostset_add6")
		with self.assertRaises(ValueError) as context:
			self.workflow.add_hosts_to_hostset("hostset_add6", None)
		self.assertIn("cannot be null", str(context.exception))
	
	def test_add_hosts_to_hostset_empty_list(self):
		"""Test adding empty list of hosts."""
		self._simulate_exists("hostset_add7")
		with self.assertRaises(exceptions.HostSetMembersAlreadyPresent):
			self.workflow.add_hosts_to_hostset("hostset_add7", [])
	
	def test_add_hosts_to_hostset_invalid_name(self):
		"""Test adding hosts with invalid hostset name."""
		with self.assertRaises(ValueError):
			self.workflow.add_hosts_to_hostset("", ["host1"])
	
	def test_add_hosts_to_hostset_uses_uid(self):
		"""Test that add operation uses UID in the URL."""
		self._simulate_exists("hostset_add8", uid="unique_uid_add", members=[])
		self.workflow.add_hosts_to_hostset("hostset_add8", ["host1"])
		call_args = self.session_client.rest_client.patch.call_args
		self.assertIn("unique_uid_add", call_args[0][0])
	
	def test_add_hosts_to_hostset_preserves_order(self):
		"""Test that adding hosts preserves the order of existing members."""
		self._simulate_exists("hostset_add9", uid="uid_add9", members=["host1", "host2"])
		self.workflow.add_hosts_to_hostset("hostset_add9", ["host3"])
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[1]["payload"]
		# Should be existing + new
		self.assertEqual(payload["members"], ["host1", "host2", "host3"])
	
	# ===================================================================
	# REMOVE HOSTS FROM HOSTSET TESTS
	# ===================================================================
	
	def test_remove_hosts_from_hostset_success(self):
		"""Test successfully removing hosts from hostset."""
		self._simulate_exists("hostset_rem", uid="uid_rem", members=["host1", "host2", "host3"])
		result = self.workflow.remove_hosts_from_hostset("hostset_rem", ["host2"])
		self.assertEqual(result["status"], "modified")
		# Verify PATCH was called with reduced members
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[1]["payload"]
		self.assertIn("host1", payload["members"])
		self.assertIn("host3", payload["members"])
		self.assertNotIn("host2", payload["members"])
	
	def test_remove_hosts_from_hostset_multiple(self):
		"""Test removing multiple hosts from hostset."""
		self._simulate_exists("hostset_rem2", uid="uid_rem2", members=["host1", "host2", "host3", "host4"])
		result = self.workflow.remove_hosts_from_hostset("hostset_rem2", ["host2", "host3"])
		self.assertEqual(result["status"], "modified")
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[1]["payload"]
		self.assertEqual(len(payload["members"]), 2)  # Only host1 and host4 remain
	
	def test_remove_hosts_from_hostset_all_members(self):
		"""Test removing all hosts from hostset (results in empty hostset)."""
		self._simulate_exists("hostset_rem3", uid="uid_rem3", members=["host1", "host2"])
		result = self.workflow.remove_hosts_from_hostset("hostset_rem3", ["host1", "host2"])
		self.assertEqual(result["status"], "modified")
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[1]["payload"]
		self.assertEqual(payload["members"], [])
	
	def test_remove_hosts_from_hostset_not_member(self):
		"""Test removing hosts that are not members."""
		self._simulate_exists("hostset_rem4", members=["host1"])
		with self.assertRaises(exceptions.HostSetMembersAlreadyRemoved):
			self.workflow.remove_hosts_from_hostset("hostset_rem4", ["host2", "host3"])
	
	def test_remove_hosts_from_hostset_partial_members(self):
		"""Test removing hosts with some being members and some not."""
		self._simulate_exists("hostset_rem5", uid="uid_rem5", members=["host1", "host2"])
		result = self.workflow.remove_hosts_from_hostset("hostset_rem5", ["host1", "host3"])
		self.assertEqual(result["status"], "modified")
		# Should only remove host1 (host3 is not a member)
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[1]["payload"]
		self.assertEqual(payload["members"], ["host2"])
	
	def test_remove_hosts_from_hostset_not_exists(self):
		"""Test removing hosts from non-existing hostset."""
		with self.assertRaises(exceptions.HostSetDoesNotExist):
			self.workflow.remove_hosts_from_hostset("nonexistent", ["host1"])
	
	def test_remove_hosts_from_hostset_null_setmembers(self):
		"""Test removing null setmembers from hostset."""
		self._simulate_exists("hostset_rem6", members=["host1"])
		with self.assertRaises(ValueError) as context:
			self.workflow.remove_hosts_from_hostset("hostset_rem6", None)
		self.assertIn("cannot be null", str(context.exception))
	
	def test_remove_hosts_from_hostset_empty_list(self):
		"""Test removing empty list of hosts."""
		self._simulate_exists("hostset_rem7", members=["host1"])
		with self.assertRaises(exceptions.HostSetMembersAlreadyRemoved):
			self.workflow.remove_hosts_from_hostset("hostset_rem7", [])
	
	def test_remove_hosts_from_hostset_invalid_name(self):
		"""Test removing hosts with invalid hostset name."""
		with self.assertRaises(ValueError):
			self.workflow.remove_hosts_from_hostset("", ["host1"])
	
	def test_remove_hosts_from_hostset_uses_uid(self):
		"""Test that remove operation uses UID in the URL."""
		self._simulate_exists("hostset_rem8", uid="unique_uid_rem", members=["host1", "host2"])
		self.workflow.remove_hosts_from_hostset("hostset_rem8", ["host1"])
		call_args = self.session_client.rest_client.patch.call_args
		self.assertIn("unique_uid_rem", call_args[0][0])
	
	def test_remove_hosts_from_hostset_preserves_order(self):
		"""Test that removing hosts preserves the order of remaining members."""
		self._simulate_exists("hostset_rem9", uid="uid_rem9", members=["host1", "host2", "host3", "host4"])
		self.workflow.remove_hosts_from_hostset("hostset_rem9", ["host2", "host4"])
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[1]["payload"]
		# Should maintain original order of remaining members
		self.assertEqual(payload["members"], ["host1", "host3"])
	
	def test_remove_hosts_from_hostset_from_empty(self):
		"""Test removing hosts from hostset with no members."""
		self._simulate_exists("hostset_rem10", members=[])
		with self.assertRaises(exceptions.HostSetMembersAlreadyRemoved):
			self.workflow.remove_hosts_from_hostset("hostset_rem10", ["host1"])
	
	# ===================================================================
	# EDGE CASES AND BOUNDARY TESTS
	# ===================================================================
	
	def test_hostset_name_exactly_27_chars(self):
		"""Test hostset with name exactly at max length (27 characters)."""
		name_27 = "a" * 27
		self.workflow.create_hostset(name_27)
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(call_args[0][1]["name"], name_27)
	
	def test_hostset_name_exactly_1_char(self):
		"""Test hostset with name exactly at min length (1 character)."""
		name_1 = "a"
		self.workflow.create_hostset(name_1)
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(call_args[0][1]["name"], name_1)
	
	def test_hostset_with_special_characters_in_name(self):
		"""Test hostset with special characters in name (should be accepted if valid)."""
		name_special = "host-set_01.test"
		self.workflow.create_hostset(name_special)
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(call_args[0][1]["name"], name_special)
	
	def test_hostset_with_large_member_list(self):
		"""Test hostset with a large number of members."""
		large_member_list = [f"host{i}" for i in range(100)]
		self.workflow.create_hostset("hostset_large", setmembers=large_member_list)
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(len(call_args[0][1]["members"]), 100)
	
	def test_hostset_comment_empty_string_allowed(self):
		"""Test that empty string comment is allowed (not validated like domain)."""
		# Based on validator, empty comment is allowed
		self.workflow.create_hostset("hostset_empty_comment", comment="")
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(call_args[0][1]["comment"], "")
	
	def test_multiple_operations_sequence(self):
		"""Test sequence of operations on same hostset."""
		# Create
		self.workflow.create_hostset("hostset_seq")
		# Simulate it exists now
		self._simulate_exists("hostset_seq", uid="uid_seq", members=[])
		# Add members
		self.workflow.add_hosts_to_hostset("hostset_seq", ["host1", "host2"])
		# Simulate updated members
		self._simulate_exists("hostset_seq", uid="uid_seq", members=["host1", "host2"])
		# Remove one member
		self.workflow.remove_hosts_from_hostset("hostset_seq", ["host1"])
		# Simulate updated members
		self._simulate_exists("hostset_seq", uid="uid_seq", members=["host2"])
		# Get info
		result = self.workflow.get_hostset("hostset_seq")
		self.assertEqual(result["members"], ["host2"])
	
	def test_rest_client_exception_handling(self):
		"""Test that REST client exceptions are properly propagated."""
		self.session_client.rest_client.get.side_effect = Exception("Connection error")
		with self.assertRaises(Exception) as context:
			self.workflow.hostset_exists("any_hostset")
		self.assertIn("Connection error", str(context.exception))
	
	def test_create_hostset_with_mixed_case_name(self):
		"""Test hostset creation with mixed case name."""
		self.workflow.create_hostset("HostSet-MixedCase")
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(call_args[0][1]["name"], "HostSet-MixedCase")
	
	def test_unicode_characters_in_comment(self):
		"""Test hostset with unicode characters in comment."""
		unicode_comment = "Test hostset with émojis 🚀 and spëcial chars"
		self.workflow.create_hostset("hostset_unicode", comment=unicode_comment)
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(call_args[0][1]["comment"], unicode_comment)


if __name__ == "__main__":
	unittest.main()
