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
import re

from hpe_storage_flowkit_py.v3.src.core.logger import Logger
log = Logger()

def validate_vlun_params(volname, hostname):
	if not isinstance(volname, str) or not volname.strip() or not isinstance(hostname, str)or not hostname.strip():
		raise ValueError("Volume and/or Host name must be a non-empty string.")


def validate_vlun_optional_params(params):
	optional_params = [
		"autoLun", "lun", "maxAutoLun", "noVcn", "overrideLowerPriority",
		"portPos"
	]
	log.info(f"Validating optional parameters: {params}")
	for param, value in params.items():
		#commented
		log.info(f"Validating parameter: {param}")
		if param not in optional_params:
			raise ValueError(f"Invalid optional parameter: {param}")
		#Additional validation can be added here as needed
		if param == "autoLun":
			if not isinstance(value, bool):
				raise ValueError("'autoLun' must be a boolean.")
		elif param == "lun":
			if not isinstance(value, int):
				raise ValueError("'lun' must be an integer.")
		elif param == 'maxAutoLun':
			if not isinstance(value, int):
				raise ValueError("'maxAutoLun' must be an integer.")
		elif param == "noVcn":
			if not isinstance(value, bool):
				raise ValueError("'noVcn' must be a boolean.")
		elif param == "overrideLowerPriority":
			if not isinstance(value, bool):
				raise ValueError("'overrideLowerPriority' must be a boolean.")
		elif param == "portPos":
			if not isinstance(value, str):
				raise ValueError("'portPos' must be a string.")
			# Validate format N:S:P where N, S, P are integers
			if not re.match(r'^\d+:\d+:\d+$', value):
				raise ValueError("'portPos' must be in the format 'N:S:P' with numeric values.")

