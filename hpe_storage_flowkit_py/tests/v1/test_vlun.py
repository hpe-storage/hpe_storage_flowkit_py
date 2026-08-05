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
from hpe_storage_flowkit_py.v1.src.workflows.vlun import VLUNWorkflow
from hpe_storage_flowkit_py.v1.src.validators.vlun_validator import validate_vlun_params

class MockSessionClient:
	"""Lightweight stand-in for SessionManager used by VLUNWorkflow."""
	def __init__(self):
		# VLUNWorkflow expects `session_client.rest_client`, so point rest_client to self
		self.rest_client = self

	def post(self, endpoint, payload):
		# Ensure all keys match workflow expectations
		response = {"status": "created", "endpoint": endpoint, "payload": payload}
		# Use correct keys for hostsetName and volumeSetName
		if "hostsetName" in payload:
			response["payload"].setdefault("hostsetName", payload["hostsetName"])
		if "volumeSetName" in payload:
			response["payload"].setdefault("volumeSetName", payload["volumeSetName"])
		if "hostname" in payload:
			response["payload"].setdefault("hostname", payload["hostname"])
		if "autoLun" in payload:
			response["payload"].setdefault("autoLun", payload["autoLun"])
		if "lun" in payload:
			response["payload"].setdefault("lun", payload["lun"])
		if "volumeName" in payload:
			response["payload"].setdefault("volumeName", payload["volumeName"])
		return response

	def get(self, endpoint):
		# Simulate list_vluns and get_vlun
		if endpoint.startswith("/vluns/"):
			return {"status": "fetched", "endpoint": endpoint, "vlun": {
				"id": endpoint.split('/')[-1],
				"volumeName": "vol1",
				"lun": 10,
				"hostname": "host1",
				"hostsetName": "hostset1",
				"volumeSetName": "volset1"
			}}
		elif endpoint == "/vluns":
			# Use 'members' key for workflow compatibility
			return {"status": "fetched", "endpoint": endpoint, "members": [
				{"volumeName": "vol1", "hostname": "host1", "lun": 10, "hostsetName": "hostset1", "volumeSetName": "volset1"},
				{"volumeName": "vol2", "hostname": "host2", "lun": 20, "hostsetName": "hostset2", "volumeSetName": "volset2"},
				{"volumeSetName": "volset1", "hostname": "host1", "lun": 7, "volumeName": "vol1", "hostsetName": "hostset1"},
				{"volumeSetName": "volset1", "hostsetName": "hostset1", "lun": 8, "volumeName": "vol1", "hostname": "host1"},
				{"volumeName": "vol1", "hostsetName": "hostset1", "lun": 5, "hostname": "host1"},  # For hostset unexport test
				{"volumeName": "vol1", "hostsetName": "hostset1", "lun": 5, "hostname": "hostset1"}  # For unexport_volume_from_hostset test
			]}
		return {"status": "fetched", "endpoint": endpoint}

	def delete(self, endpoint):
		return {"status": "deleted", "endpoint": endpoint}

class TestVLUNWorkflow(unittest.TestCase):
	def test_unexport_volume_from_host(self):
		# VLUNWorkflow.unexport_volume_from_host expects a VLUN ID string
		vlun_id = "vol1,10,host1"
		result = self.workflow.unexport_volume_from_host(vlun_id)
		self.assertEqual(result["status"], "deleted")

	def test_export_volume_to_hostset(self):
		payload = {"volumeName": "vol1", "hostsetName": "hostset1", "lun": 5, "autoLun": False}
		result = self.workflow.export_volume_to_hostset(payload)
		self.assertEqual(result["status"], "created")
		self.assertEqual(result["payload"]["volumeName"], "vol1")
		self.assertEqual(result["payload"]["hostsetName"], "hostset1")

	def test_unexport_volume_from_hostset(self):
		vlun_id = "vol1,5,hostset1"
		result = self.workflow.unexport_volume_from_hostset(vlun_id)
		self.assertEqual(result["status"], "deleted")

	def test_export_volumeset_to_host(self):
		payload = {"volumeSetName": "volset1", "hostname": "host1", "lun": 7, "autoLun": False}
		result = self.workflow.export_volumeset_to_host(payload)
		self.assertEqual(result["status"], "created")
		self.assertEqual(result["payload"]["volumeSetName"], "volset1")
		self.assertEqual(result["payload"]["hostname"], "host1")

	def test_unexport_volumeset_from_host(self):
		vlun_id = "volset1,7,host1"
		result = self.workflow.unexport_volumeset_from_host(vlun_id)
		self.assertEqual(result["status"], "deleted")

	def test_export_volumeset_to_hostset(self):
		payload = {"volumeSetName": "volset1", "hostsetName": "hostset1", "lun": 8, "autoLun": False}
		result = self.workflow.export_volumeset_to_hostset(payload)
		self.assertEqual(result["status"], "created")
		self.assertEqual(result["payload"]["volumeSetName"], "volset1")
		self.assertEqual(result["payload"]["hostsetName"], "hostset1")

	def test_unexport_volumeset_from_hostset(self):
		vlun_id = "volset1,8,hostset1"
		result = self.workflow.unexport_volumeset_from_hostset(vlun_id)
		self.assertEqual(result["status"], "deleted")

	def test_vlun_exists(self):
		exists = self.workflow.vlun_exists("vol1", 10, "host1")
		self.assertIsInstance(exists, bool)

	def test_get_vlun(self):
		result = self.workflow.get_vlun("vol1,10,host1")
		self.assertEqual(result["status"], "fetched")
		self.assertIn("vlun", result)

	def test_list_vluns(self):
		result = self.workflow.list_vluns()
		self.assertIsInstance(result, list)
		self.assertGreaterEqual(len(result), 1)
	def setUp(self):
		self.workflow = VLUNWorkflow(MockSessionClient())

	def test_export_volume_to_host_autolun(self):
		payload = {"volumeName": "vol1", "hostname": "host1", "autoLun": True}
		result = self.workflow.export_volume_to_host(payload)
		self.assertEqual(result["status"], "created")
		self.assertEqual(result["payload"]["volumeName"], "vol1")
		self.assertEqual(result["payload"]["hostname"], "host1")
		self.assertTrue(result["payload"]["autoLun"])

	def test_export_volume_to_host_with_lun(self):
		payload = {"volumeName": "vol2", "hostname": "host2", "lun": 10, "autoLun": False}
		result = self.workflow.export_volume_to_host(payload)
		self.assertEqual(result["status"], "created")
		self.assertEqual(result["payload"]["lun"], 10)
		self.assertFalse(result["payload"]["autoLun"])

	def test_export_volume_to_host_invalid(self):
		# Workflow itself does not validate values; ensure it still accepts payload
		payload = {"volumeName": "", "hostname": "host1", "autoLun": True}
		result = self.workflow.export_volume_to_host(payload)
		self.assertEqual(result["status"], "created")

	def test_validate_vlun_params(self):
		# Valid combinations should not raise
		validate_vlun_params("vol1")
		validate_vlun_params("vol1", "host1")
		validate_vlun_params("vol1", "host1", {"key": "value"})
		# Invalid non-str/dict argument should raise
		with self.assertRaises(ValueError):
			validate_vlun_params("vol1", "host1", 0)

if __name__ == "__main__":
	unittest.main()
