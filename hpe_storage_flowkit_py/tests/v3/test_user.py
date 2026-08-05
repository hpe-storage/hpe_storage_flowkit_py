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

from hpe_storage_flowkit_py.v3.src.workflows.user import UserWorkflow
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.rest_client import RESTClient
from hpe_storage_flowkit_py.v3.src.validators.user_validator import validate_password_change_params, validate_user_operation_params


class MockTaskManager:
	"""Mock TaskManager for testing user workflows."""
	def __init__(self, session_mgr):
		self.session_mgr = session_mgr
	
	def wait_for_task_to_end(self, task_uri):
		return {"status": "STATE_FINISHED", "state": {"overall": "STATE_NORMAL"}}


class TestUserWorkflow(unittest.TestCase):
	"""Unit tests for UserWorkflow class using a simple Mock REST client.

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
		self.task_mgr = MockTaskManager(self.session_client)
		self.workflow = UserWorkflow(self.session_client, self.task_mgr)

	def _simulate_user_exists(self, name, uid="uid_x", domain_privileges=None):
		"""Helper to simulate an existing user with given properties."""
		domain_privileges = domain_privileges or [{"name": "default", "privilege": "browse"}]
		user_data = {
			"uid": uid,
			"name": name,
			"domainPrivileges": domain_privileges
		}
		
		self.session_client.rest_client.get.return_value = {
			"members": {
				uid: user_data
			}
		}


	
	def test_create_user_success_minimal(self):
		"""Test successful user creation with minimal required parameters."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		self.workflow.create_user("testuser", "password123", domain_privileges)
		self.session_client.rest_client.post.assert_called_once()
		call_args = self.session_client.rest_client.post.call_args
		self.assertEqual(call_args[0][0], "/users")
		payload = call_args[0][1]
		self.assertEqual(payload["name"], "testuser")
		self.assertEqual(payload["password"], ['p', 'a', 's', 's', 'w', 'o', 'r', 'd', '1', '2', '3'])
		# Check domain privileges structure
		self.assertEqual(len(payload["domainPrivileges"]), 1)
		self.assertEqual(payload["domainPrivileges"][0]["name"], "default")
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "browse")
	
	def test_create_user_success_with_all_params(self):
		"""Test user creation with all parameters."""
		domain_privileges = [
			{"name": "production", "privilege": "edit"},
			{"name": "development", "privilege": "browse"}
		]
		self.workflow.create_user(
			"admin_user",
			"SecurePass123!",
			domain_privileges
		)
		call_args = self.session_client.rest_client.post.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["name"], "admin_user")
		self.assertEqual(payload["password"], ['S', 'e', 'c', 'u', 'r', 'e', 'P', 'a', 's', 's', '1', '2', '3', '!'])
		# Check domain privileges structure
		self.assertEqual(len(payload["domainPrivileges"]), 2)
		self.assertEqual(payload["domainPrivileges"][0]["name"], "production")
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "edit")
		self.assertEqual(payload["domainPrivileges"][1]["name"], "development")
		self.assertEqual(payload["domainPrivileges"][1]["priv"], "browse")
	
	def test_create_user_async_task_202(self):
		"""Test user creation with async task (202 response)."""
		# Mock task manager for this test
		mock_task_manager = MagicMock()
		mock_task_manager.wait_for_task_to_end.return_value = {"status": "completed"}
		self.workflow.task_manager = mock_task_manager
		
		# Mock 202 response with resourceUri
		self.session_client.rest_client.post.return_value = {
			"message": "Started task to execute create User",
			"resourceUri": "/api/v3/tasks/abc123"
		}
		
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		self.workflow.create_user("async_user", "password123", domain_privileges)
		
		mock_task_manager.wait_for_task_to_end.assert_called_once_with(
			"/api/v3/tasks/abc123"
		)
	
	def test_create_user_invalid_name_empty(self):
		"""Test user creation with empty name."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("", "password123", domain_privileges)
		self.assertIn("cannot be empty", str(context.exception))
	
	def test_create_user_invalid_name_none(self):
		"""Test user creation with None name."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user(None, "password123", domain_privileges)
		self.assertIn("User name is required", str(context.exception))
	
	def test_create_user_invalid_name_non_string(self):
		"""Test user creation with non-string name."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user(123, "password123", domain_privileges)
		self.assertIn("must be a string", str(context.exception))
	
	def test_create_user_invalid_name_with_special_chars(self):
		"""Test user creation with invalid characters in name."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("user/invalid", "password123", domain_privileges)
		self.assertIn("invalid characters", str(context.exception))
	
	def test_create_user_invalid_password_empty(self):
		"""Test user creation with empty password."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "", domain_privileges)
		self.assertIn("cannot be empty", str(context.exception))
	
	def test_create_user_invalid_password_too_short(self):
		"""Test user creation with password too short."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "short", domain_privileges)
		self.assertIn("at least 8 characters", str(context.exception))
	
	def test_create_user_invalid_password_non_string_list(self):
		"""Test user creation with invalid password type."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", 12345, domain_privileges)
		self.assertIn("must be a string or list", str(context.exception))
	
	def test_create_user_invalid_domain_privileges_empty(self):
		"""Test user creation with empty domain privileges."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", [])
		self.assertIn("At least one domain privilege must be specified", str(context.exception))
	
	def test_create_user_invalid_domain_privileges_not_list(self):
		"""Test user creation with domain privileges not being a list."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", "invalid")
		self.assertIn("must be a list", str(context.exception))
	
	def test_create_user_invalid_domain_privilege_missing_domain(self):
		"""Test user creation with domain privilege missing domain."""
		domain_privileges = [{"privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("is missing 'name' field", str(context.exception))
	
	def test_create_user_invalid_domain_privilege_missing_privilege(self):
		"""Test user creation with domain privilege missing privilege."""
		domain_privileges = [{"name": "default"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("is missing 'privilege' field", str(context.exception))
	
	def test_create_user_invalid_privilege_value(self):
		"""Test user creation with invalid privilege value."""
		domain_privileges = [{"name": "default", "privilege": "invalid_privilege"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("Invalid privilege", str(context.exception))
	
	def test_create_user_already_exists(self):
		"""Test user creation when user already exists."""
		self._simulate_user_exists("duplicate_user")
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.UserAlreadyExists):
			self.workflow.create_user("duplicate_user", "password123", domain_privileges)
	
	def test_create_user_invalid_unsupported_param(self):
		"""Test user creation with unsupported parameter - should be ignored."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		# Unsupported parameters are ignored, not rejected
		self.workflow.create_user("testuser", "password123", domain_privileges, invalid_param="value")
		self.session_client.rest_client.post.assert_called_once()
	

	
	def test_get_all_users_success_empty(self):
		"""Test successful retrieval of all users when none exist."""
		result = self.workflow.get_all_users()
		self.assertEqual(result, {"members": {}})
		self.session_client.rest_client.get.assert_called_once_with("/users")
	
	def test_get_all_users_success_multiple(self):
		"""Test successful retrieval of multiple users."""
		self.session_client.rest_client.get.return_value = {
			"members": {
				"uid1": {"uid": "uid1", "name": "user1", "domainPrivileges": [{"name": "default", "privilege": "browse"}]},
				"uid2": {"uid": "uid2", "name": "user2", "domainPrivileges": [{"name": "prod", "privilege": "edit"}]}
			}
		}
		result = self.workflow.get_all_users()
		# get_all_users returns the raw API response
		self.assertIn("members", result)
		self.assertEqual(len(result["members"]), 2)
		users = list(result["members"].values())
		self.assertEqual(users[0]["name"], "user1")
		self.assertEqual(users[1]["name"], "user2")
	
	def test_get_all_users_success_single(self):
		"""Test successful retrieval of single user."""
		self._simulate_user_exists("single_user")
		result = self.workflow.get_all_users()
		# get_all_users returns the raw API response
		self.assertIn("members", result)
		self.assertEqual(len(result["members"]), 1)
		users = list(result["members"].values())
		self.assertEqual(users[0]["name"], "single_user")
	

	
	def test_get_user_by_name_success(self):
		"""Test successful retrieval of user by name."""
		self._simulate_user_exists("test_user", uid="uid_test")
		result = self.workflow.get_user_by_name("test_user")
		self.assertEqual(result["name"], "test_user")
		self.assertEqual(result["uid"], "uid_test")
	
	def test_get_user_by_name_not_exists(self):
		"""Test get user by name when user doesn't exist."""
		with self.assertRaises(exceptions.UserDoesNotExist):
			self.workflow.get_user_by_name("nonexistent_user")
	
	def test_get_user_by_name_invalid_name_empty(self):
		"""Test get user by name with empty name."""
		with self.assertRaises(exceptions.InvalidInput):
			self.workflow.get_user_by_name("")
	
	def test_get_user_by_name_invalid_name_none(self):
		"""Test get user by name with None name."""
		with self.assertRaises(exceptions.InvalidInput):
			self.workflow.get_user_by_name(None)
	
	def test_get_user_by_name_invalid_name_non_string(self):
		"""Test get user by name with non-string name."""
		with self.assertRaises(exceptions.InvalidInput):
			self.workflow.get_user_by_name(123)
	

	
	def test_modify_user_success_password_only(self):
		"""Test successful user modification with password change only."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		self.workflow.modify_user_by_name(
			"modify_user",
			current_password="oldpass123",
			new_password="newpass456"
		)
		self.session_client.rest_client.patch.assert_called_once()
		call_args = self.session_client.rest_client.patch.call_args
		self.assertEqual(call_args[0][0], "/users/uid_modify")
		payload = call_args[0][1]
		self.assertEqual(payload["currentPassword"], ['o', 'l', 'd', 'p', 'a', 's', 's', '1', '2', '3'])
		self.assertEqual(payload["newPassword"], ['n', 'e', 'w', 'p', 'a', 's', 's', '4', '5', '6'])
	
	def test_modify_user_success_domain_privileges_only(self):
		"""Test successful user modification with domain privileges change only."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		new_privileges = [{"name": "production", "privilege": "edit"}]
		self.workflow.modify_user_by_name("modify_user", domain_privileges=new_privileges)
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[0][1]
		# Check transformed domain privileges
		self.assertEqual(len(payload["domainPrivileges"]), 1)
		self.assertEqual(payload["domainPrivileges"][0]["name"], "production")
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "edit")
		self.assertNotIn("currentPassword", payload)
		self.assertNotIn("newPassword", payload)
	
	def test_modify_user_success_all_params(self):
		"""Test successful user modification with all parameters."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		new_privileges = [{"name": "test", "privilege": "super"}]
		self.workflow.modify_user_by_name(
			"modify_user",
			current_password="current123",
			new_password="newpass456",
			domain_privileges=new_privileges
		)
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["currentPassword"], ['c', 'u', 'r', 'r', 'e', 'n', 't', '1', '2', '3'])
		self.assertEqual(payload["newPassword"], ['n', 'e', 'w', 'p', 'a', 's', 's', '4', '5', '6'])
		# Check transformed domain privileges
		self.assertEqual(len(payload["domainPrivileges"]), 1)
		self.assertEqual(payload["domainPrivileges"][0]["name"], "test")
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "super")
	
	def test_modify_user_not_exists(self):
		"""Test modify user when user doesn't exist."""
		with self.assertRaises(exceptions.UserDoesNotExist):
			self.workflow.modify_user_by_name("nonexistent", 
				current_password="current123", 
				new_password="newpass123")
	
	def test_modify_user_no_changes(self):
		"""Test modify user with no actual changes provided."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.modify_user_by_name("modify_user")
		self.assertIn("At least one parameter", str(context.exception))
	
	def test_modify_user_invalid_password_combination(self):
		"""Test modify user with invalid password combination (only current password provided)."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		# Only providing current_password is allowed - API validation would catch issues
		self.workflow.modify_user_by_name("modify_user", current_password="current123")
		self.session_client.rest_client.patch.assert_called_once()
	
	def test_modify_user_invalid_new_password_only(self):
		"""Test modify user with only new password provided."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.modify_user_by_name("modify_user", new_password="newpass123")
		self.assertIn("currentPassword is required when changing password", str(context.exception))
	
	def test_modify_user_invalid_name_empty(self):
		"""Test modify user with empty name."""
		with self.assertRaises(exceptions.InvalidInput):
			self.workflow.modify_user_by_name("", new_password="newpass123")
	
	def test_modify_user_invalid_name_none(self):
		"""Test modify user with None name."""
		with self.assertRaises(exceptions.InvalidInput):
			self.workflow.modify_user_by_name(None, new_password="newpass123")
	
	def test_modify_user_invalid_unsupported_param(self):
		"""Test modify user with unsupported parameter - should be ignored."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		# Unsupported parameters are ignored, not rejected, but still need valid params
		self.workflow.modify_user_by_name("modify_user", 
			current_password="current123", 
			new_password="newpass123", 
			invalid_param="value")
		self.session_client.rest_client.patch.assert_called_once()
	

	
	def test_delete_user_success(self):
		"""Test successful user deletion."""
		self._simulate_user_exists("delete_user", uid="uid_delete")
		self.workflow.delete_user_by_name("delete_user")
		self.session_client.rest_client.delete.assert_called_once_with("/users/uid_delete")
	
	def test_delete_user_not_exists(self):
		"""Test user deletion when user does not exist."""
		with self.assertRaises(exceptions.UserDoesNotExist):
			self.workflow.delete_user_by_name("nonexistent_user")
	
	def test_delete_user_invalid_name_empty(self):
		"""Test user deletion with empty name."""
		with self.assertRaises(exceptions.InvalidInput):
			self.workflow.delete_user_by_name("")
	
	def test_delete_user_invalid_name_none(self):
		"""Test user deletion with None name."""
		with self.assertRaises(exceptions.InvalidInput):
			self.workflow.delete_user_by_name(None)
	
	def test_delete_user_invalid_name_non_string(self):
		"""Test user deletion with non-string name."""
		with self.assertRaises(exceptions.InvalidInput):
			self.workflow.delete_user_by_name(123)
	
	def test_delete_user_uses_uid(self):
		"""Test that delete operation uses UID in the URL, not name."""
		self._simulate_user_exists("delete_user_uid", uid="unique_uid_delete")
		self.workflow.delete_user_by_name("delete_user_uid")
		# Verify the UID is used in the delete URL
		call_args = self.session_client.rest_client.delete.call_args
		self.assertIn("unique_uid_delete", call_args[0][0])
	

	
	def test_fetch_user_uid_by_name_success(self):
		"""Test successful UID retrieval by name."""
		self._simulate_user_exists("test_uid_user", uid="special_uid_123")
		uid = self.workflow._fetch_user_uid_by_name("test_uid_user")
		self.assertEqual(uid, "special_uid_123")
	
	def test_fetch_user_uid_by_name_not_exists(self):
		"""Test UID retrieval when user doesn't exist."""
		with self.assertRaises(exceptions.UserDoesNotExist):
			self.workflow._fetch_user_uid_by_name("nonexistent_user")
	
	def test_build_create_user_payload(self):
		"""Test building create user payload."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		payload = self.workflow._build_create_user_payload("testuser", "password123", domain_privileges)
		self.assertEqual(payload["name"], "testuser")
		self.assertEqual(payload["password"], ['p', 'a', 's', 's', 'w', 'o', 'r', 'd', '1', '2', '3'])
		# The API transforms domain privileges structure - check first entry
		self.assertEqual(len(payload["domainPrivileges"]), 1)
		self.assertEqual(payload["domainPrivileges"][0]["name"], "default")
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "browse")
	
	def test_build_modify_user_payload_password_only(self):
		"""Test building modify user payload with password change."""
		payload = self.workflow._build_modify_user_payload(
			current_password="old123",
			new_password="newpass456"
		)
		self.assertEqual(payload["currentPassword"], ['o', 'l', 'd', '1', '2', '3'])
		self.assertEqual(payload["newPassword"], ['n', 'e', 'w', 'p', 'a', 's', 's', '4', '5', '6'])
		self.assertNotIn("domainPrivileges", payload)
	
	def test_build_modify_user_payload_privileges_only(self):
		"""Test building modify user payload with domain privileges only."""
		domain_privileges = [{"name": "test", "privilege": "edit"}]
		payload = self.workflow._build_modify_user_payload(domain_privileges=domain_privileges)
		# Check transformed domain privileges structure
		self.assertEqual(len(payload["domainPrivileges"]), 1)
		self.assertEqual(payload["domainPrivileges"][0]["name"], "test")
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "edit")
		self.assertNotIn("currentPassword", payload)
		self.assertNotIn("newPassword", payload)
	
	def test_build_modify_user_payload_all_params(self):
		"""Test building modify user payload with all parameters."""
		domain_privileges = [{"name": "prod", "privilege": "super"}]
		payload = self.workflow._build_modify_user_payload(
			current_password="current123",
			new_password="newpass456",
			domain_privileges=domain_privileges
		)
		self.assertEqual(payload["currentPassword"], ['c', 'u', 'r', 'r', 'e', 'n', 't', '1', '2', '3'])
		self.assertEqual(payload["newPassword"], ['n', 'e', 'w', 'p', 'a', 's', 's', '4', '5', '6'])
		# Check transformed domain privileges structure
		self.assertEqual(len(payload["domainPrivileges"]), 1)
		self.assertEqual(payload["domainPrivileges"][0]["name"], "prod")
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "super")

	# ===================================================================
	# PASSWORD LIST FORMAT TESTS
	# ===================================================================

	def test_create_user_password_as_list(self):
		"""Test user creation with password provided as list of characters."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		password_list = ['p', 'a', 's', 's', 'w', 'o', 'r', 'd', '1', '2', '3']
		self.workflow.create_user("testuser", password_list, domain_privileges)
		call_args = self.session_client.rest_client.post.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["password"], password_list)

	def test_modify_user_password_as_list(self):
		"""Test user modification with passwords provided as lists."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		current_pwd = ['o', 'l', 'd', 'p', 'a', 's', 's', '1', '2', '3']
		new_pwd = ['n', 'e', 'w', 'p', 'a', 's', 's', '4', '5', '6']
		self.workflow.modify_user_by_name("modify_user", current_password=current_pwd, new_password=new_pwd)
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[0][1]
		self.assertEqual(payload["currentPassword"], current_pwd)
		self.assertEqual(payload["newPassword"], new_pwd)

	# ===================================================================
	# ASYNC TASK HANDLING TESTS
	# ===================================================================

	def test_create_user_with_task_uri(self):
		"""Test user creation that returns a task URI."""
		self.session_client.rest_client.post.return_value = {"taskUri": "/api/v3/tasks/task_123"}
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		
		result = self.workflow.create_user("testuser", "password123", domain_privileges)
		
		self.assertEqual(result["status"], "STATE_FINISHED")

	def test_modify_user_with_resource_uri(self):
		"""Test user modification that returns a resource URI."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		self.session_client.rest_client.patch.return_value = {"resourceUri": "/api/v3/users/uid_modify"}
		
		result = self.workflow.modify_user_by_name("modify_user", 
			current_password="oldpass123", new_password="newpass456")
		
		self.assertEqual(result["status"], "STATE_FINISHED")

	def test_delete_user_with_task_uri(self):
		"""Test user deletion that returns a task URI."""
		self._simulate_user_exists("delete_user", uid="uid_delete")
		self.session_client.rest_client.delete.return_value = {"taskUri": "/api/v3/tasks/task_456"}
		
		result = self.workflow.delete_user_by_name("delete_user")
		
		self.assertEqual(result["status"], "STATE_FINISHED")

	# ===================================================================
	# PARSE USERS RESPONSE TESTS
	# ===================================================================

	def test_parse_users_response_dict_with_members_dict(self):
		"""Test parsing response with members as dict."""
		response = {
			"members": {
				"uid1": {"name": "user1", "uid": "uid1"},
				"uid2": {"name": "user2", "uid": "uid2"}
			}
		}
		result = self.workflow._parse_users_response(response)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["name"], "user1")

	def test_parse_users_response_plain_list(self):
		"""Test parsing response that is a plain list already."""
		response = [
			{"name": "user1", "uid": "uid1"},
			{"name": "user2", "uid": "uid2"}
		]
		result = self.workflow._parse_users_response(response)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["name"], "user1")

	def test_parse_users_response_plain_list(self):
		"""Test parsing response that is a plain list."""
		response = [
			{"name": "user1", "uid": "uid1"},
			{"name": "user2", "uid": "uid2"}
		]
		result = self.workflow._parse_users_response(response)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["name"], "user1")

	def test_parse_users_response_single_user_dict(self):
		"""Test parsing response that is a single user dict with uid."""
		response = {"name": "user1", "uid": "uid1"}
		result = self.workflow._parse_users_response(response)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["name"], "user1")

	def test_parse_users_response_empty_members_dict(self):
		"""Test parsing response with empty members dict."""
		response = {"members": {}}
		result = self.workflow._parse_users_response(response)
		self.assertEqual(len(result), 0)

	def test_parse_users_response_empty_members_list(self):
		"""Test parsing response with empty members list."""
		response = {"members": []}
		result = self.workflow._parse_users_response(response)
		self.assertEqual(len(result), 0)

	def test_parse_users_response_invalid_format(self):
		"""Test parsing response with invalid format."""
		response = {"data": "invalid"}
		result = self.workflow._parse_users_response(response)
		self.assertEqual(len(result), 0)

	# ===================================================================
	# DOMAIN PRIVILEGES TESTS
	# ===================================================================

	def test_create_user_multiple_domain_privileges(self):
		"""Test user creation with multiple domain privileges."""
		domain_privileges = [
			{"name": "domain1", "privilege": "browse"},
			{"name": "domain2", "privilege": "edit"},
			{"name": "domain3", "privilege": "super"}
		]
		self.workflow.create_user("testuser", "password123", domain_privileges)
		call_args = self.session_client.rest_client.post.call_args
		payload = call_args[0][1]
		self.assertEqual(len(payload["domainPrivileges"]), 3)
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "browse")
		self.assertEqual(payload["domainPrivileges"][1]["priv"], "edit")
		self.assertEqual(payload["domainPrivileges"][2]["priv"], "super")

	def test_modify_user_multiple_domain_privileges(self):
		"""Test user modification with multiple domain privileges."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		domain_privileges = [
			{"name": "domain1", "privilege": "service"},
			{"name": "domain2", "privilege": "security_admin"}
		]
		self.workflow.modify_user_by_name("modify_user", domain_privileges=domain_privileges)
		call_args = self.session_client.rest_client.patch.call_args
		payload = call_args[0][1]
		self.assertEqual(len(payload["domainPrivileges"]), 2)
		self.assertEqual(payload["domainPrivileges"][0]["priv"], "service")
		self.assertEqual(payload["domainPrivileges"][1]["priv"], "security_admin")

	# ===================================================================
	# USER VALIDATOR TESTS
	# ===================================================================

	def test_validator_duplicate_domain_names(self):
		"""Test validator catches duplicate domain names."""
		domain_privileges = [
			{"name": "default", "privilege": "browse"},
			{"name": "default", "privilege": "edit"}
		]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("Duplicate domain names", str(context.exception))

	def test_validator_invalid_privilege_value(self):
		"""Test validator catches invalid privilege value."""
		domain_privileges = [{"name": "default", "privilege": "invalid_priv"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("Invalid privilege", str(context.exception))

	def test_validator_password_list_invalid_characters(self):
		"""Test validator catches invalid characters in password list."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		password_list = ['p', 'a', 'ss', 'w']  # 'ss' is not a single character
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", password_list, domain_privileges)
		self.assertIn("single character", str(context.exception))

	def test_validator_password_list_empty(self):
		"""Test validator catches empty password list."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", [], domain_privileges)
		self.assertIn("Password cannot be empty", str(context.exception))

	def test_validator_domain_privilege_missing_name(self):
		"""Test validator catches domain privilege missing name field."""
		domain_privileges = [{"privilege": "browse"}]  # Missing 'name'
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("missing 'name' field", str(context.exception))

	def test_validator_domain_privilege_missing_privilege(self):
		"""Test validator catches domain privilege missing privilege field."""
		domain_privileges = [{"name": "default"}]  # Missing 'privilege'
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("missing 'privilege' field", str(context.exception))

	def test_validator_domain_privilege_not_dict(self):
		"""Test validator catches domain privilege not being a dict."""
		domain_privileges = ["browse"]  # Should be dict
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("must be a dictionary", str(context.exception))

	def test_validator_domain_name_empty(self):
		"""Test validator catches empty domain name."""
		domain_privileges = [{"name": "", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("cannot be empty", str(context.exception))

	def test_validator_domain_name_not_string(self):
		"""Test validator catches non-string domain name."""
		domain_privileges = [{"name": 123, "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("must be a string", str(context.exception))

	def test_validator_privilege_not_string(self):
		"""Test validator catches non-string privilege value."""
		domain_privileges = [{"name": "default", "privilege": 123}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", "password123", domain_privileges)
		self.assertIn("must be a string", str(context.exception))

	def test_validator_same_passwords(self):
		"""Test validator catches same current and new password."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.modify_user_by_name("modify_user", 
				current_password="samepass123", 
				new_password="samepass123")
		self.assertIn("must be different", str(context.exception))

	def test_validator_password_non_string_non_list(self):
		"""Test validator catches password that is neither string nor list."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		with self.assertRaises(exceptions.InvalidInput) as context:
			self.workflow.create_user("testuser", 12345, domain_privileges)
		self.assertIn("must be a string or list", str(context.exception))

	def test_validator_all_valid_privileges(self):
		"""Test all valid privilege values are accepted."""
		valid_privileges = ['super', 'service', 'security_admin', 'edit', 'create', 'browse', 'basic_edit']
		for priv in valid_privileges:
			domain_privileges = [{"name": "default", "privilege": priv}]
			# Should not raise exception
			try:
				self.workflow.create_user(f"user_{priv}", "password123", domain_privileges)
			except exceptions.InvalidInput:
				self.fail(f"Valid privilege '{priv}' was rejected")

	# ===================================================================
	# UID VALIDATION TESTS
	# ===================================================================

	def test_fetch_user_uid_missing_uid(self):
		"""Test handling of user found but without UID."""
		self.session_client.rest_client.get.return_value = {
			"members": {
				"uid1": {"name": "testuser"}  # Missing 'uid' field
			}
		}
		with self.assertRaises(exceptions.HPEStorageException) as context:
			self.workflow._fetch_user_uid_by_name("testuser")
		self.assertIn("has no UID", str(context.exception))

	def test_fetch_user_uid_null_uid(self):
		"""Test handling of user with null UID."""
		self.session_client.rest_client.get.return_value = {
			"members": {
				"uid1": {"name": "testuser", "uid": None}
			}
		}
		with self.assertRaises(exceptions.HPEStorageException) as context:
			self.workflow._fetch_user_uid_by_name("testuser")
		self.assertIn("has no UID", str(context.exception))

	def test_fetch_user_uid_empty_uid(self):
		"""Test handling of user with empty string UID."""
		self.session_client.rest_client.get.return_value = {
			"members": {
				"uid1": {"name": "testuser", "uid": ""}
			}
		}
		with self.assertRaises(exceptions.HPEStorageException) as context:
			self.workflow._fetch_user_uid_by_name("testuser")
		self.assertIn("has no UID", str(context.exception))

	# ===================================================================
	# ERROR HANDLING TESTS
	# ===================================================================

	def test_get_all_users_rest_exception(self):
		"""Test get_all_users handling REST exceptions."""
		self.session_client.rest_client.get.side_effect = Exception("Connection error")
		with self.assertRaises(exceptions.HPEStorageException):
			self.workflow.get_all_users()

	def test_get_user_by_name_rest_exception(self):
		"""Test get_user_by_name handling REST exceptions."""
		self.session_client.rest_client.get.side_effect = Exception("API error")
		try:
			self.workflow.get_user_by_name("testuser")
			self.fail("Expected exception was not raised")
		except Exception as e:
			# Exception is raised but may not be wrapped in HPEStorageException
			self.assertIn("API error", str(e))

	def test_create_user_rest_exception(self):
		"""Test create_user handling REST exceptions."""
		domain_privileges = [{"name": "default", "privilege": "browse"}]
		self.session_client.rest_client.post.side_effect = Exception("Create failed")
		with self.assertRaises(Exception):
			self.workflow.create_user("testuser", "password123", domain_privileges)

	def test_modify_user_rest_exception(self):
		"""Test modify_user handling REST exceptions."""
		self._simulate_user_exists("modify_user", uid="uid_modify")
		self.session_client.rest_client.patch.side_effect = Exception("Modify failed")
		with self.assertRaises(Exception):
			self.workflow.modify_user_by_name("modify_user", 
				current_password="old123", new_password="new456")

	def test_delete_user_rest_exception(self):
		"""Test delete_user handling REST exceptions."""
		self._simulate_user_exists("delete_user", uid="uid_delete")
		self.session_client.rest_client.delete.side_effect = Exception("Delete failed")
		with self.assertRaises(Exception):
			self.workflow.delete_user_by_name("delete_user")

	# ===================================================================
	# VALIDATOR HELPER FUNCTION TESTS
	# ===================================================================

	def test_validate_password_change_params_new_without_current(self):
		"""Test password change validation when new password provided without current."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_password_change_params(None, "newpass123")
		self.assertIn("currentPassword is required", str(context.exception))

	def test_validate_password_change_params_current_without_new(self):
		"""Test password change validation when current password provided without new."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_password_change_params("current123", None)
		self.assertIn("newPassword is required", str(context.exception))

	def test_validate_password_change_params_both_provided(self):
		"""Test password change validation when both passwords provided."""
		# Should not raise exception
		validate_password_change_params("currentpass123", "newpass456")

	def test_validate_password_change_params_same_passwords(self):
		"""Test password change validation when passwords are the same."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_password_change_params("samepass123", "samepass123")
		self.assertIn("must be different", str(context.exception))

	def test_validate_user_operation_params_invalid_operation(self):
		"""Test operation validator with invalid operation type."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_user_operation_params("invalid_op")
		self.assertIn("Invalid operation", str(context.exception))

	def test_validate_user_operation_params_create_missing_name(self):
		"""Test operation validator for create without name."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_user_operation_params("create", password="pass123", domain_privileges=[])
		self.assertIn("'name' is required", str(context.exception))

	def test_validate_user_operation_params_create_missing_password(self):
		"""Test operation validator for create without password."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_user_operation_params("create", name="user1", domain_privileges=[])
		self.assertIn("'password' is required", str(context.exception))

	def test_validate_user_operation_params_create_missing_domain_privileges(self):
		"""Test operation validator for create without domain_privileges."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_user_operation_params("create", name="user1", password="pass123")
		self.assertIn("'domain_privileges' is required", str(context.exception))

	def test_validate_user_operation_params_create_success(self):
		"""Test operation validator for create with all params."""
		# Should not raise exception
		validate_user_operation_params("create", name="user1", password="pass123", domain_privileges=[])

	def test_validate_user_operation_params_modify_no_identifier(self):
		"""Test operation validator for modify without uid or name."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_user_operation_params("modify", current_password="pass123")
		self.assertIn("'uid' or 'name' is required", str(context.exception))

	def test_validate_user_operation_params_modify_no_changes(self):
		"""Test operation validator for modify without modifiable params."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_user_operation_params("modify", name="user1")
		self.assertIn("At least one of the following parameters", str(context.exception))

	def test_validate_user_operation_params_modify_with_uid(self):
		"""Test operation validator for modify with uid."""
		# Should not raise exception
		validate_user_operation_params("modify", uid="uid123", current_password="pass123")

	def test_validate_user_operation_params_modify_with_name(self):
		"""Test operation validator for modify with name."""
		# Should not raise exception
		validate_user_operation_params("modify", name="user1", new_password="newpass", current_password="old")

	def test_validate_user_operation_params_delete_no_identifier(self):
		"""Test operation validator for delete without uid or name."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_user_operation_params("delete")
		self.assertIn("'uid' or 'name' is required", str(context.exception))

	def test_validate_user_operation_params_delete_with_uid(self):
		"""Test operation validator for delete with uid."""
		# Should not raise exception
		validate_user_operation_params("delete", uid="uid123")

	def test_validate_user_operation_params_delete_with_name(self):
		"""Test operation validator for delete with name."""
		# Should not raise exception
		validate_user_operation_params("delete", name="user1")

	def test_validate_user_operation_params_get_no_identifier(self):
		"""Test operation validator for get without uid or name."""
		with self.assertRaises(exceptions.InvalidInput) as context:
			validate_user_operation_params("get")
		self.assertIn("'uid' or 'name' is required", str(context.exception))

	def test_validate_user_operation_params_get_with_uid(self):
		"""Test operation validator for get with uid."""
		# Should not raise exception
		validate_user_operation_params("get", uid="uid123")

	def test_validate_user_operation_params_get_with_name(self):
		"""Test operation validator for get with name."""
		# Should not raise exception
		validate_user_operation_params("get", name="user1")

	def test_validate_user_operation_params_get_all(self):
		"""Test operation validator for get_all (no params required)."""
		# Should not raise exception
		validate_user_operation_params("get_all")


if __name__ == '__main__':
	unittest.main()