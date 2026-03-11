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
from hpe_storage_flowkit_py.v1.src.workflows.volume import VolumeWorkflow
from hpe_storage_flowkit_py.v1.src.validators.volume_validator import validate_volume_params

class MockHTTPClient:
	def post(self, endpoint, payload):
		return {"status": "created", "payload": payload}
	def delete(self, endpoint):
		return {"status": "deleted", "endpoint": endpoint}
	def get(self, endpoint):
		if endpoint == "/volumes":
			return {"members": ["vol1", "vol2"]}
		return {"status": "fetched", "endpoint": endpoint}

class TestVolumeWorkflow(unittest.TestCase):
	def setUp(self):
		self.workflow = VolumeWorkflow(MockHTTPClient())

	def test_create_volume_success(self):
		result = self.workflow.create_volume("vol1", 1024, "CPG1")
		self.assertEqual(result["status"], "created")
		self.assertEqual(result["payload"]["name"], "vol1")

	def test_create_volume_invalid_name(self):
		with self.assertRaises(ValueError):
			self.workflow.create_volume("", 1024, "CPG1")

	def test_delete_volume(self):
		result = self.workflow.delete_volume("vol1")
		self.assertEqual(result["status"], "deleted")

	def test_get_volume(self):
		result = self.workflow.get_volume("vol1")
		self.assertEqual(result["status"], "fetched")

	def test_list_volumes(self):
		result = self.workflow.list_volumes()
		self.assertIn("vol1", result)
		self.assertIn("vol2", result)

	def test_create_volume_with_extra_params(self):
		result = self.workflow.create_volume("vol2", 2048, "CPG2", comment="Test volume", provisioningType="thin")
		self.assertEqual(result["payload"]["comment"], "Test volume")
		self.assertEqual(result["payload"]["provisioningType"], "thin")

	def test_create_volume_invalid_size(self):
		with self.assertRaises(ValueError):
			self.workflow.create_volume("vol3", -100, "CPG1")

	def test_create_volume_invalid_cpg(self):
		with self.assertRaises(ValueError):
			self.workflow.create_volume("vol4", 100, 123)

	def test_delete_volume_invalid_name(self):
		with self.assertRaises(ValueError):
			self.workflow.delete_volume("")

	def test_get_volume_invalid_name(self):
		with self.assertRaises(ValueError):
			self.workflow.get_volume("")

	def test_integration_create_and_delete(self):
		# Simulate create and delete sequence
		create_result = self.workflow.create_volume("vol5", 512, "CPG3")
		self.assertEqual(create_result["status"], "created")
		delete_result = self.workflow.delete_volume("vol5")
		self.assertEqual(delete_result["status"], "deleted")

if __name__ == "__main__":
	unittest.main()
