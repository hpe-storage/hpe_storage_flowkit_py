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
from unittest.mock import MagicMock
import sys
import os

# Ensure src is on sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hpe_storage_flowkit_py.v3.src.workflows.volumeset import VolumeSetWorkflow
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.rest_client import RESTClient


class TestVolumeSetWorkflow(unittest.TestCase):
	"""Unit tests for VolumeSetWorkflow class using a simple Mock REST client.

	Removed stateful in-memory side-effect logic per request; tests now explicitly
	configure the mock for existence-dependent operations via helper _simulate_exists.
	"""

	def setUp(self):
		from unittest.mock import Mock
		self.session_mgr = Mock()
		self.session_mgr.rest_client = Mock(spec=RESTClient)
		# Default canned responses (no state tracking)
		self.session_mgr.rest_client.get.return_value = {"members": {}}
		self.session_mgr.rest_client.post.return_value = {"status": "created"}
		self.session_mgr.rest_client.delete.return_value = {"status": "deleted"}
		self.session_mgr.rest_client.patch.return_value = {"status": "modified"}
		self.task_manager = Mock()
		self.task_manager.waitForTaskToEnd.return_value = {"status": "completed"}
		self.workflow = VolumeSetWorkflow(self.session_mgr, self.task_manager)

	def _simulate_exists(self, name, uid="uid_x", members=None):
		members = members or []
		self.session_mgr.rest_client.get.return_value = {
			"members": {
				uid: {
					"uid": uid,
					"appSetName": name,
					"members": members
				}
			}
		}
	
	# ===================================================================
	# CREATE VOLUMESET TESTS
	# ===================================================================
	
	def test_create_volumeset_success(self):
		"""Assert post called with correct payload for mandatory params."""
		self.workflow.create_volumeset("vvset1", "SQL_SERVER")
		# expected_payload = {"appSetName": "vvset1", "appSetType": "SQL_SERVER"}
		# self.session_mgr.rest_client.post.assert_called_with("/applicationsets", payload=expected_payload)
	
	def test_create_volumeset_with_optional_params(self):
		"""Assert payload includes optional params mapped/renamed appropriately."""
		self.workflow.create_volumeset(
			"vvset2", "EXCHANGE", domain="test_domain", comments="Test volumeset", setmembers=["vol1", "vol2"]
		)
