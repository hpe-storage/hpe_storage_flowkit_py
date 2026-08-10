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
from hpe_storage_flowkit_py.v1.src.core.exceptions import InvalidParameterValue

RCG_NAME_MIN = 1
RCG_NAME_MAX = 31

def _validate_name(name, param, min_len=1, max_len=31):
	if name is None:
		raise InvalidParameterValue(param, f"{param} cannot be null")
	if not isinstance(name, str):
		raise InvalidParameterValue(param, f"{param} must be a string")
	ln = len(name)
	if ln < min_len or ln > max_len:
		raise InvalidParameterValue(param, f"{param} length must be between {min_len} and {max_len} characters")

def validate_remote_copy_group_params(remote_copy_group_name,
									  local_user_cpg=None,
									  local_snap_cpg=None,
									  unset_user_cpg=False,
									  unset_snap_cpg=False,
									  volume_name=None,
									  admit_volume_targets=None,
									  snapshot_name=None,
									  volume_auto_creation=False,
									  skip_initial_sync=False,
									  different_secondary_wwn=False,
									  keep_snap=False,
									  remove_secondary_volume=False,
									  target_name=None,
									  source_port=None,
									  target_port_wwn_or_ip=None,
									  target_mode=None,
									  storage_system_ip=None):
	"""Generic parameter validator for Remote Copy related operations.

	This function applies validation rules based purely on the presence / combination
	of parameters (no operation discriminator). If a parameter is supplied, it must
	satisfy its contract. Violations raise InvalidParameterValue.
	"""
	# Remote copy group name (create / modify / delete / add volume / remove volume / admit target / dismiss target)
	
	_validate_name(remote_copy_group_name, 'remote_copy_group_name', RCG_NAME_MIN, RCG_NAME_MAX)

	# CPG pairing rule (applies whenever one of the local CPGs is provided)
	if (local_user_cpg or local_snap_cpg) and not (local_user_cpg and local_snap_cpg):
		raise InvalidParameterValue('local_user_cpg/local_snap_cpg', 'Both local_user_cpg and local_snap_cpg must be provided together or omitted')
	if (unset_user_cpg or unset_snap_cpg) and (local_user_cpg or local_snap_cpg):
		raise InvalidParameterValue('unset_user_cpg/unset_snap_cpg', 'Cannot provide local CPGs while unset flags are true')
	if local_user_cpg is not None and not isinstance(local_user_cpg, str):
		raise InvalidParameterValue('local_user_cpg', 'Must be a string')
	if local_snap_cpg is not None and not isinstance(local_snap_cpg, str):
		raise InvalidParameterValue('local_snap_cpg', 'Must be a string')

	# Volume operations (add / remove volume)
	if volume_name is not None:
		_validate_name(volume_name, 'volume_name', 1, 31)
	# Add volume specific relationships
	if snapshot_name and volume_auto_creation:
		raise InvalidParameterValue('volume_auto_creation', 'volumeAutoCreation cannot be true when snapshot_name is specified')
	if snapshot_name and skip_initial_sync:
		raise InvalidParameterValue('skip_initial_sync', 'skipInitialSync cannot be true when snapshot_name is specified')
	if different_secondary_wwn and not volume_auto_creation:
		raise InvalidParameterValue('different_secondary_wwn', 'differentSecondaryWWN cannot be true when volumeAutoCreation is false')
	if admit_volume_targets is not None and not isinstance(admit_volume_targets, list):
		raise InvalidParameterValue('admit_volume_targets', 'Must be a list')
	# Remove volume exclusivity
	if keep_snap and remove_secondary_volume:
		raise InvalidParameterValue('keep_snap/remove_secondary_volume', 'keepSnap and removeSecondaryVolume cannot both be true')

	# Link operations (admit / dismiss link) - if any of the trio is provided, all must be valid non-empty strings
	link_params = [target_name, source_port, target_port_wwn_or_ip]
	if any(p is not None for p in link_params):
		if target_name is None:
			raise InvalidParameterValue('target_name', 'Target name cannot be null for link operation')
		if source_port is None:
			raise InvalidParameterValue('source_port', 'Source port cannot be null for link operation')
		if target_port_wwn_or_ip is None:
			raise InvalidParameterValue('target_port_wwn_or_ip', 'Target port WWN/IP cannot be null for link operation')

	# Target admit / dismiss operations
	target_related = [target_mode, storage_system_ip]
	if any(p is not None for p in target_related):
		if target_name is None:
			raise InvalidParameterValue('target_name', 'Target name cannot be null for target operation')
		if storage_system_ip is None:
			raise InvalidParameterValue('storage_system_ip', 'Storage system IP cannot be null for target operation')
		if target_mode is None:
			raise InvalidParameterValue('target_mode', 'Target mode cannot be null for target operation')

	return True

