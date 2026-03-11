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

from hpe_storage_flowkit_py.v3.src.core.exceptions import HostAlreadyExists
from hpe_storage_flowkit_py.v3.src.core.exceptions import HostDoesNotExist
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.validators.host_validator import validate_host_params
from hpe_storage_flowkit_py.v3.src.validators.host_validator import validate_host_optional_params
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
logger = Logger()
class HostWorkflow:

	def __init__(self, session_mgr: SessionManager):
		self.session_mgr = session_mgr

	def _execute_create_host(self, name, **kwargs):
		"""
		Execute host creation with payload for HPE 3PAR SSMC API.
		
		Required parameters:
		- name: Name of the host to be created
		"""
		try:
			# Validate required parameters
			validate_host_params(name)
			if self._host_exists(name):
				logger.error(f"Host '{name}' already exists")
				raise HostAlreadyExists(name=name)
			
			# Build the base payload with required fields
			payload = {
				"name": name
			}
			
			# Process optional parameters directly from kwargs
			opt_params = {}
			if kwargs:
				opt_params = {k: v for k, v in kwargs.items() if v is not None}
			if opt_params:
				validate_host_optional_params(opt_params)
				payload.update(opt_params)
			logger.info(f"Host creation payload: {payload}")
			
			response = self.session_mgr.rest_client.post(f"/hosts", payload)
			return response
		except Exception as e:
			# Log the error
			logger.error(f"Host creation failed: {e}")
			raise


	def create_host(self, name, **kwargs):
		try:
			response = self._execute_create_host(name, **kwargs)
			return response
		except Exception as e:
			raise

	
	def _host_exists(self, name):
		try:
			uid = self._get_host_uid("name", name)

			return uid is not None
		except Exception as e:
			logger.debug(f"_host_exists check failed for '{name}': {e}")
			raise
	
	
	def delete_host(self, hostName):
		uid = self._get_host_uid("name", hostName)
		if uid is not None:
			try:
				response = self.session_mgr.rest_client.delete(f"/hosts/{uid}")
				return response
			except Exception as e:
				logger.error(f"Host deletion failed: {e}")
				raise
		else:
			logger.error(f"Host '{hostName}' does not exist")
			raise HostDoesNotExist(name=hostName)


	def _get_host_uid(self, queryKey, queryValue):
		if queryKey is not None and queryValue is not None:
			try:
				headers = {'experimentalfilter': 'true'}
				uri = f"/hosts?{queryKey}={queryValue}"
				response = self.session_mgr.rest_client.get(uri, headers=headers)
				members = self.normalize_members(response)
				if members:
					return members[0].get("uid")
			except Exception as e:
				logger.error(f"Fetching Host UID failed: {e}")
				raise
		else:
			return None


	def get_host(self, queryKey, queryValue):
		if queryKey is not None and queryValue is not None:
			try:
				headers = {'experimentalfilter': 'true'}
				uri = f"/hosts?{queryKey}={queryValue}"
				response = self.session_mgr.rest_client.get(uri, headers=headers)
				members = self.normalize_members(response)
				if not members:
					raise HostDoesNotExist(name=queryValue)
				host_paths = self._get_host_paths()
				filtered = []
				for host_path in host_paths:
					if not isinstance(host_path, dict):
						continue
					if host_path.get("hostName") != members[0].get("name"):
						continue
					filtered.append({
						"IPAddr": host_path.get("IPAddr", ""),
						"address": host_path.get("address", ""),
						"pathType": host_path.get("pathType", ""),
						"portPos": {
							"node": host_path.get("portPos", {}).get("node"),
							"slot": host_path.get("portPos", {}).get("slot"),
							"port": host_path.get("portPos", {}).get("port")
						}
					})
				
				members[0]["paths"] = filtered
				final_response = members[0]
				
				return final_response
			except Exception as e:
				logger.error(f"Fetching Host failed: {e}")
				raise
		return None
	

	def _get_host_paths(self):
		try:
			headers = {'experimentalfilter': 'false'}
			response = self.session_mgr.rest_client.get(f"/hostpaths", headers=headers)
			members = self.normalize_members(response)
			if not members:
				raise ValueError("Invalid hostPaths response format")
			
			return members

		except Exception as e:
			logger.error(f"Fetching Host Paths failed: {e}")
			raise


	def get_hosts(self):
		try:
			response = self.session_mgr.rest_client.get(f"/hosts")
			members = self.normalize_members(response)
			if not members:
				raise ValueError("Invalid hosts response format")
			
			host_paths = self._get_host_paths()
			
			for member in members:
				if not isinstance(member, dict):
					continue
				filtered = []
				for host_path in host_paths:
					if not isinstance(host_path, dict):
						continue
					if host_path.get("hostName") != member.get("name"):
						continue
					filtered.append({
						"IPAddr": host_path.get("IPAddr", ""),
						"address": host_path.get("address", ""),
						"pathType": host_path.get("pathType", ""),
						"portPos": {
							"node": host_path.get("portPos", {}).get("node"),
							"slot": host_path.get("portPos", {}).get("slot"),
							"port": host_path.get("portPos", {}).get("port")
						}
					})
				
				member["paths"] = filtered
			
			return members
		except Exception as e:
				logger.error(f"Fetching Hosts failed: {e}")
				raise


	def get_host_by_iqn_wwn_nqn(self, iqnOrwwnOrnqn=None):
		try:
			headers = {'experimentalfilter': 'false'}
			response = self.session_mgr.rest_client.get(f"/hostpaths", headers=headers)
			members = self.normalize_members(response)
			if not members:
				raise ValueError("Invalid hostPaths response format")
		
			for member in members:
				if not isinstance(member, dict):
					continue		
				if iqnOrwwnOrnqn and member.get("address") == iqnOrwwnOrnqn:
					queryKey = "name"
					queryValue = member.get("hostName")
					headersNew = {'experimentalfilter': 'true'}
				
					uri = f"/hosts?{queryKey}={queryValue}"
					response = self.session_mgr.rest_client.get(uri, headers=headersNew)

					return response[0]

		except Exception as e:
			logger.error(f"Fetching Host based on IQN, WWN, NQN failed: {e}")
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


