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

def validate_clone_params(src_name=None,dest_name=None, params=None):
    """
    Validate parameters for clone operations using v3 API (CREATE_VVCOPY).
    
    Args:
        src_name: Source volume name (required)
        params: Dictionary with clone parameters:
            - addToSet: Adds the volume copies to the specified volume set (string, only with online option)
            - appSetBusinessUnit: Business unit for application using this set (string)
            - appSetComments: Free-form comments about virtual volume set (string)
            - appSetExcludeAIQoS: Exclude virtual volume set from aiqos (enum: yes, no)
            - appSetImportance: Virtual volume set importance (string)
            - appSetType: Type of the application using this set (string)
            - bulkvv: Make the new created target volume VMware specific (bool)
            - destination: Destination volume name or volume set name (string, required, set name must start with 'set:')
            - destinationCpg: Destination CPG for destination volume (string, mandatory if online=True)
            - enableResync: Re-synchronize destination volume with parent using saved snapshot (bool)
            - expireSecs: Expiration value for volume snapshot (uint64)
            - online: Destination can be immediately exported and automatically created (bool)
            - priority: Priority of the copy operation (enum: PRIORITYTYPE_HIGH, PRIORITYTYPE_MED, PRIORITYTYPE_LOW)
            - reduce: Volume should use dedup and compression (bool)
            - retainSecs: Retention value for volume snapshot (uint64)
            - selectionType: How volumes are selected from destination set (enum: PARENTVV_INDEX, PARENTVV_PREFIX)
            - skipZero: Only copy allocated portions of thin provisioned source (bool)
            
            Note: 'action' parameter is NOT validated as it's set internally by the workflow (CREATE_VVCOPY)
    
    Raises:
        ValueError: If validation fails or unknown parameters are provided
    """
    logger.info("Started validating clone parameters")
    # Validate src_name
    if src_name is not None:
        if not isinstance(src_name, str) or not src_name.strip():
            raise ValueError("Source volume name must be a non-empty string.")
    if dest_name is not None:
        if not isinstance(dest_name, str) or not dest_name.strip():
            raise ValueError("Destination volume name must be a non-empty string.")
    
    # Define allowed parameters - ONLY official API parameters (excluding 'action' which is set by workflow)
    ALLOWED_PARAMS = {
        'addToSet', 'appSetBusinessUnit', 'appSetComments', 'appSetExcludeAIQoS',
        'appSetImportance', 'appSetType', 'bulkvv', 'destination', 'destinationCpg',
        'enableResync', 'expireSecs', 'online', 'priority', 'reduce',
        'retainSecs', 'selectionType', 'skipZero'
    }
    
    # If no params provided, validation is complete
    if params is None:
        return
    
    if not isinstance(params, dict):
        raise ValueError("Clone params must be a dictionary if provided.")
    
    # Check for unknown parameters
    unknown_params = set(params.keys()) - ALLOWED_PARAMS
    if unknown_params:
        raise ValueError(f"Unknown clone parameter(s) not accepted by API: {', '.join(sorted(unknown_params))}")
    
    # Validate destination (required)
    if 'destination' in params and params['destination'] is not None:
        if not isinstance(params['destination'], str) or not params['destination'].strip():
            raise ValueError("destination must be a non-empty string")
        # Check if destination is a volume set (must start with 'set:')
        if params['destination'].startswith('set:') and len(params['destination']) <= 4:
            raise ValueError("Volume set name must have content after 'set:' prefix")
    
    # Validate destinationCpg
    if 'destinationCpg' in params and params['destinationCpg'] is not None:
        if not isinstance(params['destinationCpg'], str) or not params['destinationCpg'].strip():
            raise ValueError("destinationCpg must be a non-empty string")
    
    # Validate online and check destinationCpg requirement
    if 'online' in params and params['online'] is not None:
        if not isinstance(params['online'], bool):
            raise ValueError("online must be a boolean")
        # If online=True, destinationCpg is mandatory
        if params['online'] and 'destinationCpg' not in params:
            raise ValueError("destinationCpg is mandatory when online=True")
    
    # Validate addToSet (can only be used with online option)
    if 'addToSet' in params and params['addToSet'] is not None:
        if not isinstance(params['addToSet'], str):
            raise ValueError("addToSet must be a string")
        if len(params['addToSet']) < 1:
            raise ValueError("addToSet cannot be empty")
        # Check if online is True when addToSet is used
        if not params.get('online', False):
            raise ValueError("addToSet can only be used with online option")
    
    # Validate appSetBusinessUnit
    if 'appSetBusinessUnit' in params and params['appSetBusinessUnit'] is not None:
        if not isinstance(params['appSetBusinessUnit'], str):
            raise ValueError("appSetBusinessUnit must be a string")
    
    # Validate appSetComments
    if 'appSetComments' in params and params['appSetComments'] is not None:
        if not isinstance(params['appSetComments'], str):
            raise ValueError("appSetComments must be a string")
    
    # Validate appSetExcludeAIQoS
    if 'appSetExcludeAIQoS' in params and params['appSetExcludeAIQoS'] is not None:
        valid_values = ['yes', 'no']
        if not isinstance(params['appSetExcludeAIQoS'], str):
            raise ValueError("appSetExcludeAIQoS must be a string")
        if params['appSetExcludeAIQoS'] not in valid_values:
            raise ValueError(f"appSetExcludeAIQoS must be one of: {', '.join(valid_values)}")
    
    # Validate appSetImportance
    if 'appSetImportance' in params and params['appSetImportance'] is not None:
        if not isinstance(params['appSetImportance'], str):
            raise ValueError("appSetImportance must be a string")
    
    # Validate appSetType
    if 'appSetType' in params and params['appSetType'] is not None:
        if not isinstance(params['appSetType'], str):
            raise ValueError("appSetType must be a string")
    
    # Validate bulkvv
    if 'bulkvv' in params and params['bulkvv'] is not None:
        if not isinstance(params['bulkvv'], bool):
            raise ValueError("bulkvv must be a boolean")
    
    # Validate enableResync
    if 'enableResync' in params and params['enableResync'] is not None:
        if not isinstance(params['enableResync'], bool):
            raise ValueError("enableResync must be a boolean")
    
    # Validate expireSecs
    if 'expireSecs' in params and params['expireSecs'] is not None:
        if not isinstance(params['expireSecs'], (int, float)):
            raise ValueError("expireSecs must be a number (uint64)")
        if params['expireSecs'] < 0:
            raise ValueError("expireSecs must be a non-negative number")
    
    # Validate priority
    if 'priority' in params and params['priority'] is not None:
        valid_priorities = ['PRIORITYTYPE_HIGH', 'PRIORITYTYPE_MED', 'PRIORITYTYPE_LOW']
        if not isinstance(params['priority'], str):
            raise ValueError("priority must be a string")
        if params['priority'] not in valid_priorities:
            raise ValueError(f"priority must be one of: {', '.join(valid_priorities)}")
    
    # Validate reduce
    if 'reduce' in params and params['reduce'] is not None:
        if not isinstance(params['reduce'], bool):
            raise ValueError("reduce must be a boolean")
    
    # Validate retainSecs
    if 'retainSecs' in params and params['retainSecs'] is not None:
        if not isinstance(params['retainSecs'], (int, float)):
            raise ValueError("retainSecs must be a number (uint64)")
        if params['retainSecs'] < 0:
            raise ValueError("retainSecs must be a non-negative number")
    
    # Validate selectionType
    if 'selectionType' in params and params['selectionType'] is not None:
        valid_selection_types = ['PARENTVV_INDEX', 'PARENTVV_PREFIX']
        if not isinstance(params['selectionType'], str):
            raise ValueError("selectionType must be a string")
        if params['selectionType'] not in valid_selection_types:
            raise ValueError(f"selectionType must be one of: {', '.join(valid_selection_types)}")
    
    # Validate skipZero
    if 'skipZero' in params and params['skipZero'] is not None:
        if not isinstance(params['skipZero'], bool):
            raise ValueError("skipZero must be a boolean")
    
    logger.info("Completed validating clone parameters")




