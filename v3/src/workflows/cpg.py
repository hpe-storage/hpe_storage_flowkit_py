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
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, CpgDoesNotExist, CpgAlreadyExists
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.validators.cpg_validator import validate_cpg_params
from hpe_storage_flowkit_py.v3.src.utils.utils import _convert_size_to_mib,handle_async_response
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
logger = Logger()
 
class CpgWorkflow:
    def __init__(self, session_mgr: SessionManager,task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager=task_manager
    def _preprocess_create_cpg(self, kwargs):
        """
        Preprocess CPG creation parameters, converting growth parameters with units to MiB.
        
        Args:
            kwargs: Dictionary with CPG parameters
            
        Returns:
            dict: Processed parameters with converted values
        """
        processed_params = {}
        
        if kwargs is not None:
            # Copy all parameters as-is
            processed_params.update(kwargs)
            
            # Handle growth_increment conversion
            if 'growth_increment' in kwargs and kwargs['growth_increment'] is not None:
                growth_increment_unit = kwargs.get('growth_increment_unit')
                growth_increment_mib = _convert_size_to_mib(kwargs['growth_increment'], growth_increment_unit)
                if growth_increment_mib is not None:
                    processed_params['growthSizeMiB'] = growth_increment_mib
                    logger.info(f"Converted growth_increment: {kwargs['growth_increment']} {growth_increment_unit} -> {growth_increment_mib} MiB")
                # Remove the convenience parameters
                processed_params.pop('growth_increment', None)
                processed_params.pop('growth_increment_unit', None)
            
            # Handle growth_limit conversion
            if 'growth_limit' in kwargs and kwargs['growth_limit'] is not None:
                growth_limit_unit = kwargs.get('growth_limit_unit')
                growth_limit_mib = _convert_size_to_mib(kwargs['growth_limit'], growth_limit_unit)
                if growth_limit_mib is not None:
                    processed_params['growthLimitMiB'] = growth_limit_mib
                    logger.info(f"Converted growth_limit: {kwargs['growth_limit']} {growth_limit_unit} -> {growth_limit_mib} MiB")
                # Remove the convenience parameters
                processed_params.pop('growth_limit', None)
                processed_params.pop('growth_limit_unit', None)
            
            # Handle growth_warning conversion
            if 'growth_warning' in kwargs and kwargs['growth_warning'] is not None:
                growth_warning_unit = kwargs.get('growth_warning_unit')
                growth_warning_mib = _convert_size_to_mib(kwargs['growth_warning'], growth_warning_unit)
                if growth_warning_mib is not None:
                    processed_params['growthWarnMiB'] = growth_warning_mib
                    logger.info(f"Converted growth_warning: {kwargs['growth_warning']} {growth_warning_unit} -> {growth_warning_mib} MiB")
                # Remove the convenience parameters
                processed_params.pop('growth_warning', None)
                processed_params.pop('growth_warning_unit', None)
        
        return processed_params
    
    def _execute_create_cpg(self, name, **kwargs):
        logger.info(f"Starting CPG creation for '{name}'")
        logger.info(f"Preprocessing CPG parameters for {name}: {kwargs}")
        
        # Check if CPG already exists
        existing_cpg = self.get_cpg_info(name)
        if existing_cpg:
            logger.error(f"CPG '{name}' already exists")
            raise CpgAlreadyExists(name=name)
        
        # Preprocess parameters to convert growth values with units to MiB
        processed_params = self._preprocess_create_cpg(kwargs)
        
        logger.info(f"Processed CPG parameters: {processed_params}")
        
        # Validate the processed API parameters
        validate_cpg_params(name, processed_params)
        
        payload = {"name": name}
        if processed_params:
            payload.update(processed_params) 

        try:
            resp = self.session_mgr.rest_client.post(f"/cpgs", payload)
            logger.info(f"CPG creation initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "CPG creation", name, resp)
            logger.info(f"CPG '{name}' created successfully")
            return result
        except Exception as e:
            logger.exception(f"Error creating cpg {payload}: {str(e) or repr(e)}") 
            return e 
  
    def create_cpg(self, name, **kwargs):
        logger.info(f">>>>>>>Entered create_cpg: name='{name}'")
        try:
            response = self._execute_create_cpg(name, **kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"create_cpg response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to create CPG due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited create_cpg: name='{name}'")       

    def _execute_delete_cpg(self,name):
        logger.info(f"Starting CPG deletion for '{name}'")
        validate_cpg_params(name)
        
        # Get CPG UID with proper error handling
        resp_list = self.get_cpg_info(name)
        if not resp_list:
            logger.error(f"CPG not found for deletion: {name}")
            raise CpgDoesNotExist(name=name)
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"CPG UID missing for: {name} in response {resp_list}")
            raise ValueError(f"CPG UID missing for: {name}")
        
        try:
            resp = self.session_mgr.rest_client.delete(f"/cpgs/{uid}")
            logger.info(f"CPG deletion initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "CPG deletion", name, resp)
            logger.info(f"CPG '{name}' deleted successfully")
            return result
        except Exception as e:
            logger.exception(f"Error deleting CPG {name}: {str(e) or repr(e)}") 
            return e 
                  
    def delete_cpg(self,name):
        logger.info(f">>>>>>>Entered delete_cpg: name='{name}'")
        try:
            response=self._execute_delete_cpg(name)
            if isinstance(response, Exception):
                raise response
            logger.info(f"delete_cpg response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to delete CPG due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited delete_cpg: name='{name}'")              
    
    def get_cpg_info(self,name):
        try:
            headers = {"experimentalfilter": "true"}
            endpoint = f"/cpgs?name={name}"
            logger.info(f"Getting CPG with endpoint={endpoint}, headers={headers}")
            response = self.session_mgr.rest_client.get(endpoint, headers=headers)
            logger.info(f"get_cpg_info response: {response}")
            return response
        except HPEStorageException as e:
            logger.exception(f"HPEStorageException in get_cpg_uid: {str(e) or repr(e)}")
            raise        
    
    def list_cpgs(self):
        try:
            endpoint = f"/cpgs"
            logger.info(f"Getting all CPGs with endpoint={endpoint}")
            response = self.session_mgr.rest_client.get(endpoint)
            logger.info(f"list_cpgs response: {response}")
            return response
        except HPEStorageException as e:
            logger.exception(f"HPEStorageException in list_cpgs: {str(e) or repr(e)}")
            raise
