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

def validate_cpg_params(name, params=None):
	if not name or not isinstance(name, str):
		raise ValueError("CPG name must be a non-empty string.")
	if params is not None and not isinstance(params, dict):
		raise ValueError("CPG params must be a dictionary if provided.")
	if len(name) < 1 or len(name) > 31:
		raise ValueError("CPG create failed. CPG name must be atleast 1 character and not more than 31 characters")