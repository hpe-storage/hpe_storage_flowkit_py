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


def validate_host_params(name, iscsiNames=None, FCWwns=None, host_domain=None, host_persona=None,
						 chap_name=None, chap_secret=None, chap_secret_hex=False, force_path_removal=None):
	"""Validate host-related parameters.

	This single validator centralizes checks used across host workflows.

	Parameters are optional and only validated when provided (except name which
	is required by many operations).

	Raises InvalidParameterValue for invalid inputs.
	"""
	# name
	if name is None or not isinstance(name, str):
		raise InvalidParameterValue('name', "Must be a non-empty string.")
	if len(name) < 1 or len(name) > 31:
		raise InvalidParameterValue('name', "Host name must be at least 1 character and not more than 31 characters.")

	# iscsiNames: list of strings
	if iscsiNames is not None:
		if not isinstance(iscsiNames, list):
			raise InvalidParameterValue('iscsiNames', "Must be a list of non-empty strings.")
		for iqn in iscsiNames:
			if not isinstance(iqn, str) or not iqn:
				raise InvalidParameterValue('iscsiNames', "Each iSCSI name must be a non-empty string.")

	# FCWwns: list of strings
	if FCWwns is not None:
		if not isinstance(FCWwns, list):
			raise InvalidParameterValue('FCWwns', "Must be a list of non-empty strings.")
		for wwn in FCWwns:
			if not isinstance(wwn, str) or not wwn:
				raise InvalidParameterValue('FCWwns', "Each FC WWN must be a non-empty string.")

	

	# host_domain: None or str
	if host_domain is not None and not isinstance(host_domain, str):
		raise InvalidParameterValue('host_domain', "Must be a string or None.")

	# host_persona: None or str
	if host_persona is not None and not isinstance(host_persona, str):
		raise InvalidParameterValue('host_persona', "Must be a string or None.")

	# CHAP validations
	if chap_name is not None:
		if not isinstance(chap_name, str) or not chap_name:
			raise InvalidParameterValue('chap_name', "Chap name must be a non-empty string.")
		# chap_secret is required when chap_name is provided
		if chap_secret is None:
			raise InvalidParameterValue('chap_secret', "Chap secret is required when chap_name is provided.")
		if chap_secret_hex:
			if not isinstance(chap_secret, str) or len(chap_secret) != 32:
				raise InvalidParameterValue('chap_secret', "Attribute chap_secret must be 32 hexadecimal characters if chap_secret_hex is true")
		else:
			if not isinstance(chap_secret, str) or len(chap_secret) < 12 or len(chap_secret) > 16:
				raise InvalidParameterValue('chap_secret', "Attribute chap_secret must be 12 to 16 characters if chap_secret_hex is false")

	# force_path_removal must be boolean when provided
	if force_path_removal is not None and not isinstance(force_path_removal, bool):
		raise InvalidParameterValue('force_path_removal', "Must be a boolean when provided.")

	return True
