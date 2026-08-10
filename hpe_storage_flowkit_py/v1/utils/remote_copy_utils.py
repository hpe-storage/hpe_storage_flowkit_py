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
"""Utility helpers for Remote Copy Group operations."""
from hpe_storage_flowkit_py.v1.src.validators.remote_copy_validator import validate_remote_copy_group_params
from hpe_storage_flowkit_py.v1.src.core.exceptions import InvalidParameterValue

# Remote Copy mode string tokens (Ansible / user input) and their WSAPI numeric codes
RC_MODE_SYNC_TOKEN = 'sync'
RC_MODE_PERIODIC_TOKEN = 'periodic'
RC_MODE_ASYNC_TOKEN = 'async'

RC_MODE_SYNC = 1
RC_MODE_PERIODIC = 3
RC_MODE_ASYNC = 4

RC_START_STATE = 3
RC_STOP_STATE = 5

_RC_MODE_MAP = {
	RC_MODE_SYNC_TOKEN: RC_MODE_SYNC,
	RC_MODE_PERIODIC_TOKEN: RC_MODE_PERIODIC,
	RC_MODE_ASYNC_TOKEN: RC_MODE_ASYNC,
}


def _normalize_targets(remote_copy_targets):
	"""Return (normalized_targets, target_names) with validated entries.

	Accepts user-supplied list of dicts; converts keys / maps mode tokens to numeric
	constants using _RC_MODE_MAP. Raises InvalidParameterValue on any invalid key
	or mode.
	"""
	normalized_targets = []
	target_names = []
	for target_dict in remote_copy_targets or []:
		target = {}
		for key, value in (target_dict or {}).items():
			if key == 'target_name':
				if value is None:
					raise InvalidParameterValue('target_name', 'Target name is null')
				target['targetName'] = value
				target_names.append(value)
			elif key == 'target_mode':
				target_mode = _RC_MODE_MAP.get(str(value).lower()) if value is not None else None
				if not target_mode:
					raise InvalidParameterValue('target_mode', 'Target mode is invalid')
				target['mode'] = target_mode
			elif key == 'user_cpg':
				target['userCPG'] = value
			elif key == 'snap_cpg':
				target['snapCPG'] = value
			else:
				raise InvalidParameterValue(key, f"Unexpected parameter '{key}' for target descriptor")
		normalized_targets.append(target)
	return normalized_targets, target_names



def preprocess_create_remote_copy_group(remote_copy_group_name,
                                       domain=None,
                                       remote_copy_targets=None,
                                       local_user_cpg=None,
                                       local_snap_cpg=None):
	"""Validate & normalize target descriptors for create operation.
	Returns (normalized_targets, target_names)."""
	validate_remote_copy_group_params(remote_copy_group_name,
		local_user_cpg=local_user_cpg,
		local_snap_cpg=local_snap_cpg)
	normalized_targets, target_names = _normalize_targets(remote_copy_targets)
	payload_params = {}
	if domain:
		payload_params['domain'] = domain
	if local_user_cpg:
		payload_params['localUserCPG'] = local_user_cpg
	if local_snap_cpg:
		payload_params['localSnapCPG'] = local_snap_cpg
	return normalized_targets, target_names, payload_params


def preprocess_delete_remote_copy_group(remote_copy_group_name):
	"""Basic validation for delete operation (name only)."""
	validate_remote_copy_group_params(remote_copy_group_name)


def _normalize_modify_targets(modify_targets):
	"""Transform modify_targets list into WSAPI shape.

	Supports keys:
	  target_name -> targetName
	  remote_user_cpg -> remoteUserCPG
	  remote_snap_cpg -> remoteSnapCPG
	  sync_period -> syncPeriod
	  rm_sync_period -> rmSyncPeriod
	  target_mode -> mode (mapped via _RC_MODE_MAP)
	  snap_frequency -> snapFrequency
	  rm_snap_frequency -> rmSnapFrequency
	  policies -> policies (passed as-is)
	"""
	transformed = []
	target_names = []
	for target_dict in modify_targets or []:
		ws_target = {}
		for key, value in (target_dict or {}).items():
			if key == 'target_name':
				if value is None:
					raise InvalidParameterValue('target_name', 'Target name is null')
				ws_target['targetName'] = value
				target_names.append(value)
			elif key == 'remote_user_cpg':
				ws_target['remoteUserCPG'] = value
			elif key == 'remote_snap_cpg':
				ws_target['remoteSnapCPG'] = value
			elif key == 'sync_period':
				ws_target['syncPeriod'] = value
			elif key == 'rm_sync_period':
				ws_target['rmSyncPeriod'] = value
			elif key == 'target_mode':
				mode_val = _RC_MODE_MAP.get(str(value).lower()) if value is not None else None
				if not mode_val:
					raise InvalidParameterValue('target_mode', 'Target mode is invalid')
				ws_target['mode'] = mode_val
			elif key == 'snap_frequency':
				ws_target['snapFrequency'] = value
			elif key == 'rm_snap_frequency':
				ws_target['rmSnapFrequency'] = value
			elif key == 'policies':
				ws_target['policies'] = value
			else:
				raise InvalidParameterValue(key, f"Unexpected parameter '{key}' for modify target descriptor")
		transformed.append(ws_target)
	return transformed, target_names