def validate_resync_physical_copy(volume_name=None,params=None):
    """
    Validate resync physical copy parameters.
    
    Args:
        params: Dictionary with resync parameters:
            - priority: Priority value for the resync action (enum: PRIORITYTYPE_HIGH, PRIORITYTYPE_MED, PRIORITYTYPE_LOW)
            
            Note: 'action' parameter is NOT validated as it's set internally by the workflow (RESYNC_VVCOPY)
    
    Raises:
        ValueError: If validation fails or unknown parameters are provided
    """
    logger.info("Started validating resync physical copy parameters")
    if volume_name is not None:
        if not isinstance(volume_name, str):
            raise ValueError("Volume name must be a string")
        if not volume_name or volume_name.strip() == "":
            raise ValueError("Volume name cannot be empty")
    # Define allowed parameters - ONLY official API parameters (excluding 'action' which is set by workflow)
    ALLOWED_PARAMS = {
        'priority'
    }
    
    # If no params provided, validation is complete
    if params is None:
        return
    
    if not isinstance(params, dict):
        raise ValueError("Resync params must be a dictionary if provided.")
    
    # Check for unknown parameters
    unknown_params = set(params.keys()) - ALLOWED_PARAMS
    if unknown_params:
        raise ValueError(f"Unknown resync parameter(s) not accepted by API: {', '.join(sorted(unknown_params))}")
    
    # Validate priority
    if 'priority' in params and params['priority'] is not None:
        valid_priorities = ['PRIORITYTYPE_HIGH', 'PRIORITYTYPE_MED', 'PRIORITYTYPE_LOW']
        if not isinstance(params['priority'], str):
            raise ValueError("priority must be a string")
        if params['priority'] not in valid_priorities:
            raise ValueError(f"priority must be one of: {', '.join(valid_priorities)}")
    
    logger.info("Completed validating resync physical copy parameters")