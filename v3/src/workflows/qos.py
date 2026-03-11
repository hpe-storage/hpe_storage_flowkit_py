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
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, QosDoesNotExist, QosAlreadyExists
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager  
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.validators.qos_validator import validate_qos_params
from hpe_storage_flowkit_py.v3.src.utils.utils import handle_async_response
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager

logger = Logger()

class QosWorkflow:


    def __init__(self, session_mgr: SessionManager, task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager = task_manager


    def _execute_create_qos(self, vvs_name, qos, **kwargs):
        logger.info(f"Starting QoS rule creation for '{vvs_name}'")
        
        # Check if QoS rule already exists
        existing_qos = self.get_qos(vvs_name)
        if existing_qos:
            logger.error(f"QoS rule '{vvs_name}' already exists")
            raise QosAlreadyExists(name=vvs_name)
        
        # First, validate all parameters in the qos dict
        # Build params dict for validation including ALL keys from qos dict
        params_to_validate = {
            'targetName': vvs_name,
        }
        
        # Add all parameters from qos dict to validation
        params_to_validate.update(qos)
        
        # Merge kwargs into params for validation
        params_to_validate.update(kwargs)
        
        # Validate with params dict - this will catch invalid parameters like maxBW
        validate_qos_params(params_to_validate)
        
        # Now extract the valid parameters
        iopsMaxLimit = qos.get('iopsMaxLimit')  
        bandwidthMaxLimitKiB = qos.get('bandwidthMaxLimitKiB')
        targetType = qos.get('targetType', 'QOS_TGT_VVSET')  # Default to VVSET if not provided
        
        # Validate that at least one limit is provided
        if not iopsMaxLimit and not bandwidthMaxLimitKiB:
            raise ValueError("At least one of iopsMaxLimit or bandwidthMaxLimitKiB must be provided for QoS rule")
        
        # Build payload
        qosRule = {}
        qosRule["targetName"] = vvs_name  
        qosRule["targetType"] = targetType
        if iopsMaxLimit:
            qosRule['iopsMaxLimit'] = int(iopsMaxLimit)
        if bandwidthMaxLimitKiB:
            qosRule['bandwidthMaxLimitKiB'] = int(bandwidthMaxLimitKiB)
        
        # Add any additional valid parameters from qos dict (like enable, allowAIQoS, etc.)
        for key in ['enable', 'allowAIQoS']:
            if key in qos:
                qosRule[key] = qos[key]
        
        # Add any additional kwargs to payload
        qosRule.update(kwargs)

        logger.info(f"Creating QOS rule with payload: {qosRule}")
        try:
            resp = self.session_mgr.rest_client.post("/qosconfigs", qosRule)
            logger.info(f"QoS creation initiated: {resp}")
            
            result = handle_async_response(self.task_manager, "QoS creation", vvs_name, resp)
            logger.info(f"QoS rule for '{vvs_name}' created successfully")
            return result
        except Exception as e:
            logger.exception(f"Error creating QOS rule {qosRule}: {str(e) or repr(e)}")
            return e

    def create_qos(self, vvs_name, qos, **kwargs):
        logger.info(f">>>>>>>Entered create_qos: vvs_name='{vvs_name}'")
        try:
            logger.info(f"Calling _execute_create_qos with qos={qos}, vvs_name={vvs_name}, kwargs={kwargs}")
            response = self._execute_create_qos(vvs_name, qos, **kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"create_qos response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to create QoS due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited create_qos: vvs_name='{vvs_name}'")

    def _execute_modify_qos(self, name, **kwargs):
        logger.info(f"Starting QoS rule modification for '{name}'")
        # Build params dict for validation
        params_to_validate = {}
        # Merge kwargs into params for validation
        params_to_validate.update(kwargs)
        
        # Validate with params dict
        validate_qos_params(params_to_validate)
        
        # Get QoS UID with proper error handling
        resp_list = self.get_qos(name=name)
        if not resp_list:
            logger.error(f"QoS rule not found for modification: {name}")
            raise QosDoesNotExist(name=name)
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"QoS UID missing for: {name} in response {resp_list}")
            raise ValueError(f"QoS UID missing for: {name}")
        
        # Build payload from params and kwargs
        payload = {}
        
        # Add any additional kwargs to payload
        payload.update(kwargs)
        
        logger.info(f"Modifying QOS rule with payload: {payload}")
        try:
            response = self.session_mgr.rest_client.patch(f"/qosconfigs/{uid}", payload)
            logger.info(f"QoS modification initiated: {response}")
            
            result = handle_async_response(self.task_manager, "QoS modification", name, response)
            logger.info(f"QoS rule '{name}' modified successfully")
            return result
        except Exception as e:
            logger.exception(f"Error modifying QOS rule {payload}: {str(e) or repr(e)}")
            return e
        
    def modify_qos(self, name, **kwargs):
        logger.info(f">>>>>>>Entered modify_qos: name='{name}'")
        try:
            logger.info(f"Calling _execute_modify_qos with name={name}, kwargs={kwargs}")
            response = self._execute_modify_qos(name, **kwargs)
            if isinstance(response, Exception):
                raise response
            logger.info(f"modify_qos response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to modify QoS due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited modify_qos: name='{name}'")
    
    def _execute_delete_qos(self, name):
        logger.info(f"Starting QoS rule deletion for '{name}'")
        # Get QoS UID with proper error handling
        resp_list = self.get_qos(name)
        if not resp_list:
            logger.error(f"QoS rule not found for deletion: {name}")
            raise QosDoesNotExist(name=name)
        
        uid = resp_list[0].get("uid")
        if not uid:
            logger.error(f"QoS UID missing for: {name} in response {resp_list}")
            raise ValueError(f"QoS UID missing for: {name}")
        
        logger.info(f"Deleting QOS with uid={uid}")
        try:
            response = self.session_mgr.rest_client.delete(f"/qosconfigs/{uid}")
            logger.info(f"QoS deletion initiated: {response}")
            
            result = handle_async_response(self.task_manager, "QoS deletion", name, response)
            logger.info(f"QoS rule '{name}' deleted successfully")
            return result
        except Exception as e:
            logger.exception(f"Error deleting qos rule with uid {uid}: {str(e) or repr(e)}")
            return e
    
    def delete_qos(self, name):
        logger.info(f">>>>>>>Entered delete_qos: name='{name}'")
        try:
            logger.info(f"Calling _execute_delete_qos with name={name}")
            response = self._execute_delete_qos(name)
            if isinstance(response, Exception):
                raise response
            logger.info(f"delete_qos response: {response}")
            return response
        except Exception as e:
            logger.exception(f"Failed to delete QoS due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited delete_qos: name='{name}'")

    def get_qos(self, name):
        try:
            headers = {"experimentalfilter": "true"}
            endpoint = f"/qosconfigs?targetName={name}"
            logger.info(f"Getting QOS with endpoint={endpoint}, headers={headers}")
            response = self.session_mgr.rest_client.get(endpoint, headers=headers)
            logger.info(f"get_qos response: {response}")
            return response
        except HPEStorageException as e:
            logger.exception(f"HPEStorageException in get_qos: {str(e) or repr(e)}")
            raise

    def list_qos(self):
        try:
            logger.info("Listing all QOS configs")
            resp = self.session_mgr.rest_client.get("/qosconfigs")
            logger.info(f"list_qos response: {resp}")
            return resp.get("members", [])
        except HPEStorageException as e:
            logger.exception(f"HPEStorageException in list_qos: {str(e) or repr(e)}")
            raise
