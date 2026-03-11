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
from hpe_storage_flowkit_py.v3.src.core.session import  SessionManager
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.validators.snapshot_validator import validate_snapshot_params ,validate_promote_snapshot_volume_params
from hpe_storage_flowkit_py.v3.src.utils.utils import _convert_to_seconds,handle_async_response
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
import re
logger = Logger()


class SnapshotWorkflow:
    def __init__(self, session_mgr: SessionManager, task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager = task_manager

    def _preprocess_create_snapshot(self, optional):
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

    def _execute_create_snapshot(self, volume_name, snapshot_name, **kwargs):
        logger.info(f"Starting snapshot creation for volume '{volume_name}' with name '{snapshot_name}'")
        
        # Check if snapshot already exists (snapshot is a volume)
        existing_snapshot = self.get_snapshot_uid(snapshot_name)
        if existing_snapshot:
            logger.error(f"Snapshot '{snapshot_name}' already exists")
            raise VolumeAlreadyExists(name=snapshot_name)
        
        # First preprocess to convert unit parameters if provided
        processed_params = {}
        if kwargs:
            processed_params = self._preprocess_create_snapshot(kwargs)
        
        # Now validate the processed API parameters
        logger.info(f"Validating snapshot parameters for volume={volume_name}, snapshot={snapshot_name}, processed_params={processed_params}")
        validate_snapshot_params(volume_name, snapshot_name, processed_params)
        
        logger.info(f"Fetching UID for volume: {volume_name}")
        resp_list = self.get_volume_info(volume_name)
        if not resp_list:
            logger.error(f"Volume not found for snapshot creation: {volume_name}")
            raise VolumeDoesNotExist(name=volume_name)
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"Volume UID missing for: {volume_name} in response {resp_list}")
            raise ValueError(f"Volume UID missing for: {volume_name}")
        
        logger.info(f"Volume UID: {uid}")
        
        parameters = {'customName': snapshot_name, "namePattern": "CUSTOM"}        
        if processed_params:
            logger.info(f"Processing kwargs parameters: {kwargs}")
            parameters.update(processed_params)
            logger.info(f"Updated parameters with kwargs: {parameters}")
        
        info = {'action': 'CREATE_SNAPSHOT_VOLUME',
                'parameters': parameters}
        logger.info(f"Creating snapshot with payload: {info}")
        
        try:
            resp = self.session_mgr.rest_client.post(f"/volumes/{uid}", info)
            logger.info(f"Snapshot creation initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "snapshot creation", snapshot_name, resp)
            logger.info(f"Snapshot '{snapshot_name}' created successfully for volume '{volume_name}'")
            return result
        except Exception as e:
            logger.exception(f"Error creating Snapshot {info}: {str(e) or repr(e)}") 
            return e

    def create_snapshot(self, volume_name,snapshot_name,**kwargs):
        logger.info(f">>>>>>>Entered create_snapshot: volume='{volume_name}', snapshot='{snapshot_name}'")
        try:
            response=self._execute_create_snapshot(volume_name,snapshot_name,**kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"create_snapshot response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to create snapshot due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited create_snapshot: volume='{volume_name}', snapshot='{snapshot_name}'")
    
    def _execute_delete_snapshot(self,snapshot_name):
        logger.info(f"Starting snapshot deletion for '{snapshot_name}'")
        validate_snapshot_params(snapshot_name)
        
        # Get snapshot UID with proper error handling
        resp_list = self.get_snapshot_uid(snapshot_name)
        if not resp_list:
            logger.error(f"Snapshot not found for deletion: {snapshot_name}")
            raise VolumeDoesNotExist(name=snapshot_name)
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"Snapshot UID missing for: {snapshot_name} in response {resp_list}")
            raise ValueError(f"Snapshot UID missing for: {snapshot_name}")
        
        try:
            resp = self.session_mgr.rest_client.delete(f"/volumes/{uid}")
            logger.info(f"Snapshot deletion initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "snapshot deletion", snapshot_name, resp)
            logger.info(f"Snapshot '{snapshot_name}' deleted successfully")
            return result
        except Exception as e:
            logger.exception(f"Error deleting Snapshot {snapshot_name}: {str(e) or repr(e)}") 
            return e


    def delete_snapshot(self,snapshot_name):
        logger.info(f">>>>>>>Entered delete_snapshot: snapshot='{snapshot_name}'")
        try:
            response=self._execute_delete_snapshot(snapshot_name)
            if isinstance(response, Exception):
                raise response
            logger.info(f"delete_snapshot response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to delete snapshot due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited delete_snapshot: snapshot='{snapshot_name}'")            
    
    def _execute_promote_snapshot_volume(self, snapshot_name, **kwargs):
        logger.info(f"Starting snapshot promotion for '{snapshot_name}'")
        # Validate the promote parameters
        validate_promote_snapshot_volume_params(snapshot_name, kwargs)
        
        # Get snapshot UID with proper error handling
        resp_list = self.get_snapshot_uid(snapshot_name)
        if not resp_list:
            logger.error(f"Snapshot not found for promotion: {snapshot_name}")
            raise VolumeDoesNotExist(name=snapshot_name)
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"Snapshot UID missing for: {snapshot_name} in response {resp_list}")
            raise ValueError(f"Snapshot UID missing for: {snapshot_name}")
        
        # Build parameters payload from validated kwargs
        parameters = {}
        if kwargs:
            parameters.update(kwargs)
        
        info = {"action": "PROMOTE_SNAPSHOT_VOLUME", 'parameters': parameters}
        logger.info(f"Promoting snapshot with payload: {info}")
        try:
            resp = self.session_mgr.rest_client.post(f"/volumes/{uid}", info)
            logger.info(f"Snapshot promotion initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "snapshot promotion", snapshot_name, resp)
            logger.info(f"Snapshot '{snapshot_name}' promoted successfully")
            return result
        except Exception as e:
            logger.exception(f"Error promoting Snapshot {snapshot_name}: {str(e) or repr(e)}") 
            return e

    def promote_snapshot_volume(self,snapshot_name,**kwargs):
        logger.info(f">>>>>>>Entered promote_snapshot_volume: snapshot='{snapshot_name}'")
        try:
            response=self._execute_promote_snapshot_volume(snapshot_name,**kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"promote_virtual_copy response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to promote snapshot volume due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited promote_snapshot_volume: snapshot='{snapshot_name}'")             

    
    def _execute_appset_snapshot(self,snapshot_name,appset_name,optional):
        logger.info(f"Starting appset snapshot creation for appset '{appset_name}' with snapshot name '{snapshot_name}'")
        # Get appset UID with proper error handling
        resp_list = self.get_appset_uid(appset_name)
        if not resp_list:
            logger.error(f"AppSet not found for snapshot creation: {appset_name}")
            raise ValueError(f"AppSet not found: {appset_name}")
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"AppSet UID missing for: {appset_name} in response {resp_list}")
            raise ValueError(f"AppSet UID missing for: {appset_name}")
        
        parameters={"snapshotName":snapshot_name}
        if optional:
            parameters.update(optional)
        info={"action":"CREATE_SNAPSHOT_APPSET",'parameters':parameters}
        logger.info(f"Creating appset snapshot with payload: {info}")
        try:
            resp = self.session_mgr.rest_client.post(f"/applicationsets/{uid}",info)
            logger.info(f"Appset snapshot creation initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "appset snapshot creation", snapshot_name, resp)
            logger.info(f"Snapshot '{snapshot_name}' created successfully for appset '{appset_name}'")
            return result
        except Exception as e:
            logger.exception(f"Error creating appset Snapshot {snapshot_name}: {str(e) or repr(e)}") 
            return e

    def create_appset_snapshot(self,snapshot_name,appset_name,optional):
        try:
            response=self._execute_appset_snapshot(snapshot_name,appset_name,optional)
            if isinstance(response, Exception):
                raise response
            logger.info(f"create_appset_snapshot response: {response}")
            return response
        except HPEStorageException as e:
            logger.exception(f"HPEStorageException in create_appset_snapshot: {str(e) or repr(e)}")
            raise
        except Exception as e:
            logger.exception(f"Exception in create_appset_snapshot: {str(e) or repr(e)}")
            raise             


    def get_appset_uid(self,name):
        try:
            headers={"experimentalfilter":"true"}
            endpoint=f"/applicationsets?appSetName={name}"
            logger.info(f"Getting appset with endpoint={endpoint}, headers={headers}")
            response = self.session_mgr.rest_client.get(endpoint, headers=headers)
            logger.info(f"get_appset_uid response: {response}")
            return response
        except HPEStorageException as e:
            logger.exception(f"HPEStorageException in get_appset_uid: {str(e) or repr(e)}")
            raise

    def get_snapshot_uid(self,volume_name):
        try:
            headers = {"experimentalfilter": "true"}
            endpoint = f"/volumes?name={volume_name}"
            logger.info(f"Getting Volume with endpoint={endpoint}, headers={headers}")
            response = self.session_mgr.rest_client.get(endpoint, headers=headers)
            logger.info(f"get_volume_info response: {response}")
            return response
        except HPEStorageException as e:
            logger.error(f"HPEStorageException in get_volume_snapshots: {str(e) or repr(e)}")
            raise


    def get_volume_info(self,volume_name):
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

    
    def get_volume_snapshots(self, volume_name, live_test=True):
        """Return list of snapshot names for a given volume name.

        live_test=True filters using actual copyOfShortName and type.
        live_test=False uses a name pattern heuristic (prefix 'SNAP').
        """
        try:
            headers = {"experimentalfilter": "true"}
            endpoint = f"/volumes?copyOfShortName={volume_name}"
            logger.info(f"Getting Volume Snapshots with endpoint={endpoint}, headers={headers}")
            response = self.session_mgr.rest_client.get(endpoint, headers=headers)
            logger.info(f"get_volume_snapshots raw response: {response}")

            # Normalize members list (API may return list directly or dict with 'members')
            if isinstance(response, dict):
                members = response.get('members', [])
            else:
                members = response

            if not isinstance(members, list):
                logger.error("Unexpected response format for snapshots; expected list")
                return []

            snapshots = []
            if live_test:
                for vol in members:
                    if vol.get('type') == 'VVTYPE_SNAPSHOT' and vol.get('copyOfShortName') == volume_name:
                        snapshots.append(vol.get('name'))
            else:
                for vol in members:
                    name = vol.get('name', '')
                    if re.match(r'^SNAP', name):
                        snapshots.append(name)

            logger.info(f"Extracted snapshots: {snapshots}")
            return snapshots
        except HPEStorageException as e:
            logger.exception(f"HPEStorageException in get_volume_snapshots: {str(e) or repr(e)}")
            raise