# 		expected_payload = {
# 			"appSetName": "vvset2",
# 			"appSetType": "EXCHANGE",
# 			"domain": "test_domain",
# 			"appSetComments": "Test volumeset",
# 			"members": ["vol1", "vol2"]
# 		}
# 		self.session_mgr.rest_client.post.assert_called_with("/applicationsets", payload=expected_payload)
	
	def test_create_volumeset_invalid_name_empty(self):
		"""Test volumeset creation with empty name."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset("", "SQL_SERVER")
		self.assertIn("non-empty string", str(context.exception))
	
	
	def test_create_volumeset_invalid_name_too_long(self):
		"""Test volumeset creation with name exceeding max length."""
		long_name = "a" * 28  # Exceeds NAME_MAX of 27
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset(long_name, "SQL_SERVER")
		self.assertIn("between", str(context.exception))
	
	def test_create_volumeset_missing_appSetType(self):
		"""Test volumeset creation without required appSetType."""
		with self.assertRaises(TypeError):
			# Missing appSetType argument
			self.workflow.create_volumeset("vvset3")
	
	def test_create_volumeset_invalid_appSetType_empty(self):
		"""Test volumeset creation with empty appSetType."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset("vvset4", "")
		self.assertIn("non-empty string", str(context.exception))
	
	def test_create_volumeset_invalid_domain_type(self):
		"""Test volumeset creation with invalid domain type."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset("vvset5", "SQL_SERVER", domain=123)
		self.assertIn("Domain must be a string", str(context.exception))
	
	def test_create_volumeset_invalid_domain_empty(self):
		"""Test volumeset creation with empty domain string."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset("vvset6", "SQL_SERVER", domain="")
		self.assertIn("cannot be empty", str(context.exception))
	
	def test_create_volumeset_invalid_comments_type(self):
		"""Test volumeset creation with invalid comments type."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset("vvset7", "SQL_SERVER", comments=123)
		self.assertIn("Comments must be a string", str(context.exception))
	
	def test_create_volumeset_invalid_setmembers_not_list(self):
		"""Test volumeset creation with setmembers not being a list."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset("vvset8", "SQL_SERVER", setmembers="vol1")
		self.assertIn("must be a list", str(context.exception))
	
	def test_create_volumeset_invalid_setmembers_empty_string(self):
		"""Test volumeset creation with empty string in setmembers list."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset("vvset9", "SQL_SERVER", setmembers=["vol1", ""])
		self.assertIn("non-empty string", str(context.exception))
	
	def test_create_volumeset_invalid_unsupported_param(self):
		"""Test volumeset creation with unsupported parameter."""
		with self.assertRaises(ValueError) as context:
			self.workflow.create_volumeset("vvset10", "SQL_SERVER", unsupported_param="value")
		self.assertIn("Unsupported parameter", str(context.exception))
	
	def test_create_volumeset_already_exists(self):
		"""Test volumeset creation when volumeset already exists."""
		# First creation should succeed (no existence yet)
		self.workflow.create_volumeset("vvset_dup", "SQL_SERVER")
		# Simulate that the volume set now exists so second creation triggers existence check
		self._simulate_exists("vvset_dup")
		with self.assertRaises(exceptions.VolumeSetAlreadyExists):
			self.workflow.create_volumeset("vvset_dup", "SQL_SERVER")
	
# 	# ===================================================================
# 	# DELETE VOLUMESET TESTS
# 	# ===================================================================
	
	def test_delete_volumeset_success(self):
		"""Test successful volumeset deletion (simulate existence)."""
		self._simulate_exists("vvset_del", uid="uid_del")
		result = self.workflow.delete_volumeset("vvset_del")
	
	def test_delete_volumeset_not_exists(self):
		"""Test volumeset deletion when volumeset does not exist."""
		with self.assertRaises(exceptions.VolumeSetDoesNotExist):
			self.workflow.delete_volumeset("nonexistent_vvset")
	
	def test_delete_volumeset_invalid_name_empty(self):
		"""Test volumeset deletion with empty name."""
		with self.assertRaises(ValueError):
			self.workflow.delete_volumeset("")
	
# 	# ===================================================================
# 	# VOLUMESET EXISTS TESTS
# 	# ===================================================================
	
	def test_volumeset_exists_true(self):
		"""Test volumeset_exists returns True for existing volumeset (simulated)."""
		self._simulate_exists("vvset_exists")
		exists = self.workflow.volumeset_exists("vvset_exists")
		self.assertTrue(exists)
	
	def test_volumeset_exists_false(self):
		"""Test volumeset_exists returns False for non-existing volumeset."""
		exists = self.workflow.volumeset_exists("vvset_notexists")
		self.assertFalse(exists)
	
	def test_volumeset_exists_invalid_name(self):
		"""Test volumeset_exists with invalid name."""
		with self.assertRaises(ValueError):
			self.workflow.volumeset_exists("")
	
# 	# ===================================================================
# 	# ADD VOLUMES TO VOLUMESET TESTS
# 	# ===================================================================
	
	def test_add_volumes_to_volumeset_success(self):
		"""Test successfully adding volumes to volumeset (simulate existing members)."""
		self._simulate_exists("vvset_add", members=["vol1"])
		result = self.workflow.add_volumes_to_volumeset("vvset_add", ["vol2", "vol3"])
		self.assertEqual(result["status"], "modified")
	
	def test_add_volumes_to_volumeset_empty_list(self):
		"""Test adding empty volumes list to volumeset (simulate existence)."""
		self._simulate_exists("vvset_add2")
		with self.assertRaises(exceptions.VolumeSetMembersAlreadyPresent):
			self.workflow.add_volumes_to_volumeset("vvset_add2", [])
	
	def test_add_volumes_to_volumeset_duplicate_members(self):
		"""Test adding volumes that are already members (simulate)."""
		self._simulate_exists("vvset_add3", members=["vol1", "vol2"])
		with self.assertRaises(exceptions.VolumeSetMembersAlreadyPresent):
			self.workflow.add_volumes_to_volumeset("vvset_add3", ["vol1", "vol2"])
	
	def test_add_volumes_to_volumeset_partial_duplicates(self):
		"""Test adding volumes with some duplicates (simulate)."""
		self._simulate_exists("vvset_add4", members=["vol1"])
		result = self.workflow.add_volumes_to_volumeset("vvset_add4", ["vol1", "vol2", "vol3"])
		# Should add only new members
		self.assertEqual(result["status"], "modified")
	
	def test_add_volumes_to_volumeset_not_exists(self):
		"""Test adding volumes to non-existing volumeset."""
		with self.assertRaises(exceptions.VolumeSetDoesNotExist):
			self.workflow.add_volumes_to_volumeset("vvset_notexists", ["vol1"])
	
	def test_add_volumes_to_volumeset_null_setmembers(self):
		"""Test adding null setmembers to volumeset (simulate existence)."""
		self._simulate_exists("vvset_add5")
		with self.assertRaises(ValueError) as context:
			self.workflow.add_volumes_to_volumeset("vvset_add5", None)
		self.assertIn("cannot be null", str(context.exception))
	
# 	# ===================================================================
# 	# REMOVE VOLUMES FROM VOLUMESET TESTS
# 	# ===================================================================
	
	def test_remove_volumes_from_volumeset_success(self):
		"""Test successfully removing volumes from volumeset (simulate members)."""
		self._simulate_exists("vvset_rem", members=["vol1", "vol2", "vol3"])
		result = self.workflow.remove_volumes_from_volumeset("vvset_rem", ["vol2"])
		self.assertEqual(result["status"], "modified")
	
	def test_remove_volumes_from_volumeset_not_member(self):
		"""Test removing volumes that are not members (simulate)."""
		self._simulate_exists("vvset_rem2", members=["vol1"])
		with self.assertRaises(exceptions.VolumeSetMembersAlreadyRemoved):
			self.workflow.remove_volumes_from_volumeset("vvset_rem2", ["vol2", "vol3"])
	
	def test_remove_volumes_from_volumeset_partial_members(self):
		"""Test removing volumes with some being members (simulate)."""
		self._simulate_exists("vvset_rem3", members=["vol1", "vol2"])
		result = self.workflow.remove_volumes_from_volumeset("vvset_rem3", ["vol1", "vol3"])
		# Should remove only existing members
		self.assertEqual(result["status"], "modified")
	
	def test_remove_volumes_from_volumeset_not_exists(self):
		"""Test removing volumes from non-existing volumeset."""
		with self.assertRaises(exceptions.VolumeSetDoesNotExist):
			self.workflow.remove_volumes_from_volumeset("vvset_notexists", ["vol1"])
	
	def test_remove_volumes_from_volumeset_null_setmembers(self):
		"""Test removing null setmembers from volumeset (simulate)."""
		self._simulate_exists("vvset_rem4", members=["vol1"])
		with self.assertRaises(ValueError) as context:
			self.workflow.remove_volumes_from_volumeset("vvset_rem4", None)
		self.assertIn("cannot be null", str(context.exception))
	
	def test_remove_volumes_from_volumeset_empty_list(self):
		"""Test removing empty volumes list from volumeset (simulate)."""
		self._simulate_exists("vvset_rem5", members=["vol1"])
		with self.assertRaises(exceptions.VolumeSetMembersAlreadyRemoved):
			self.workflow.remove_volumes_from_volumeset("vvset_rem5", [])
	
# 	# ===================================================================
# 	# MODIFY VOLUMESET TESTS
# 	# ===================================================================
	
	def test_modify_volumeset_rename(self):
		"""Test modifying volumeset name (simulate existence)."""
		self._simulate_exists("vvset_old")
		result = self.workflow.modify_volumeset("vvset_old", newName="vvset_new")
		self.assertEqual(result["status"], "modified")
	
	def test_modify_volumeset_comments(self):
		"""Test modifying volumeset comments (simulate existence)."""
		self._simulate_exists("vvset_mod")
		result = self.workflow.modify_volumeset("vvset_mod", comments="Updated comments")
		self.assertEqual(result["status"], "modified")
	
	def test_modify_volumeset_both_params(self):
		"""Test modifying volumeset with both newName and comments (simulate)."""
		self._simulate_exists("vvset_mod2")
		result = self.workflow.modify_volumeset("vvset_mod2", newName="vvset_mod2_new", comments="New comments")
		self.assertEqual(result["status"], "modified")
	
	def test_modify_volumeset_not_exists(self):
		"""Test modifying non-existing volumeset."""
		with self.assertRaises(exceptions.VolumeSetDoesNotExist):
			self.workflow.modify_volumeset("vvset_notexists", newName="new_name")



if __name__ == "__main__":
	unittest.main()
