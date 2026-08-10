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
"""Utility (preprocessing) helpers for volume set operations.

Responsible for assembling payload dicts AFTER validation is delegated to
`validators.volumeset_validator`. This keeps orchestration code thin.
"""

from hpe_storage_flowkit_py.v1.src.validators.volumeset_validator import validate_volumeset_params

def preprocess_create_volumeset(name, domain=None, setmembers=None):
    """Validate and build payload for create volume set.

    Returns dict suitable for passing directly to workflow create call.
    """
    validate_volumeset_params(name, domain=domain, setmembers=setmembers)
    payload = {}
    if domain:
        payload['domain'] = domain
    if setmembers:
        # At this point validator guaranteed it's a list
        payload['setmembers'] = setmembers
    return payload
