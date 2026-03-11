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
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, ScheduleDoesNotExist, ScheduleAlreadyExists
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.validators.schedule_validator import validate_schedule_params, validate_modify_schedule_params,validate_suspend_resume_schedule_params
from hpe_storage_flowkit_py.v3.src.utils.utils import _convert_to_seconds,handle_async_response

logger = Logger()


class ScheduleWorkflow:
    def __init__(self, session_mgr: SessionManager, task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager = task_manager

    def _preprocess_createsv_params(self, createsv):
        """
        Preprocess createSV parameters to convert expiration/retention time units to seconds
        
        Args:
            createsv: Dictionary containing createSV parameters
            
        Returns:
            dict: Processed createSV parameters with converted time values
        """
        if not createsv:
            return createsv
            
        processed_createsv = {}
        processed_createsv.update(createsv)
        
        # Handle expiration_time conversion
        if 'expiration_time' in createsv:
            expiration_unit = createsv.get("expiration_unit", "hours")
            expireSecs = _convert_to_seconds(createsv['expiration_time'], expiration_unit)
            if expireSecs is not None:
                processed_createsv['expireSecs'] = expireSecs
            # Remove the unit parameters as they're not part of API
            processed_createsv.pop('expiration_unit', None)
            processed_createsv.pop('expiration_time', None)
        
        # Handle retention_time conversion
        if 'retention_time' in createsv:
            retention_unit = createsv.get("retention_unit", "hours")
            retainSecs = _convert_to_seconds(createsv['retention_time'], retention_unit)
            if retainSecs is not None:
                processed_createsv['retainSecs'] = retainSecs
            # Remove the unit parameters as they're not part of API
            processed_createsv.pop('retention_unit', None)
            processed_createsv.pop('retention_time', None)
        
        return processed_createsv

    def _execute_create_schedule(self,name, **kwargs):
        """
        Execute schedule creation with proper time field defaults
        
        Args:
            name: Schedule name
            **kwargs: Schedule parameters
            
        Returns:
            dict: API response
        """
        # Check if schedule already exists
        existing_schedule = self.get_schedule_info(name)
        if existing_schedule:
            logger.error(f"Schedule '{name}' already exists")
            raise ScheduleAlreadyExists(name=name)
        
        # Preprocess createSV parameters if present
        if 'createsv' in kwargs and kwargs['createsv']:
            kwargs['createsv'] = self._preprocess_createsv_params(kwargs['createsv'])
        
        # Build schedule payload with name
        schedule_payload = {
            'name': name
        }
        
        # Add all provided parameters
        schedule_payload.update(kwargs)
        
        
         # Validate the complete payload
        validate_schedule_params(name, kwargs)
        
        logger.info(f"Schedule creation payload: {schedule_payload}")
        
        try:
            # Make API call to create schedule
            endpoint = "/schedules"
            resp = self.session_mgr.rest_client.post(endpoint, schedule_payload)
            logger.info(f"Schedule creation initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "schedule creation", name, resp)
            return result
        except Exception as e:
            logger.error(f"Error creating schedule {name}: {str(e) or repr(e)}")
            return e

    def create_schedule(self, name, **kwargs):
        """
        Create a new schedule
        
        Args:
            name: Schedule name
            **kwargs: Schedule parameters (command/createsv, time fields, options)
            
        Returns:
            dict: API response
            
        Raises:
            HPEStorageException: If schedule creation fails
        """
        try:
            response = self._execute_create_schedule(name, **kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"create_schedule response: {response}")
            return response
        except HPEStorageException as e:
            logger.error(f"HPEStorageException in create_schedule: {str(e) or repr(e)}")
            raise
        except Exception as e:
            logger.error(f"Exception in create_schedule: {str(e) or repr(e)}")
            raise

    def _execute_modify_schedule(self,schedule_name, **kwargs):
        """
        Execute schedule modification with proper time field defaults
        
        Args:
            schedule_name: Schedule name
            **kwargs: Schedule parameters
            
        Returns:
            dict: API response
        """
        # Preprocess createSV parameters if present
        if 'createsv' in kwargs and kwargs['createsv']:
            kwargs['createsv'] = self._preprocess_createsv_params(kwargs['createsv'])
             
         # Validate the complete payload
        validate_modify_schedule_params(schedule_name,kwargs)
        schedule_payload={}
        schedule_payload.update(kwargs)
        logger.info(f"Schedule modification payload: {schedule_payload}")
        
        # Get schedule UID with proper error handling
        resp_list = self.get_schedule_info(schedule_name)
        if not resp_list:
            logger.error(f"Schedule not found for modification: {schedule_name}")
            raise ScheduleDoesNotExist(name=schedule_name)
        
        if isinstance(resp_list, list) and len(resp_list) > 1:
            logger.error(f"Multiple schedules found for name '{schedule_name}'. Aborting modification.")
            raise ValueError(f"Multiple schedules found for name '{schedule_name}'. Please disambiguate.")
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"schedule UID missing for: {schedule_name} in response {resp_list}")
            raise ValueError(f"schedule UID missing for: {schedule_name}")
        
        try:
            # Make API call to create schedule
            endpoint = f"/schedules/{uid}"
            resp = self.session_mgr.rest_client.patch(endpoint, schedule_payload)
            logger.info(f"Schedule modification initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "schedule modification", schedule_name, resp)
            return result
        except Exception as e:
            logger.error(f"Error modifying schedule {schedule_name}: {str(e) or repr(e)}")
            return e

    def modify_schedule(self,schedule_name,**kwargs):
        try:
            response=self._execute_modify_schedule(schedule_name,**kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"modify_schedule response: {response}")
            return response
        except HPEStorageException as e:
            logger.error(f"HPEStorageException in modify_schedule: {str(e) or repr(e)}")
            raise
        except Exception as e:
            logger.error(f"Exception in modify_schedule: {str(e) or repr(e)}")
            raise            


    def _execute_delete_schedule(self,name):
         
        # Get schedule UID with proper error handling
        resp_list = self.get_schedule_info(name)
        if not resp_list:
            logger.error(f"Schedule not found for deletion: {name}")
            raise ScheduleDoesNotExist(name=name)
        
        if isinstance(resp_list, list) and len(resp_list) > 1:
            logger.error(f"Multiple schedules found for name '{name}'. Aborting deletion.")
            raise ValueError(f"Multiple schedules found for name '{name}'. Please disambiguate.")
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"schedule UID missing for: {name} in response {resp_list}")
            raise ValueError(f"schedule UID missing for: {name}")
        
        try:
            resp = self.session_mgr.rest_client.delete(f"/schedules/{uid}")
            logger.info(f"Schedule deletion initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "schedule deletion", name, resp)
            return result
        except Exception as e:
            logger.error(f"Error deleting schedule {name}: {str(e) or repr(e)}") 
            return e 
                  
    def delete_schedule(self,name):
        try:
            response=self._execute_delete_schedule(name)
            if isinstance(response, Exception):
                raise response
            logger.info(f"delete_schedule response: {response}")
            return response
        except HPEStorageException as e:
            logger.error(f"HPEStorageException in delete_schedule: {str(e) or repr(e)}")
            raise
        except Exception as e:
            logger.error(f"Exception in delete: {str(e) or repr(e)}")
            raise              
    
    def get_schedule_info(self,name):
        try:
            headers = {"experimentalfilter": "true"}
            endpoint = f"/schedules?name={name}"
            logger.info(f"Getting schedule with endpoint={endpoint}, headers={headers}")
            response = self.session_mgr.rest_client.get(endpoint, headers=headers)
            logger.info(f"get_schedule_info response: {response}")
            return response
        except HPEStorageException as e:
            logger.error(f"HPEStorageException in get_schedule_info: {str(e) or repr(e)}")
            raise        
        
    def _execute_action_schedule(self, name, action: str, **kwargs):
        """Internal helper to perform schedule actions like suspend/resume."""
        validate_suspend_resume_schedule_params(name, kwargs)

        # Get schedule UID with proper error handling
        resp_list = self.get_schedule_info(name)
        if not resp_list:
            logger.error(f"Schedule not found for {action.replace('_', ' ')}: {name}")
            raise ScheduleDoesNotExist(name=name)
        if isinstance(resp_list, list) and len(resp_list) > 1:
            logger.error(f"Multiple schedules found for name '{name}'. Aborting {action.replace('_', ' ')}.")
            raise ValueError(f"Multiple schedules found for name '{name}'. Please disambiguate.")

        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"Schedule UID missing for: {name} in response {resp_list}")
            raise ValueError(f"Schedule UID missing for: {name}")

        # Build payload with action and parameters
        payload = {
            "action": action,
            "parameters": {}
        }

        if kwargs:
            payload["parameters"].update(kwargs)

        logger.info(f"{action.replace('_', ' ').capitalize()} payload: {payload}")

        try:
            endpoint = f"/schedules/{uid}"
            resp = self.session_mgr.rest_client.post(endpoint, payload)
            logger.info(f"Schedule {action.replace('_', ' ')} initiated: {resp}")
            result = handle_async_response(self.task_manager, action.replace('_', ' '), name, resp)
            return result
        except Exception as e:
            logger.error(f"Error performing action '{action}' on schedule {name}: {str(e) or repr(e)}")
            return e
    
    def _execute_suspend_schedule(self,name,**kwargs):
        return self._execute_action_schedule(name, "suspend_schedule", **kwargs)        

    def suspend_schedule(self,name,**kwargs):
        try:
            response=self._execute_suspend_schedule(name,**kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"suspend_schedule response: {response}")
            return response
        except HPEStorageException as e:
            logger.error(f"HPEStorageException in suspend_schedule: {str(e) or repr(e)}")
            raise
        except Exception as e:
            logger.error(f"Exception in suspend schedule: {str(e) or repr(e)}")
            raise

    def _execute_resume_schedule(self,name,**kwargs):
        return self._execute_action_schedule(name, "resume_schedule", **kwargs)

    def resume_schedule(self,name,**kwargs):
        try:
            response=self._execute_resume_schedule(name,**kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"resume_schedule response: {response}")
            return response
        except HPEStorageException as e:
            logger.error(f"HPEStorageException in resume_schedule: {str(e) or repr(e)}")
            raise
        except Exception as e:
            logger.error(f"Exception in resume schedule: {str(e) or repr(e)}")
            raise       

