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
from typing import Any, List, Dict

from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
logger = Logger()
class PortWorkflow:

	def __init__(self, session_mgr: SessionManager):
		self.session_mgr = session_mgr	
    

	def get_ports(self):
		try:
			response = self.session_mgr.rest_client.get(f"/ports")
			members = self.normalize_members(response)

			if not members:
				raise ValueError("Invalid ports response format")
			
			return members
		except Exception as e:
				logger.error(f"Fetching Ports failed: {e}")
				raise

	@staticmethod
	def normalize_members(response: Any) -> List[Dict]:
		"""
		Normalize API responses that may be in one of several shapes:
    		- dict with key "members" as dict: return list(members.values())
    		- dict with key "members" as list: return that list
    		- plain list: return as-is
    		- otherwise: return empty list
    	"""
		if isinstance(response, dict):
			members = response.get("members")
			if isinstance(members, dict):
				return list(members.values())
			if isinstance(members, list):
				return members
			return []
		if isinstance(response, list):
			return response
		return []

	

