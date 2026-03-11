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
# utils helper file
# Add any utility functions or classes here that can be shared across modules
def convert_to_hours(time, unit):
	hours = 0
	if unit == 'Days':
		hours = time * 24
	elif unit == 'Hours':
		hours = time
	return hours


def mergeDict(dict1, dict2):
	"""
	Safely merge 2 dictionaries together
	"""
	if type(dict1) is not dict:
		raise Exception("dict1 is not a dictionary")
	if type(dict2) is not dict:
		raise Exception("dict2 is not a dictionary")

	dict3 = dict1.copy()
	dict3.update(dict2)

	return dict3