def _normalize_admit_volume_targets(admit_volume_targets):
	"""Normalize admit_volume_targets list into WSAPI shape.

	Each entry must include:
	  target_name -> targetName (1-31 chars)
	  sec_volume_name -> secVolumeName (1-31 chars)

	Returns (normalized_targets, target_names)
	"""
	normalized = []
	target_names = []
	for target_dict in admit_volume_targets or []:
		if not isinstance(target_dict, dict):
			raise InvalidParameterValue('admit_volume_targets', 'Each target entry must be a dict')
		ws_target = {}
		for key, value in target_dict.items():
			if key == 'target_name':
				if value is None:
					raise InvalidParameterValue('target_name', 'Target name is null')
				if not isinstance(value, str) or not (1 <= len(value) <= 31):
					raise InvalidParameterValue('target_name', 'Target name must be 1-31 characters')
				ws_target['targetName'] = value
				target_names.append(value)
			elif key == 'sec_volume_name':
				if value is None:
					raise InvalidParameterValue('sec_volume_name', 'Secondary volume is null')
				if not isinstance(value, str) or not (1 <= len(value) <= 31):
					raise InvalidParameterValue('sec_volume_name', 'Secondary volume name must be 1-31 characters')
				ws_target['secVolumeName'] = value
			else:
				raise InvalidParameterValue(key, f"Unexpected parameter name '{key}' in admit_volume_targets entry")
		# Ensure required keys present
		if 'targetName' not in ws_target or 'secVolumeName' not in ws_target:
			raise InvalidParameterValue('admit_volume_targets', 'Each target entry must include target_name and sec_volume_name')
		normalized.append(ws_target)
	return normalized, target_names



def preprocess_add_volume_to_remote_copy_group(remote_copy_group_name, volume_name, admit_volume_targets,
											  snapshot_name=None, volume_auto_creation=False,
											  skip_initial_sync=False, different_secondary_wwn=False):
	"""Validate and build payload for add volume operation."""
	# Explicit required volume name check (generic validator only enforces if provided)
	if volume_name is None:
		raise InvalidParameterValue('volume_name', 'Volume name cannot be null')
	# Run generic validation (length / mutual exclusions)
	validate_remote_copy_group_params(remote_copy_group_name,
		volume_name=volume_name,
		admit_volume_targets=admit_volume_targets,
		snapshot_name=snapshot_name,
		volume_auto_creation=volume_auto_creation,
		skip_initial_sync=skip_initial_sync,
		different_secondary_wwn=different_secondary_wwn)

	# Normalize admit volume targets via helper
	transformed_targets, target_names = _normalize_admit_volume_targets(admit_volume_targets)
	payload_params={}
	if snapshot_name:
		payload_params['snapshotName'] = snapshot_name
	if volume_auto_creation:
		payload_params['volumeAutoCreation'] = True
	if skip_initial_sync:
		payload_params['skipInitialSync'] = True
	if different_secondary_wwn:
		payload_params['differentSecondaryWWN'] = True
	return transformed_targets, target_names, payload_params  


def preprocess_remove_volume_from_remote_copy_group(remote_copy_group_name, volume_name,
											   keep_snap=False, remove_secondary_volume=False):
	"""Validate and build payload for remove volume operation."""
	validate_remote_copy_group_params(remote_copy_group_name,
		volume_name=volume_name,
		keep_snap=keep_snap,
		remove_secondary_volume=remove_secondary_volume)
	

def preprocess_modify_remote_copy_group(remote_copy_group_name,
									   modify_targets=None,
									   local_user_cpg=None,
									   local_snap_cpg=None,
									   unset_user_cpg=False,
									   unset_snap_cpg=False):
	"""Validate & normalize parameters for modify operation.

	Returns (normalized_modify_targets, target_names)
	"""
	validate_remote_copy_group_params(remote_copy_group_name,
		local_user_cpg=local_user_cpg,
		local_snap_cpg=local_snap_cpg,
		unset_user_cpg=unset_user_cpg,
		unset_snap_cpg=unset_snap_cpg)
	normalized, target_names = _normalize_modify_targets(modify_targets)
	payload = {}
	if normalized:
		payload['targets'] = normalized
	if unset_user_cpg:
		payload['unsetUserCPG'] = True
	if unset_snap_cpg:
		payload['unsetSnapCPG'] = True
	if local_user_cpg:
		payload['localUserCPG'] = local_user_cpg
	if local_snap_cpg:
		payload['localSnapCPG'] = local_snap_cpg
	return payload, target_names


