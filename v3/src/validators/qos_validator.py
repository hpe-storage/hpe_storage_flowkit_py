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
from hpe_storage_flowkit_py.v3.src.core.logger import Logger

logger = Logger()

def validate_qos_params(params=None):
    """
    Validate QoS parameters.
    
    Args:
        params: Dictionary with QoS parameters:
            - allowAIQoS: Flag to force allow QoS rules even if Intelligent QoS is enabled (bool)
            - bandwidthMaxLimitKiB: I/O issue bandwidth maximum limit for QoS throttling (int64)
            - enable: If true, the QoS config is enabled. Otherwise, it is disabled (bool)
            - iopsMaxLimit: I/O issue count maximum limit for QoS throttling (int64)
            - targetName: Name of the QoS target (string, available since v2.5.0, ignored when modifying)
            - targetType: QoS target type - QOS_TGT_VV, QOS_TGT_VVSET, QOS_TGT_DOMAIN or QOS_TGT_SYSTEM (string, available since v2.5.0, ignored when modifying)
        
    Raises:
        ValueError: If validation fails or unknown parameters are provided
    """
    logger.info("Started validating QoS parameters")
    # Define allowed parameters - ONLY official API parameters
    ALLOWED_PARAMS = {
        'allowAIQoS', 'bandwidthMaxLimitKiB', 'enable', 'iopsMaxLimit',
        'targetName', 'targetType'
    }
    
    # If no params provided, validation is complete
    if params is None:
        return
    
    if not isinstance(params, dict):
        raise ValueError("QoS params must be a dictionary if provided.")
    
    # Check for unknown parameters
    unknown_params = set(params.keys()) - ALLOWED_PARAMS
    if unknown_params:
        raise ValueError(f"Unknown QoS parameter(s) not accepted by API: {', '.join(sorted(unknown_params))}")
    
    # Validate allowAIQoS
    if 'allowAIQoS' in params and params['allowAIQoS'] is not None:
        if not isinstance(params['allowAIQoS'], bool):
            raise ValueError("allowAIQoS must be a boolean")
    
    # Validate bandwidthMaxLimitKiB
    if 'bandwidthMaxLimitKiB' in params and params['bandwidthMaxLimitKiB'] is not None:
        if not isinstance(params['bandwidthMaxLimitKiB'], (int, float)):
            raise ValueError("bandwidthMaxLimitKiB must be a number (int64)")
        if params['bandwidthMaxLimitKiB'] <= 0:
            raise ValueError("bandwidthMaxLimitKiB must be a positive number")
    
    # Validate enable
    if 'enable' in params and params['enable'] is not None:
        if not isinstance(params['enable'], bool):
            raise ValueError("enable must be a boolean")
    
    # Validate iopsMaxLimit
    if 'iopsMaxLimit' in params and params['iopsMaxLimit'] is not None:
        if not isinstance(params['iopsMaxLimit'], (int, float)):
            raise ValueError("iopsMaxLimit must be a number (int64)")
        if params['iopsMaxLimit'] <= 0:
            raise ValueError("iopsMaxLimit must be a positive number")
    
    # Validate targetName (available since v2.5.0)
    if 'targetName' in params and params['targetName'] is not None:
        if not isinstance(params['targetName'], str):
            raise ValueError("targetName must be a string")
        if len(params['targetName']) < 1:
            raise ValueError("targetName cannot be empty")
    
    # Validate targetType (available since v2.5.0)
    if 'targetType' in params and params['targetType'] is not None:
        valid_target_types = ['QOS_TGT_VV', 'QOS_TGT_VVSET', 'QOS_TGT_DOMAIN', 'QOS_TGT_SYSTEM']
        if not isinstance(params['targetType'], str):
            raise ValueError("targetType must be a string")
        if params['targetType'] not in valid_target_types:
            raise ValueError(f"targetType must be one of: {', '.join(valid_target_types)}")
    
    logger.info("Completed validating QoS parameters")