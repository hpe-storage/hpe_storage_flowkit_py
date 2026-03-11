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

def validate_snapshot_params(volume_name=None, snapshot_name=None, params=None):
	"""
	Validate snapshot parameters.
	
	Args:
		volume_name: Parent volume name (required for create operations)
		snapshot_name: Snapshot name (required for most operations)
		params: Dictionary with snapshot parameters:
			- comment: Free-form comments about volume snapshot (string)
			- customName: User specified name for the snapshot (string)
			- expireSecs: Expiration value specified for volume snapshot (uint64)
			- id: ID of the snapshot to be created (uint64)
			- namePattern: Pattern that will be used to generate the name of snapshot (enum: PARENT_TIMESTAMP, PARENT_SEC_SINCE_EPOCH, CUSTOM)
			- readOnly: If true snapshot mode is read only else read/write (bool)
			- retainSecs: Retention value specified for volume snapshot (uint64)
			
			Note: 'action' parameter is NOT validated as it's set internally by the workflow
		
	Raises:
		ValueError: If validation fails or unknown parameters are provided
	"""
	logger.info("Started validating snapshot parameters")
	# Validate volume_name if provided
	if volume_name is not None:
		if not isinstance(volume_name, str):
			raise ValueError("Volume name must be a string")
		if not volume_name or volume_name.strip() == "":
			raise ValueError("Volume name cannot be empty")
	
	# Validate snapshot_name if provided
	if snapshot_name is not None:
		if not isinstance(snapshot_name, str):
			raise ValueError("Snapshot name must be a string")
		if not snapshot_name or snapshot_name.strip() == "":
			raise ValueError("Snapshot name cannot be empty")
	
	# Define allowed parameters - ONLY official API parameters (excluding 'action' which is set by workflow)
	ALLOWED_PARAMS = {
		'comment', 'customName', 'expireSecs', 'id', 'namePattern', 
		'readOnly', 'retainSecs'
	}
	
	# If no params provided, validation is complete
	if params is None:
		return
	
	if not isinstance(params, dict):
		raise ValueError("Snapshot params must be a dictionary if provided.")
	
	# Check for unknown parameters
	unknown_params = set(params.keys()) - ALLOWED_PARAMS
	if unknown_params:
		raise ValueError(f"Unknown snapshot parameter(s) not accepted by API: {', '.join(sorted(unknown_params))}")
	
	# Validate comment
	if 'comment' in params and params['comment'] is not None:
		if not isinstance(params['comment'], str):
			raise ValueError("comment must be a string")
	
	# Validate customName
	if 'customName' in params and params['customName'] is not None:
		if not isinstance(params['customName'], str):
			raise ValueError("customName must be a string")
		if len(params['customName']) < 1:
			raise ValueError("customName cannot be empty")
	
	# Validate expireSecs
	if 'expireSecs' in params and params['expireSecs'] is not None:
		if not isinstance(params['expireSecs'], (int, float)):
			raise ValueError("expireSecs must be a number (uint64)")
		if params['expireSecs'] < 0:
			raise ValueError("expireSecs must be a non-negative number")
	
	# Validate id
	if 'id' in params and params['id'] is not None:
		if not isinstance(params['id'], (int, float)):
			raise ValueError("id must be a number (uint64)")
		if params['id'] < 0:
			raise ValueError("id must be a non-negative number")
	
	# Validate namePattern
	if 'namePattern' in params and params['namePattern'] is not None:
		valid_name_patterns = ['PARENT_TIMESTAMP', 'PARENT_SEC_SINCE_EPOCH', 'CUSTOM']
		if not isinstance(params['namePattern'], str):
			raise ValueError("namePattern must be a string")
		if params['namePattern'] not in valid_name_patterns:
			raise ValueError(f"namePattern must be one of: {', '.join(valid_name_patterns)}")
	
	# Validate readOnly
	if 'readOnly' in params and params['readOnly'] is not None:
		if not isinstance(params['readOnly'], bool):
			raise ValueError("readOnly must be a boolean")
	
	# Validate retainSecs
	if 'retainSecs' in params and params['retainSecs'] is not None:
		if not isinstance(params['retainSecs'], (int, float)):
			raise ValueError("retainSecs must be a number (uint64)")
		if params['retainSecs'] < 0:
			raise ValueError("retainSecs must be a non-negative number")
	
	logger.info("Completed validating snapshot parameters")


def validate_promote_snapshot_volume_params(snapshot_name=None,params=None):
	"""
	Validate promote virtual copy parameters.
	
	Args:
		params: Dictionary with promote parameters:
			- online: With this option the promote operation will be executed while the target volume has VLUN exports (bool, available since v2.6.0)
			- priority: Priority value for the promote action (enum: PRIORITYTYPE_HIGH, PRIORITYTYPE_MED, PRIORITYTYPE_LOW)
			- rcp: Indicates if promote action to proceed even if the RW parent volume is currently in a Remote Copy volume group (bool)
			- target: Target volume for the promote action (string)
			
			Note: 'action' parameter is NOT validated as it's set internally by the workflow (PROMOTE_SNAPSHOT_VOLUME)
		
	Raises:
		ValueError: If validation fails or unknown parameters are provided
	"""
	logger.info("Started validating promote snapshot parameters")
		# Validate snapshot_name if provided
	if snapshot_name is not None:
		if not isinstance(snapshot_name, str):
			raise ValueError("Snapshot name must be a string")
		if not snapshot_name or snapshot_name.strip() == "":
			raise ValueError("Snapshot name cannot be empty")
	# Define allowed parameters - ONLY official API parameters (excluding 'action' which is set by workflow)
	ALLOWED_PARAMS = {
		'online', 'priority', 'rcp', 'target'
	}
	
	# If no params provided, validation is complete
	if params is None:
		return
	
	if not isinstance(params, dict):
		raise ValueError("Promote params must be a dictionary if provided.")
	
	# Check for unknown parameters
	unknown_params = set(params.keys()) - ALLOWED_PARAMS
	if unknown_params:
		raise ValueError(f"Unknown promote parameter(s) not accepted by API: {', '.join(sorted(unknown_params))}")
	
	# Validate online (available since v2.6.0)
	if 'online' in params and params['online'] is not None:
		if not isinstance(params['online'], bool):
			raise ValueError("online must be a boolean")
	
	# Validate priority
	if 'priority' in params and params['priority'] is not None:
		valid_priorities = ['PRIORITYTYPE_HIGH', 'PRIORITYTYPE_MED', 'PRIORITYTYPE_LOW']
		if not isinstance(params['priority'], str):
			raise ValueError("priority must be a string")
		if params['priority'] not in valid_priorities:
			raise ValueError(f"priority must be one of: {', '.join(valid_priorities)}")
	
	# Validate rcp
	if 'rcp' in params and params['rcp'] is not None:
		if not isinstance(params['rcp'], bool):
			raise ValueError("rcp must be a boolean")
	
	# Validate target
	if 'target' in params and params['target'] is not None:
		if not isinstance(params['target'], str):
			raise ValueError("target must be a string")
		if len(params['target']) < 1:
			raise ValueError("target cannot be empty")
	
	logger.info("Completed validating promote snapshot parameters")
