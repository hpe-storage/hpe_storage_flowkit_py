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
from hpe_storage_flowkit_py.v1.src.workflows.cpg import CPGWorkflow

class MockHTTPClient:
	def post(self, endpoint, payload):
		return {"status": "created", "payload": payload}
	def delete(self, endpoint):
		return {"status": "deleted", "endpoint": endpoint}
	def get(self, endpoint):
		if endpoint == "/cpgs":
			return {"members": ["cpg1", "cpg2"]}
		return {"status": "fetched", "endpoint": endpoint}

class TestCPGWorkflow(unittest.TestCase):
	def setUp(self):
		self.workflow = CPGWorkflow(MockHTTPClient())

	def test_create_cpg_success(self):
		result = self.workflow.create_cpg("cpg1", {"domain": "test"})
		self.assertEqual(result["status"], "created")
		self.assertEqual(result["payload"]["name"], "cpg1")

	def test_create_cpg_invalid_name(self):
		with self.assertRaises(ValueError):
			self.workflow.create_cpg("", {"domain": "test"})

	def test_delete_cpg(self):
		result = self.workflow.delete_cpg("cpg1")
		self.assertEqual(result["status"], "deleted")

	def test_get_cpg(self):
		result = self.workflow.get_cpg("cpg1")
		self.assertEqual(result["status"], "fetched")

	def test_list_cpgs(self):
		result = self.workflow.list_cpgs()
		self.assertIn("cpg1", result)
		self.assertIn("cpg2", result)

if __name__ == "__main__":
	unittest.main()
