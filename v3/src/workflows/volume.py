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
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, VolumeDoesNotExist, VolumeAlreadyExists
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.validators.volume_validator import validate_create_volume_params, validate_modify_volume_params, validate_volume_params ,validate_tune_volume_params
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.utils.utils import _convert_size_to_mib, _convert_to_seconds, handle_async_response
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
logger = Logger()

class VolumeWorkflow:

	def __init__(self, session_mgr: SessionManager,task_manager: TaskManager):
		self.session_mgr = session_mgr
		self.task_manager=task_manager
	def _preprocess_volume_time_params(self, kwargs):
		"""
		Preprocess volume parameters, converting expiration_time and retention_time to seconds.
		
		Args:
			kwargs: Dictionary with volume parameters
			
		Returns:
			dict: Processed parameters with converted values
		"""
		logger.debug("Starting volume time parameter preprocessing")
		processed_params = {}
		
		if kwargs is not None:
			# Copy all parameters as-is
			processed_params.update(kwargs)
			
			# Handle expiration_time conversion
			if 'expiration_time' in kwargs and kwargs['expiration_time'] is not None:
				expiration_unit = kwargs.get('expiration_unit')
				expireSecs = _convert_to_seconds(kwargs['expiration_time'], expiration_unit)
				if expireSecs is not None:
					processed_params['expireSecs'] = expireSecs
					logger.debug(f"Converted expiration_time: {kwargs['expiration_time']} {expiration_unit} -> {expireSecs} seconds")
				# Remove the convenience parameters
				processed_params.pop('expiration_time', None)
				processed_params.pop('expiration_unit', None)
			
			# Handle retention_time conversion
			if 'retention_time' in kwargs and kwargs['retention_time'] is not None:
				retention_unit = kwargs.get('retention_unit')
				retainSecs = _convert_to_seconds(kwargs['retention_time'], retention_unit)
				if retainSecs is not None:
					processed_params['retainSecs'] = retainSecs
					logger.debug(f"Converted retention_time: {kwargs['retention_time']} {retention_unit} -> {retainSecs} seconds")
				# Remove the convenience parameters
				processed_params.pop('retention_time', None)
				processed_params.pop('retention_unit', None)
		
		logger.debug("Completed volume time parameter preprocessing")
		return processed_params


	def _execute_create_volume(self, name, cpg, size, **kwargs):
		"""
		Execute volume creation with payload for HPE 3PAR SSMC API.
		
		Required parameters:
		- name: Name of the volume to be created
		- cpg: User CPG of the volume to be created  
		- size: Size of the volume to be created (converted to MiB)
		
		Optional parameters:
		- comments: Comments of the volume to be created
		- count: Count of volumes to be created
		- dataReduction: Data reduction setting of the volume to be created
		- expiration_time: Expiration time value (will be converted to expireSecs)
		- expiration_unit: Unit for expiration_time (seconds, minutes, hours, days)
		- expireSecs: Expiration value specified for volume snapshot
		- ransomWare: Enable/disabled the ransomware policy for the volume
		- retention_time: Retention time value (will be converted to retainSecs)
		- retention_unit: Unit for retention_time (seconds, minutes, hours, days)
		- retainSecs: Retention value specified for volume snapshot
		- userAllocWarning: User allocation warning value of the volume to be created
		"""
		logger.info(f"Starting volume creation for '{name}'")
		
		# Check if volume already exists
		existing_volume = self.get_volume_info(name)
		if existing_volume:
			logger.error(f"Volume '{name}' already exists")
			raise VolumeAlreadyExists(name=name)
		
		# Preprocess time parameters (expiration_time, retention_time)
		processed_params = self._preprocess_volume_time_params(kwargs)
		
		# Validate required parameters
		size_unit = processed_params.pop('size_unit', None)
		logger.debug(f"Converting size for volume creation")
		sizeMib = _convert_size_to_mib(size, size_unit)
		logger.debug(f"Size converted to MiB: {sizeMib}")

		validate_create_volume_params(name, sizeMib, cpg, processed_params)

		# Build the base payload with required fields
		logger.debug("Building volume creation payload")
		payload = {
			"name": name,
			"userCpg": cpg,
			"sizeMiB": sizeMib
		}
		payload.update(processed_params)
		logger.debug(f"Volume creation payload: {payload}")
		try:
			resp = self.session_mgr.rest_client.post("/volumes", payload)
			logger.info(f"Volume creation initiated: {resp}")
			
			result = handle_async_response(self.task_manager, "volume creation", name, resp)
			logger.info(f"Volume '{name}' created successfully")
			return result
		except Exception as e:
			logger.exception(f"Error creating Volume {name}: {str(e) or repr(e)}")
			return e

	def create_volume(self, name, cpg, size, **kwargs):
		logger.info(f">>>>>>>Entered create_volume: name='{name}', cpg='{cpg}', size={size}")
		try:
			response = self._execute_create_volume(name, cpg, size, **kwargs)
			if isinstance(response, Exception):
				raise response
			logger.info(f"createVolume response: {response}")
			return response
		except Exception as e:
			logger.exception(f"Failed to create volume due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited create_volume: name='{name}'")

	def _execute_modify_volume(self, vol_name, **kwargs):
		"""
		Execute volume modification using PATCH for HPE 3PAR SSMC API.
		
		Required parameters:
		- vol_name: Name of the volume to be modified
		
		Optional parameters (via **kwargs):
		- comments: Edit comment of virtual volume (string, max length: vv_comment_len)
		- expiration_time: Expiration time value (will be converted to expireSecs)
		- expiration_unit: Unit for expiration_time (seconds, minutes, hours, days)
		- expireSecs: Expiration value specified for volume snapshot (uint64)
		- keyValuePairs: Key value pairs assigned to the object (map[string]string)
		- name: Edit name of virtual volume (string, must satisfy tpd_obj_name validation)
		- ransomWare: Enable/disable the ransomware policy of the volume (bool)
		- retention_time: Retention time value (will be converted to retainSecs)
		- retention_unit: Unit for retention_time (seconds, minutes, hours, days)
		- retainSecs: Retention value specified for volume snapshot (uint64)
		- size: Edit size of virtual volume (will be converted to MiB)
		- size_unit: Unit of size (GiB, TiB, MiB) - if not provided, auto-detection is used
		- sizeMiB: Edit size of virtual volume in MiB (float64, min: vv_usr_min_mb)
		- userAllocWarning: Edit user space allocation warning of virtual volume (int64, 0-100%)
		- wwn: World Wide Name of the volume (string)
		"""
		logger.info(f"Starting volume modification for '{vol_name}'")
		# Preprocess time parameters (expiration_time, retention_time)
		processed_params = self._preprocess_volume_time_params(kwargs)
		
		size_unit = processed_params.pop('size_unit', None)
		size = processed_params.pop('size', None)
		
		if size is not None:
			logger.debug(f"Converting size for volume modification")
			sizeMib = _convert_size_to_mib(size, size_unit)
			processed_params['sizeMiB'] = sizeMib
			logger.debug(f"Size converted to MiB: {sizeMib}")

		validate_modify_volume_params(vol_name, processed_params)
		
		# Build the payload with all processed params
		logger.debug("Building volume modification payload")
		payload = {}
		payload.update(processed_params)
		logger.debug(f"Volume modification payload built")

		# Get volume UID with proper error handling
		resp_list = self.get_volume_info(vol_name)
		if not resp_list:
			logger.error(f"Volume not found for modification: {vol_name}")
			raise VolumeDoesNotExist(name=vol_name)
		
		volumeUID = resp_list[0].get("uid")
		if not volumeUID:
			logger.error(f"Volume UID missing for: {vol_name} in response {resp_list}")
			raise ValueError(f"Volume UID missing for: {vol_name}")
		logger.debug(f"Volume UID retrieved: {volumeUID}")
		
		try:
			endpoint = f"/volumes/{volumeUID}"
			resp = self.session_mgr.rest_client.patch(endpoint, payload)
			logger.info(f"Volume modification initiated: {resp}")
			
			result = handle_async_response(self.task_manager, "volume modification", vol_name, resp)
			logger.info(f"Volume '{vol_name}' modified successfully")
			return result
		except Exception as e:
			logger.exception(f"Error modifying Volume {vol_name}: {str(e) or repr(e)}")
			return e

	def modify_volume(self, vol_name, **kwargs):
		logger.info(f">>>>>>>Entered modify_volume: vol_name='{vol_name}'")
		try:
			response = self._execute_modify_volume(vol_name, **kwargs)
			if isinstance(response, Exception):
				raise response
			logger.info(f"modifyVolume response: {response}")
			return response
		except Exception as e:
			logger.exception(f"Failed to modify volume due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited modify_volume: vol_name='{vol_name}'")

	def _execute_get_volumes(self):
		"""
		Execute volume retrieval using GET for HPE 3PAR SSMC API.
		"""
		try:
			# The API expects GET to /api/v3/volumes/
			endpoint = f"/volumes/"
			response = self.session_mgr.rest_client.get(endpoint)
			return response
		except HPEStorageException as e:
			logger.exception(f"Volume retrieval failed: {e}")
			raise


	def get_volumes(self):
		logger.info(">>>>>>>Entered get_volumes")
		try:
			return self._execute_get_volumes()
		except Exception as e:
			logger.exception(f"Failed to get volumes due to error: {e}")
			raise
		finally:
			logger.info("<<<<<<<Exited get_volumes")


	def _execute_delete_volume(self, name):
		logger.info(f"Starting volume deletion for '{name}'")
		validate_volume_params(name)
		
		# Get volume UID with proper error handling
		resp_list = self.get_volume_info(name)
		if not resp_list:
			logger.error(f"Volume not found for deletion: {name}")
			raise VolumeDoesNotExist(name=name)
		
		uid = resp_list[0].get("uid")
		if not uid:
			logger.error(f"Volume UID missing for: {name} in response {resp_list}")
			raise ValueError(f"Volume UID missing for: {name}")
		logger.debug(f"Volume UID retrieved: {uid}")
		
		try:
			resp = self.session_mgr.rest_client.delete(f"/volumes/{uid}")
			logger.info(f"Volume deletion initiated: {resp}")
			
			result = handle_async_response(self.task_manager, "volume deletion", name, resp)
			logger.info(f"Volume '{name}' deleted successfully")
			return result
		except Exception as e:
			logger.exception(f"Error deleting Volume {name}: {str(e) or repr(e)}")
			return e

	def delete_volume(self, name):
		logger.info(f">>>>>>>Entered delete_volume: name='{name}'")
		try:
			response = self._execute_delete_volume(name)
			if isinstance(response, Exception):
				raise response
			logger.info(f"delete_volume response: {response}")
			return response
		except Exception as e:
			logger.exception(f"Failed to delete volume due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited delete_volume: name='{name}'")

	def get_volume_info(self, volume_name):
		try:
			headers = {"experimentalfilter": "true"}
			endpoint = f"/volumes?name={volume_name}"
			logger.info(f"Getting Volume with endpoint={endpoint}, headers={headers}")
			response = self.session_mgr.rest_client.get(endpoint, headers=headers)
			logger.info(f"get_volume_info response: {response}")
			return response
		except HPEStorageException as e:
			logger.exception(f"HPEStorageException in get_volume_info: {str(e) or repr(e)}")
			raise


	def _execute_grow_volume(self, name,growth_size_mib):
		logger.info(f"Starting volume grow operation for '{name}'")
		validate_volume_params(name,growth_size_mib)
		
		# Get volume UID with proper error handling
		resp_list = self.get_volume_info(name)
		if not resp_list:
			logger.error(f"Volume not found for growing: {name}")
			raise VolumeDoesNotExist(name=name)
		
		uid = resp_list[0].get("uid")
		if not uid:
			logger.error(f"Volume UID missing for: {name} in response {resp_list}")
			raise ValueError(f"Volume UID missing for: {name}")
		logger.debug(f"Volume UID retrieved: {uid}")
		
		logger.debug(f"Building payload for volume grow")
		payload={
			"sizeMiB":growth_size_mib
		}
		logger.debug(f"Payload built for volume grow")
		try:
			resp = self.session_mgr.rest_client.patch(f"/volumes/{uid}",payload)
			logger.info(f"Volume grow initiated: {resp}")
			
			result = handle_async_response(self.task_manager, "volume grow", name, resp)
			logger.info(f"Volume '{name}' grown successfully")
			return result
		except Exception as e:
			logger.exception(f"Error increasing size {name}: {str(e) or repr(e)}")
			return e

	def grow_volume(self, name, growth_size_mib):
		logger.info(f">>>>>>>Entered grow_volume: name='{name}', growth_size_mib={growth_size_mib}")
		try:
			response = self._execute_grow_volume(name, growth_size_mib)
			if isinstance(response, Exception):
				raise response
			logger.info(f"grow_volume response: {response}")
			return response
		except Exception as e:
			logger.exception(f"Failed to grow volume due to error: {e}")
			raise
		finally:
			logger.info(f"<<<<<<<Exited grow_volume: name='{name}'")

	def _execute_tune_volume(self, name, cpg,**kwargs):
		logger.info(f"Starting volume tune operation for '{name}'")
		validate_tune_volume_params(name,cpg,kwargs)
		
		# Get volume UID with proper error handling
		resp_list = self.get_volume_info(name)
		if not resp_list:
			logger.error(f"Volume not found for tuning: {name}")
			raise VolumeDoesNotExist(name=name)
		
		uid = resp_list[0].get("uid")
		if not uid:
			logger.error(f"Volume UID missing for: {name} in response {resp_list}")
			raise ValueError(f"Volume UID missing for: {name}")
		
		# Build the payload with action and parameters
		# Build the payload with action and parameters
		payload = {
			"action": "TUNE_VOLUME",
			"parameters": {
				"userCpgName": cpg
			}
		}
		payload["parameters"].update(kwargs)
		
		logger.info(f"Tune volume payload: {payload}")
		
		try:
			resp = self.session_mgr.rest_client.post(f"/volumes/{uid}", payload)
			logger.info(f"Volume tune initiated: {resp}")
			
			result = handle_async_response(self.task_manager, "volume tune", name, resp)
			logger.info(f"Volume '{name}' tuned successfully")
			return result
		except Exception as e:
			logger.exception(f"Error in tuning volume: {str(e) or repr(e)}")
			return e

	def tune_volume(self,name,cpg,**kwargs):
		"""
		Tune a virtual volume with a custom action.

		Expected params (dictionary):
		- action (string, required): Must be set to "TUNE_VOLUME".
		- parameters (object, required): Parameters for the custom action.
		    - conversionType (enum, optional): Change provision type of virtual volume.
		        Allowed: CONVERSIONTYPE_THIN, CONVERSIONTYPE_V1, CONVERSIONTYPE_V2.
		        Default: CONVERSIONTYPE_V1.
		        
		        Volume Type Mappings:
		        - CONVERSIONTYPE_THIN: Volume is TPVV (Thin Provisioned Virtual Volume)
		        - CONVERSIONTYPE_V1: Volume is TDVV (Thin Deduplicated Virtual Volume) 
		          with deduplication enabled and V1 compression
		        - CONVERSIONTYPE_V2: Volume is TDVV (Thin Deduplicated Virtual Volume) 
		          with deduplication enabled and V2 compression
		        
		        Note: Both V1 and V2 enable deduplication; the difference is in the 
		        compression algorithm version used.
		        
		    - saveToNewName (string, optional): Tune virtual volume and save the original
		        under a new virtual volume name.
		    - userCpgName (string, required): Change user CPG of virtual volume.
		        Must satisfy tpd_obj_name validation.

		Notes:
		- When changing user CPG, ensure the provided userCpgName is different from the
		  current volume CPG.
		- When only converting provision type, provide conversionType and omit userCpgName.
		"""
		try:
			response = self._execute_tune_volume(name,cpg,**kwargs)
			if isinstance(response, Exception):
				raise response
			logger.info(f"tune_volume response: {response}")
			return response
		except Exception as e:
			logger.exception(f"Failed to tune volume due to error: {e}")
			raise
