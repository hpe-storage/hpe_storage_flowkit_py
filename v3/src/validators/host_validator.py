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
log = Logger()

def validate_host_params(name):
	if not isinstance(name, str) or not name.strip():
		raise ValueError("Host name must be a non-empty string.")

def validate_host_optional_params(params):
	optional_params = [
		"addPath", "descriptors", "domain", "fcPaths", "isVvolHost",
		"iscsiPaths", "keyValuePairs", "nvmePaths",
		"persona", "port", "setName", "transportType"
	]
	log.info(f"Validating optional parameters: {params}")
	for param, value in params.items():
		#commented
		log.info(f"Validating parameter: {param}")
		if param not in optional_params:
			raise ValueError(f"Invalid optional parameter: {param}")
		#Additional validation can be added here as needed
		if param == "addPath":
			if not isinstance(value, bool):
				raise ValueError("'addPath' must be a boolean.")
		elif param == "descriptors":
			expected_keys = {"IPAddr", "comment", "contact", "location", "model", "os"}
			if not isinstance(param, dict) and set(param.keys()) != expected_keys and not all(isinstance(k, str) and v == "string" for k, v in param.items()):
				raise ValueError(f"'descriptors' must be a dictionary with the following string keys: {', '.join(expected_keys)} and all values must be 'string'.")
		elif param == "domain":
			if not isinstance(value, str):
				raise ValueError("'domain' must be a string.")
		elif param == "fcPaths":
			_validate_string_list("fcPaths", value)
		elif param == "isVvolHost":
			if not isinstance(value, bool):
				raise ValueError("'isVvolHost' must be a boolean.")
		elif param == "iscsiPaths":
			_validate_string_list("iscsiPaths", value)
		elif param == "keyValuePairs":
			if not isinstance(value, dict) and not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
				raise ValueError("'keyValuePairs' must be a dictionary of string-string.")
		elif param == "nvmePaths":
			_validate_string_list("nvmePaths", value)
		elif param == "persona":
			if not isinstance(value, int):
				raise ValueError("'persona' must be an integer.")
		elif param == "port":
			_validate_string_list("port", value)
			""" if not isinstance(value, list) and not all(isinstance(item, str) for item in value):
				raise ValueError("'port' must be a list of strings.") """
		elif param == "setName":
			if not isinstance(value, str):
				raise ValueError("'setName' must be a string.")
		elif param == "transportType":
			allowed_values = {"UNKNOWN", "FC", "TCP"}
			if not isinstance(value, str) and value not in allowed_values:
				raise ValueError("'transportType' can be UNKNOWN or FC or TCP.")
			
def _validate_string_list(field_name, value):
	if not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
		raise ValueError(f"'{field_name}' must be a list of strings.")
