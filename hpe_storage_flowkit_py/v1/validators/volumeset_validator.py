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
"""Validator functions for Volume Set operations.
"""

from hpe_storage_flowkit_py.v1.src.core import exceptions

NAME_MIN = 1
NAME_MAX = 27


def validate_volumeset_params(name: str, domain=None, setmembers=None):
    """Validate volume set parameters.

    Current rules:
      - name: required, length between NAME_MIN and NAME_MAX
      - domain: optional (placeholder for future domain-specific validation)
      - setmembers: if not None, MUST be a list (strict) and non-empty list allowed; empty list ignored

    Raises InvalidParameterValue on first rule violation.
    """
    # Name validation
    if name is None:
        raise exceptions.InvalidParameterValue(param='volumeset_name', message='Name cant be null')
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        raise exceptions.InvalidParameterValue(
            param='volumeset_name',
            message=f'Name length must be between {NAME_MIN} and {NAME_MAX} characters'
        )

    # setmembers strict type check (only when provided and not empty)
    if setmembers is not None:
        if not isinstance(setmembers, list):
            raise exceptions.InvalidParameterValue(param='setmembers', message='Setmembers must be a list')
    return True
