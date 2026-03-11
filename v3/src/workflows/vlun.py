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
from hpe_storage_flowkit_py.v3.src.validators.vlun_validator import validate_vlun_params
from hpe_storage_flowkit_py.v3.src.validators.vlun_validator import validate_vlun_optional_params
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
logger = Logger()
class VLunWorkflow:

	def __init__(self, session_mgr: SessionManager):
		self.session_mgr = session_mgr

	def _execute_create_vlun(self, volname, hostname, **kwargs):
		"""
		Execute vlun creation with payload for HPE 3PAR SSMC API.
		
		Required parameters:
		- volname: Name of the volume to be exported
		- hostname: Name of the host to export to.
		"""
		try:
			# Validate required parameters
			validate_vlun_params(volname, hostname)
			
			# Build the base payload with required fields
			payload = {
				"volumeName": volname,
				"hostName": hostname
			}
			# Process optional parameters directly from kwargs
			opt_params = {}
			if kwargs:
				opt_params = {k: v for k, v in kwargs.items() if v is not None}
			if opt_params:
				validate_vlun_optional_params(opt_params)
			
			payload.update(opt_params)
			logger.info(f"VLun creation payload: {payload}")
			
			response = self.session_mgr.rest_client.post(f"/vluns", payload)
			return response
		except Exception as e:
			# Log the error
			logger.error(f"VLun creation failed: {e}")
			raise


	def create_vlun(self, volname, hostname, **kwargs):
		try:
			response = self._execute_create_vlun(volname, hostname, **kwargs)
			return response
		except Exception as e:
			raise

	
	def delete_vlun(self, volname, lun, hostname=None, port=None):
		uids = self._get_vlun_uids(volname, lun, hostname, port)
		logger.info(f"Retrieved VLUN UIDs: {uids}")
		responses = []
		if isinstance(uids, list) and uids:
			for uid in uids:
				try:
					response = self.session_mgr.rest_client.delete(f"/vluns/{uid}")
					logger.info(f"Deleted VLUN with UID: {uid}")
					responses.append(response)

				except Exception as e:
					logger.error(f"VLUN deletion failed for UID {uid}: {e}")
					raise
			return responses
		else:
			logger.error(f"VLUN UIDs not found for volume '{volname}' and LUN '{lun}'")
			return None
		
    	
	def _get_vlun_uids(self, volname, lun, hostname, port):
		if volname is not None and lun is not None:
			try:
				query = f"volumeName={volname}&lun={str(lun)}"
				if hostname is not None:
					query += f"&hostName={hostname}"
				if port is not None:
					query += f"&portPos={port}"
				
				headers = {'experimentalfilter': 'true'}
				uri = f"/vluns?{query}"
				response = self.session_mgr.rest_client.get(uri, headers=headers)

				members = self.normalize_members(response)
				if members:
					return [item["uid"] for item in response if "uid" in item]

			except Exception as e:
				logger.error(f"Fetching VLun UIDs failed: {e}")
				raise
		else:
			return None


	def get_vlun(self, queryKey, queryValue):
		if queryKey is not None and queryValue is not None:
			try:
				headers = {'experimentalfilter': 'true'}
				uri = f"/vluns?{queryKey}={queryValue}"
				response = self.session_mgr.rest_client.get(uri, headers=headers)
				members = self.normalize_members(response)
				if not members:
					raise ValueError("Invalid vlun response format")

				return members
			except Exception as e:
				logger.error(f"Fetching VLun failed: {e}")
				raise
		return None
	

	def get_vluns(self):
		try:
			response = self.session_mgr.rest_client.get(f"/vluns")
			members = self.normalize_members(response)
			if not members:
				raise ValueError("Invalid vluns response format")
			return members
		except Exception as e:
				logger.error(f"Fetching VLuns failed: {e}")
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

	

