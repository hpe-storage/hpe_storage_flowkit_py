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
# Host Set action enumerations
# Mirrors WSAPI host set modify action codes.

from hpe_storage_flowkit_py.v1.src.validators.hostset_validator import validate_hostset_params

HOSTSET_ACTION_ADD = 1
HOSTSET_ACTION_REMOVE = 2

__all__ = [
    'HOSTSET_ACTION_ADD',
    'HOSTSET_ACTION_REMOVE'
]

def preprocess_create_hostset(name, domain=None, setmembers=None):
    """Validate and build payload for create host set.

    Returns dict suitable for passing directly to workflow create call.
    """
    validate_hostset_params(name, domain=domain, setmembers=setmembers)

    payload_params = {}
    if domain:
        payload_params['domain'] = domain
    if setmembers:
        payload_params['setmembers'] = setmembers
    return payload_params