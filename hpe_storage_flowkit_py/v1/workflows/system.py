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

from hpe_storage_flowkit_py.v1.src.core.exceptions import HPEStorageException
from hpe_storage_flowkit_py.v1.src.core.session import SessionManager


class SystemWorkflow:
	def __init__(self, session_mgr: SessionManager):
		self.session_mgr = session_mgr

	def get_storage_system_info(self):
		"""Get the Storage System Information."""
		try:
			response = self.session_mgr.rest_client.get(f"/system")
			return response
		except HPEStorageException as e:
			raise

	def get_ws_api_version(self):
		try:
			response = self.session_mgr.rest_client.get_api_version(f"/api")
			return response
		except HPEStorageException as e:
			raise