def preprocess_start_remote_copy_group(remote_copy_group_name,
									  skip_initial_sync=False,
									  target_name=None,
									  starting_snapshots=None):
	"""Validate parameters for starting a remote copy group.

	starting_snapshots: list of dicts each with keys volumeName (required) and optional snapshotName.
	Returns payload (dict) to merge into action request.
	"""
	# Reuse generic validator (ensures name length); target_name optional but if starting snapshots provided
	# they must be a list of dicts with at minimum volumeName
	validate_remote_copy_group_params(remote_copy_group_name)
	if starting_snapshots is not None:
		if not isinstance(starting_snapshots, list):
			raise InvalidParameterValue('starting_snapshots', 'Must be a list of dicts')
		norm_snaps = []
		for entry in starting_snapshots:
			if not isinstance(entry, dict):
				raise InvalidParameterValue('starting_snapshots', 'Each entry must be a dict')
			vol = entry.get('volumeName') or entry.get('volume_name')
			if vol is None:
				raise InvalidParameterValue('starting_snapshots.volumeName', 'volumeName is required')
			_validate_name = lambda n: (len(n) >=1 and len(n) <=31)
			if not _validate_name(vol):
				raise InvalidParameterValue('starting_snapshots.volumeName', 'volumeName length invalid (1-31)')
			snap = entry.get('snapshotName') or entry.get('snapshot_name')
			snap_dict = {'volumeName': vol}
			if snap:
				snap_dict['snapshotName'] = snap
			norm_snaps.append(snap_dict)
		starting_snapshots = norm_snaps
	payload = {}
	if skip_initial_sync:
		payload['skipInitialSync'] = skip_initial_sync
	if target_name:
		payload['targetName'] = target_name
	if starting_snapshots:
		payload['startingSnapshots'] = starting_snapshots
	return payload


def preprocess_stop_remote_copy_group(remote_copy_group_name,
									 no_snapshot=False,
									 target_name=None):
	"""Validate parameters for stopping a remote copy group.

	Returns payload (dict) to merge into action request.
	"""
	validate_remote_copy_group_params(remote_copy_group_name)
	payload = {}
	if no_snapshot:
		payload['noSnapshot'] = True
	if target_name:
		payload['targetName'] = target_name
	return payload


def preprocess_synchronize_remote_copy_group(remote_copy_group_name,
											no_resync_snapshot=False,
											target_name=None,
											full_sync=False):
	"""Validate parameters for synchronizing (action=5) a remote copy group.

	Returns payload dict for workflow (without action code).
	"""
	validate_remote_copy_group_params(remote_copy_group_name)
	payload = {}
	if no_resync_snapshot:
		payload['noResyncSnapshot'] = True
	if target_name:
		payload['targetName'] = target_name
	if full_sync:
		payload['fullSync'] = True
	return payload


def preprocess_remote_copy_links(target_name, source_port, target_port_wwn_or_ip):
	"""Validate parameters for admitting remote copy links.
	Returns tuple (target_name, source_port, target_port_wwn_or_ip, storage_system_ip) after basic checks.
	"""
	if not target_name:
		raise InvalidParameterValue('target_name', 'Target name cannot be null')
	if not source_port:
		raise InvalidParameterValue('source_port', 'Source port cannot be null')
	if not target_port_wwn_or_ip:
		raise InvalidParameterValue('target_port_wwn_or_ip', 'Target port WWN/IP cannot be null')

def preprocess_admit_remote_copy_target(remote_copy_group_name, target_name, target_mode, local_remote_volume_pair_list):
	"""Validate parameters for admitting a remote copy target to an existing group.

	local_remote_volume_pair_list: list of dicts each with local_volume_name, remote_volume_name
	Returns dict with normalized volumePairs list for workflow payload.
	"""
	validate_remote_copy_group_params(remote_copy_group_name)
	if not target_name:
		raise InvalidParameterValue('target_name', 'Target name cannot be null')
	if not target_mode:
		raise InvalidParameterValue('target_mode', 'Target mode cannot be null')
	

def preprocess_dismiss_remote_copy_target(remote_copy_group_name, target_name):
	"""Validate parameters for dismissing a remote copy target from a group."""
	validate_remote_copy_group_params(remote_copy_group_name)
	if not target_name:
		raise InvalidParameterValue('target_name', 'Target name cannot be null')




