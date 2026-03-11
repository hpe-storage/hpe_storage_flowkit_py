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
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.validators.clone_validator import validate_clone_params , validate_resync_physical_copy
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.workflows.volume import VolumeWorkflow
from hpe_storage_flowkit_py.v3.src.utils.utils import find_task_by_command ,is_task_completed,_convert_to_seconds,handle_async_response
logger = Logger()

class CloneWorkflow:

    def __init__(self, session_mgr: SessionManager,task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager=task_manager
        self.volume_workflow=VolumeWorkflow(self.session_mgr, self.task_manager)
        
    def _preprocess_copy_volume(self,optional):
            optional_params = {}
            
            if optional is not None:
                # Copy all parameters as-is
                optional_params.update(optional)
                
                
                if 'expiration_time' in optional:
                    expiration_unit = optional.get("expiration_unit")
                    expireSecs = _convert_to_seconds(optional['expiration_time'], expiration_unit)
                    if expireSecs is not None:
                        optional_params['expireSecs'] = expireSecs
                    # Remove the unit parameter as it's not part of API
                    optional_params.pop('expiration_unit', None)
                    optional_params.pop('expiration_time', None)
                
                # Only handle unit conversions if retainSecs has a retention_unit
                if 'retention_time' in optional:
                    retention_unit = optional.get("retention_unit")
                    retainSecs = _convert_to_seconds(optional['retention_time'], retention_unit)
                    if retainSecs is not None:
                        optional_params['retainSecs'] = retainSecs
                    # Remove the unit parameter as it's not part of API
                    optional_params.pop('retention_unit', None)
                    optional_params.pop('retention_time', None)
                
            return optional_params	    

    def _execute_copy_volume(self, src_name, dest_name, **kwargs):
        """Execute physical copy of a volume using v3 API"""
        logger.info(f"Starting volume copy from '{src_name}' to '{dest_name}'")
        # First preprocess to convert unit parameters if provided
        processed_params = {}
        if kwargs:
            processed_params = self._preprocess_copy_volume(kwargs)        
        # Check if online=True requires destinationCpg
        online = kwargs.get('online')
        destinationCpg = kwargs.get('destinationCpg')
        
        if online is True and not destinationCpg:
            raise ValueError("destinationCpg is mandatory when online=True")
        
        # Validate all parameters
        logger.info(f"Validating clone parameters for volume={src_name}, clone={dest_name}, processed_params={processed_params}")
        validate_clone_params(src_name,dest_name, processed_params)

        # Get source volume UID with proper error handling
        resp_list = self.get_volume_info(volume_name=src_name)
        if not resp_list:
            logger.error(f"Source volume not found for cloning: {src_name}")
            raise VolumeDoesNotExist(name=src_name)
        
        src_uid = resp_list[0].get("uid")
        if not src_uid:
            logger.error(f"Source volume UID missing for: {src_name} in response {resp_list}")
            raise ValueError(f"Source volume UID missing for: {src_name}")

        # Build the payload for v3 API
        payload = {
            "action": "CREATE_VVCOPY",
            "parameters": {
                "destination": dest_name  # Required parameter
            }
        }

        # Add all validated kwargs to parameters
        if kwargs:
            payload['parameters'].update(processed_params)

        logger.info(f"Creating volume copy from {src_name} to {dest_name} with payload: {payload}")

        try:
            response = self.session_mgr.rest_client.post(f"/volumes/{src_uid}", payload)
            logger.info(f"Volume copy initiated: {response}")
            
            result = handle_async_response(self.task_manager, "volume copy", dest_name, response)
            logger.info(f"Volume copy from '{src_name}' to '{dest_name}' created successfully")
            return result
        except Exception as e:
            logger.exception(f"Error creating volume copy from {src_uid} to {dest_name}: {str(e) or repr(e)}")
            return e


    def copy_volume(self, src_name, dest_name, **kwargs):
        """Create a volume copy using v3 API"""
        logger.info(f">>>>>>>Entered copy_volume: src='{src_name}', dest='{dest_name}'")
        try:
            logger.info(f"Calling _execute_copy_volume with src_uid={src_name}, dest_name={dest_name}, kwargs={kwargs}")
            response = self._execute_copy_volume(src_name, dest_name,**kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"copy_volume response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to copy volume due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited copy_volume: src='{src_name}', dest='{dest_name}'")

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

    def _execute_stop_physical_copy(self, volume_name):
        """Execute halt volume copy operation using v3 API"""
        logger.info(f"Starting stop physical copy operation for '{volume_name}'")
        validate_clone_params(dest_name=volume_name)
        
        # Get volume UID with proper error handling
        resp_list = self.get_volume_info(volume_name=volume_name)
        if not resp_list:
            logger.error(f"Volume not found for stopping physical copy: {volume_name}")
            raise VolumeDoesNotExist(name=volume_name)
        
        volume_uid = resp_list[0].get("uid")
        if not volume_uid:
            logger.error(f"Volume UID missing for: {volume_name} in response {resp_list}")
            raise ValueError(f"Volume UID missing for: {volume_name}")
        
        payload = {
            "action": "HALT_VVCOPY",
            "parameters": {}
        }

        logger.info(f"Halting volume copy for volume {volume_name} with payload: {payload}")

        try:
            response = self.session_mgr.rest_client.post(f"/volumes/{volume_uid}", payload)
            logger.info(f"Volume copy halt initiated: {response}")
            result = handle_async_response(self.task_manager, "volume copy halt", volume_name, response)
            logger.info(f"Physical copy for volume '{volume_name}' stopped successfully")
            return result
        except Exception as e:
            logger.exception(f"Error halting volume copy for volume {volume_uid}: {str(e) or repr(e)}")
            return e

    def stop_physical_copy(self, volume_name):
        """Stop a physical copy operation using v3 API"""
        logger.info(f">>>>>>>Entered stop_physical_copy: volume='{volume_name}'")
        try:
            logger.info(f"Calling _execute_stop_physical_copy with volume_uid={volume_name}")
            response = self._execute_stop_physical_copy(volume_name)
            if isinstance(response, Exception):
                raise response
            logger.info(f"stop_physical_copy response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to stop physical copy due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited stop_physical_copy: volume='{volume_name}'")

    def _execute_resync_physical_copy(self, volume_name, **kwargs):
        """Execute resync physical copy operation using v3 API"""
        logger.info(f"Starting resync physical copy operation for '{volume_name}'")
        validate_resync_physical_copy(volume_name, kwargs)
        
        # Get volume UID with proper error handling
        resp_list = self.get_volume_info(volume_name=volume_name)
        if not resp_list:
            logger.error(f"Volume not found for resyncing physical copy: {volume_name}")
            raise VolumeDoesNotExist(name=volume_name)
        
        volume_uid = resp_list[0].get("uid")
        if not volume_uid:
            logger.error(f"Volume UID missing for: {volume_name} in response {resp_list}")
            raise ValueError(f"Volume UID missing for: {volume_name}")
        
        # Extract priority from kwargs
        priority = kwargs.get('priority')
        
        payload = {
            "action": "RESYNC_VVCOPY",
            "parameters": {}
        }
        
        if priority is not None:
            payload["parameters"]["priority"] = priority

        logger.info(f"Resyncing physical copy for volume {volume_uid} with payload: {payload}")

        try:
            response = self.session_mgr.rest_client.post(f"/volumes/{volume_uid}", payload)
            logger.info(f"Physical copy resync initiated: {response}")
            
            result = handle_async_response(self.task_manager, "physical copy resync", volume_name, response)
            logger.info(f"Physical copy for volume '{volume_name}' resynced successfully")
            return result
        except Exception as e:
            logger.exception(f"Error resyncing physical copy for volume {volume_uid}: {str(e) or repr(e)}")
            return e

    def resync_physical_copy(self, volume_name,**kwargs):
        """Resync a physical copy operation using v3 API"""
        logger.info(f">>>>>>>Entered resync_physical_copy: volume='{volume_name}'")
        try:
            logger.info(f"Calling _execute_resync_physical_copy with volume_uid={volume_name}")
            response = self._execute_resync_physical_copy(volume_name,**kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"resync_physical_copy response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to resync physical copy due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited resync_physical_copy: volume='{volume_name}'")

    def offline_physical_copy_exist(self, src_name, phycopy_name):

        try:
            logger.info(f"Checking if offline physical copy exists for src={src_name}, dest={phycopy_name}")
            
            # Check if source volume exists
            source_vol = self.volume_workflow.get_volume_info(src_name)
            logger.info(f"Source volume query result: {source_vol}")
            
            if len(source_vol)==0:
                source_vol=None
            # Check if physical copy volume exists
            phy_copy = self.volume_workflow.get_volume_info(phycopy_name)
            logger.info(f"Physical copy volume query result: {phy_copy}")
            if len(phy_copy)==0:
                phy_copy=None
            # Search for task matching the copy operation
            required_strings = [
                "createvvcopy",
                src_name,
                phycopy_name,
            ]
            resp = self.task_manager.get_all_tasks()
            logger.info(f"Retrieved all tasks, searching for matching task")
            task = find_task_by_command(resp, required_strings)
            task_details=task
            if task_details is None:
                return False
            if is_task_completed(task):
                task_details=None          
            if source_vol and phy_copy and task_details is not None:
                return True
            return False            
        except Exception as e:
            logger.exception(f"Error checking offline physical copy existence: {str(e) or repr(e)}")
            raise    

    def online_physical_copy_exist(self,src_name,phycopy_name):
        try:
            logger.info(f"Checking if online physical copy exists for src={src_name}, dest={phycopy_name}")
            
            # Check if source volume exists
            source_vol = self.volume_workflow.get_volume_info(src_name)
            logger.info(f"Source volume query result: {source_vol}")
            
            if len(source_vol)==0:
                source_vol=None
            # Check if physical copy volume exists
            phy_copy = self.volume_workflow.get_volume_info(phycopy_name)
            logger.info(f"Physical copy volume query result: {phy_copy}")
            if len(phy_copy)==0:
                phy_copy=None
            # Search for task matching the copy operation
            required_strings = [
           "createvvcopy",
            "-online",
            src_name,
            phycopy_name
            ]
            resp = self.task_manager.get_all_tasks()
            logger.info(f"Retrieved all tasks, searching for matching task")
            task = find_task_by_command(resp, required_strings)
            task_details=task
            if task_details is None:
                return False
            if is_task_completed(task):
                task_details=None          
            if source_vol and phy_copy and task_details is not None:
                return True
            return False            
        except Exception as e:
            logger.exception(f"Error checking online physical copy existence: {str(e) or repr(e)}")
            raise         
