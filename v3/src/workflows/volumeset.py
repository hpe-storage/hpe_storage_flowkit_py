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
"""Volume Set workflow implementation (v3 consolidated).

This module provides end-to-end operations for volume sets in a single file:
  - Pre-processing & validation helpers
  - REST payload construction
  - Post-processing / uniform error handling

Endpoint assumptions (same as legacy implementation):
  POST   /volumesets                -> create volume set
  GET    /volumesets/{name}         -> get a volume set
  GET    /volumesets                -> list volume sets
  DELETE /volumesets/{name}         -> delete volume set
  PUT    /volumesets/{name}         -> modify (add/remove members via action flag)

Action codes (legacy parity):
  action = 1 -> add members
  action = 2 -> remove members

Return convention:
  On success: raw RESTClient parsed response
  On failure (caught exception): (False, False, <friendly_message>, {})

NOTE: The validator file for volume sets is currently empty; minimal inline
	  validation is performed here. This can be refactored later once
	  validator functions are added.
"""
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.validators.volumeset_validator import validate_volumeset_params
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.utils.utils import handle_async_response

logger = Logger()


class VolumeSetWorkflow:
	"""Workflow encapsulating Volume Set operations."""

	def __init__(self, session_mgr: SessionManager, task_manager: TaskManager):
		self.session_mgr = session_mgr
		self.task_manager = task_manager
	
	def _build_create_payload(self, name: str, appSetType: str, **kwargs):
		"""Build create payload with mandatory name & appSetType.

		Optional keys already validated by validator: domain, comments, members/setmembers.
		We simply loop through kwargs and map them into the payload; members/setmembers
		are merged into a single 'members' list if both supplied.
		"""
		payload = {"appSetName": name, "appSetType": appSetType}
		members_accum = []
		for param, value in kwargs.items():
			if value is None:
				continue
			if param == "domain":
				payload["domain"] = value
			if param == "comments":
				payload["appSetComments"] = value
			if param == "setmembers":
				payload["members"] = value
		logger.debug(f"Built create payload for volume set '{name}': {payload}")
		return payload

	# ------------------------------------------------------------------
	# Create / Delete
	# ------------------------------------------------------------------
	def _execute_create_volumeset(self, name: str, appSetType: str, **kwargs):
		try:
			logger.info(f"Starting volume set creation for '{name}'")
			# Include operation='create' so validator enforces appSetType only in create context
			validate_volumeset_params(name=name, appSetType=appSetType, operation='create', **kwargs)
			if self.volumeset_exists(name):
				logger.error(f"Volume set '{name}' already exists")
				raise exceptions.VolumeSetAlreadyExists(name=name)
			payload = self._build_create_payload(name, appSetType, **kwargs)
			logger.info(f"Creating volume set '{name}' with payload: {payload}")
			response = self.session_mgr.rest_client.post("/applicationsets", payload=payload)
			result = handle_async_response(self.task_manager, "volume set creation", name, response)
			logger.info(f"Volume set '{name}' created successfully")
			return result
		except Exception as e:
			logger.exception(f"Volume set creation failed for '{name}': {e}")
			raise
		
	def create_volumeset(self, name: str, appSetType: str, **kwargs):
		"""Public create method with only name & appSetType required.

		Optional values: domain, comments, members/setmembers, and future kwargs.
		"""
		logger.info(f">>>>>>>Entered create_volumeset: name='{name}'")
		try:
			return self._execute_create_volumeset(name, appSetType, **kwargs)
		except Exception as e:
			logger.exception(f"Failed to create volumeset due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited create_volumeset: name='{name}'")
		
	def _get_volumesets_info(self):
		try:
			resp = self.session_mgr.rest_client.get("/applicationsets")
			return resp
		except Exception as e:
			logger.exception(f"Failed to get volume sets info: {e}")
			raise e

	def _get_volumeset_info(self, name: str):
		try:
			logger.info(f"Retrieving volume set '{name}' info")
			volumesets_info = self._get_volumesets_info()
			for volumeset_info in volumesets_info.get("members", []).values():
				if volumeset_info.get("appSetName") == name:
					return volumeset_info
			return []
		except Exception as e:
			logger.exception(f"Failed to get volume set info '{name}': {e}")
			raise e
	def _execute_volumeset_exists(self, name: str) -> bool:
		try:
			# Validate only name presence; appSetType not needed for existence check
			if not isinstance(name, str) or not name.strip():
				logger.error(f"Invalid volume set name provided: {name}")
				raise ValueError("Volume set name must be a non-empty string")
			return self._get_volumeset_info(name) != []
		except Exception as e:
			logger.info(f"volumeset_exists check failed for '{name}': {e}")
			raise
	def volumeset_exists(self, name: str) -> bool:
		return self._execute_volumeset_exists(name)
	
	def _execute_delete_volumeset(self, name: str):
		try:
			logger.info(f"Starting volume set deletion for '{name}'")
			if not self.volumeset_exists(name):
				logger.error(f"Volume set '{name}' does not exist")
				raise exceptions.VolumeSetDoesNotExist(name=name)
			logger.info(f"Deleting volume set '{name}'")
			volumeset_info_uid = (self._get_volumeset_info(name)).get("uid")
			logger.info(f"Volume set '{name}' UID: {volumeset_info_uid}")
			response = self.session_mgr.rest_client.delete(f"/applicationsets/{volumeset_info_uid}")
			result = handle_async_response(self.task_manager, "volume set deletion", name, response)
			logger.info(f"Volume set '{name}' deleted successfully")
			return result
		except Exception as e:
			logger.exception(f"Volume set deletion failed for '{name}': {e}")
			raise
	def delete_volumeset(self, name: str):
		logger.info(f">>>>>>>Entered delete_volumeset: name='{name}'")
		try:
			return self._execute_delete_volumeset(name)
		except Exception as e:
			logger.exception(f"Failed to delete volumeset due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited delete_volumeset: name='{name}'")

	def _execute_add_volumes_to_volumeset(self, name: str, setmembers):
		# Ensure variable exists for exception logging even if early validation fails
		new_members = []
		try:
			logger.info(f"Starting add volumes operation for volume set '{name}'")
			logger.info(f"Validating parameters for adding volumes to volume set '{name}'")
			if setmembers is None:
				logger.error(f"Setmembers parameter is null for volume set '{name}'")
				raise ValueError("Setmembers cannot be null")
			validate_volumeset_params(name=name, setmembers=setmembers)
			if not self.volumeset_exists(name):
				logger.error(f"Volume set '{name}' does not exist, cannot add volumes")
				raise exceptions.VolumeSetDoesNotExist(name=name)
			volumeset_info = self._get_volumeset_info(name)
			existing_volumeset_members = volumeset_info.get("members") or []
			logger.info(f"Existing members in volume set '{name}': {existing_volumeset_members}")
			for member in setmembers:
				if member not in existing_volumeset_members:
					new_members.append(member)
				else:
					logger.info(f"Volume '{member}' is already a member of volume set '{name}' so skipping it")
			if len(new_members) == 0:
				logger.warning(f"All the members are already present in the volume set '{name}'")
				raise exceptions.VolumeSetMembersAlreadyPresent(name=name)
			logger.info(f"Adding {new_members} members to volume set '{name}'")
			members_list = existing_volumeset_members + new_members
			payload = {"members": members_list}
			response = self.session_mgr.rest_client.patch(f"/applicationsets/{volumeset_info.get('uid')}", payload=payload)
			result = handle_async_response(self.task_manager, "add volumes to volume set", name, response)
			logger.info(f"Successfully added {new_members} members to volume set '{name}'")
			return result
		except Exception as e:
			logger.exception(f"Failed adding {new_members} members to volume set '{name}': {e}")
			raise e

	def add_volumes_to_volumeset(self, name: str, setmembers):
		logger.info(f">>>>>>>Entered add_volumes_to_volumeset: name='{name}'")
		try:
			return self._execute_add_volumes_to_volumeset(name, setmembers)
		except Exception as e:
			logger.exception(f"Failed to add volumes to volumeset due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited add_volumes_to_volumeset: name='{name}'")

	def _execute_remove_volumes_from_volumeset(self, name: str, setmembers):
		members_to_remove = []
		try:
			logger.info(f"Starting remove volumes operation for volume set '{name}'")
			logger.info(f"Validating parameters for removing volumes from volume set '{name}'")
			if setmembers is None:
				logger.error(f"Setmembers parameter is null for volume set '{name}'")
				raise ValueError("Setmembers cannot be null")
			validate_volumeset_params(name=name, setmembers=setmembers)
			if not self.volumeset_exists(name):
				logger.error(f"Volume set '{name}' does not exist, cannot remove volumes")
				raise exceptions.VolumeSetDoesNotExist(name=name)
			volumeset_info = self._get_volumeset_info(name)
			existing_volumeset_members = volumeset_info.get("members") or []
			for member in setmembers:
				if member in existing_volumeset_members:
					members_to_remove.append(member)
				else:
					logger.info(f"Volume '{member}' is already removed or not a member of volume set '{name}' so skipping it")
			members_list = [m for m in existing_volumeset_members if m not in members_to_remove]
			if len(members_to_remove) == 0:
				logger.warning(f"All the members are already removed or not the members of the volume set '{name}'")
				raise exceptions.VolumeSetMembersAlreadyRemoved(name=name)
			logger.info(f"Removing {members_to_remove} members from volume set '{name}'")
			payload = {"members": members_list}
			response = self.session_mgr.rest_client.patch(f"/applicationsets/{volumeset_info.get('uid')}", payload=payload)
			result = handle_async_response(self.task_manager, "remove volumes from volume set", name, response)
			logger.info(f"Successfully removed {members_to_remove} members from volume set '{name}'")
			return result
		except Exception as e:
			logger.exception(f"Failed removing {members_to_remove} members from volume set '{name}': {e}")
			raise e
	def remove_volumes_from_volumeset(self, name: str, setmembers):
		logger.info(f">>>>>>>Entered remove_volumes_from_volumeset: name='{name}'")
		try:
			return self._execute_remove_volumes_from_volumeset(name, setmembers)
		except Exception as e:
			logger.exception(f"Failed to remove volumes from volumeset due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited remove_volumes_from_volumeset: name='{name}'")
	
	def _execute_modify_volumeset(self, name: str, **kwargs):
		try:
			logger.info(f"Starting volume set modification for '{name}'")
			newName = kwargs.get('newName')
			comments = kwargs.get('comments')
			validate_volumeset_params(name=name, newName=newName, comments=comments)
			if not self.volumeset_exists(name):
				logger.error(f"Volume set '{name}' does not exist")
				raise exceptions.VolumeSetDoesNotExist(name=name)
			volumeset_info = self._get_volumeset_info(name)
			payload = {}
			if newName is not None:
				payload["appSetName"] = newName
			if comments is not None:
				payload["appSetComments"] = comments
			response = self.session_mgr.rest_client.patch(f"/applicationsets/{volumeset_info.get('uid')}", payload=payload)
			result = handle_async_response(self.task_manager, "volume set modification", name, response)
			logger.info(f"Volume set '{name}' modified successfully")
			return result
		except Exception as e:
			logger.exception(f"Failed modifying volume set '{name}': {e}")
			raise e

	def modify_volumeset(self, name: str, **kwargs):
		logger.info(f">>>>>>>Entered modify_volumeset: name='{name}'")
		try:
			return self._execute_modify_volumeset(name, **kwargs)
		except Exception as e:
			logger.exception(f"Failed to modify volumeset due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited modify_volumeset: name='{name}'")