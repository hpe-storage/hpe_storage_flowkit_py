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

def validate_cpg_params(name, params=None):
	"""
	Validate CPG (Common Provisioning Group) parameters.
	
	Args:
		name: CPG name (required, 1-31 characters)
		params: Dictionary with optional parameters:
			- cage: Cage number that the CPG is allowed to use (string, available since v2.6.0)
			- domain: Name of the domain that the CPG belongs to (string)
			- growthLimitMiB: Limit size in MiB beyond which the admin/data space will not grow (uint64)
			- growthSizeMiB: Amount of admin/data LD storage in MiB created on each auto-grow (uint64)
			- growthWarnMiB: Size in MiB of the admin/data space at which a warning alert is generated (uint64)
			- ha: Requested High Availability setting (enum: HAJBOD_JBOD or HAJBOD_DISK)
			- keyValuePairs: Key value pairs assigned to the object (dict, available since v2.6.0)
			- position: Position number that the CPG is allowed to use (string, available since v2.6.0)
	
	Raises:
		ValueError: If any validation fails or unknown parameters are provided
	"""
	logger.info("Started validating CPG parameters")
	# Define allowed parameters - ONLY official API parameters
	ALLOWED_PARAMS = {
		'cage', 'domain', 'growthLimitMiB', 'growthSizeMiB', 'growthWarnMiB',
		'ha', 'keyValuePairs', 'position'
	}
	
	# Validate name
	if not name or not isinstance(name, str):
		raise ValueError("CPG name must be a non-empty string.")
	if len(name) < 1 or len(name) > 31:
		raise ValueError("CPG create failed. CPG name must be atleast 1 character and not more than 31 characters")
	
	# If no params provided, validation is complete
	if params is None:
		return
	
	if not isinstance(params, dict):
		raise ValueError("CPG params must be a dictionary if provided.")
	
	# Check for unknown parameters
	unknown_params = set(params.keys()) - ALLOWED_PARAMS
	if unknown_params:
		raise ValueError(f"Unknown CPG parameter(s) not accepted by API: {', '.join(sorted(unknown_params))}")
	
	# Validate cage (available since v2.6.0)
	if 'cage' in params and params['cage'] is not None:
		if not isinstance(params['cage'], str):
			raise ValueError("cage must be a string")
		if len(params['cage']) < 1:
			raise ValueError("cage cannot be empty")
	
	# Validate domain
	if 'domain' in params and params['domain'] is not None:
		if not isinstance(params['domain'], str):
			raise ValueError("domain must be a string")
		if len(params['domain']) < 1:
			raise ValueError("domain name cannot be empty")
	
	# Validate position (available since v2.6.0)
	if 'position' in params and params['position'] is not None:
		if not isinstance(params['position'], str):
			raise ValueError("position must be a string")
		if len(params['position']) < 1:
			raise ValueError("position cannot be empty")
	
	# Validate keyValuePairs (available since v2.6.0)
	if 'keyValuePairs' in params and params['keyValuePairs'] is not None:
		if not isinstance(params['keyValuePairs'], dict):
			raise ValueError("keyValuePairs must be a dictionary")
	
	# Validate growthLimitMiB
	if 'growthLimitMiB' in params and params['growthLimitMiB'] is not None:
		if not isinstance(params['growthLimitMiB'], (int, float)):
			raise ValueError("growthLimitMiB must be a number (uint64)")
		elif params['growthLimitMiB'] < 0:
			raise ValueError("growthLimitMiB must be a non-negative number")
	
	# Validate growthSizeMiB
	if 'growthSizeMiB' in params and params['growthSizeMiB'] is not None:
		if not isinstance(params['growthSizeMiB'], (int, float)):
			raise ValueError("growthSizeMiB must be a number (uint64)")
		elif params['growthSizeMiB'] < 0:
			raise ValueError("growthSizeMiB must be a non-negative number")
	
	# Validate growthWarnMiB
	if 'growthWarnMiB' in params and params['growthWarnMiB'] is not None:
		if not isinstance(params['growthWarnMiB'], (int, float)):
			raise ValueError("growthWarnMiB must be a number (uint64)")
		elif params['growthWarnMiB'] < 0:
			raise ValueError("growthWarnMiB must be a non-negative number")
	
	# Validate ha (high availability)
	if 'ha' in params and params['ha'] is not None:
		valid_ha_values = ['HAJBOD_JBOD', 'HAJBOD_DISK']
		ha_value = params['ha']
		if not isinstance(ha_value, str):
			raise ValueError("ha must be a string")
		if ha_value not in valid_ha_values:
			raise ValueError(f"ha must be one of: {', '.join(valid_ha_values)}")
	
	logger.info("Completed validating CPG parameters")
