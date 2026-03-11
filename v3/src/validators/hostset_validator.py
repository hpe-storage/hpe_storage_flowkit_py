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
"""Validator functions for Host Set operations.

Rules:
    - `name` always required.
    - Supported optional kwargs: domain, comment, setmembers.
    - Unknown kwargs raise ValueError.
"""

from hpe_storage_flowkit_py.v3.src.core.logger import Logger

logger = Logger()

NAME_MIN = 1
NAME_MAX = 27
OPTIONAL_PARAMS = {"domain", "comment", "setmembers"}


def validate_hostset_params(name: str, **kwargs) -> bool:
    """Validate host set parameters.

    Parameters:
      name: host set name (required).
      kwargs: optional params (domain, comment, setmembers).
    
    Raises:
      ValueError: When any parameter is invalid.
    
    Returns:
      bool: True if all validations pass.
    """
    logger.info("Started validating host set parameters")
    # Validate required: name
    if name is None:
        logger.error("Host set name parameter is null")
        raise ValueError('Host set name cannot be null.')
    if not isinstance(name, str) or not name.strip():
        logger.error(f"Host set name is not a valid string: {name}")
        raise ValueError('Host set name must be a non-empty string.')
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        logger.error(f"Host set name length ({len(name)}) is outside valid range {NAME_MIN}-{NAME_MAX}")
        raise ValueError(f'Host set name must be {NAME_MIN}-{NAME_MAX} characters in length.')

    # Iterate kwargs for validation
    for key, value in kwargs.items():
        if key not in OPTIONAL_PARAMS:
            logger.error(f"Unsupported parameter '{key}' for host set operation")
            raise ValueError(f"Unsupported parameter for host set operation: {key}")
        
        if key == "domain":
            if value is not None:
                if not isinstance(value, str):
                    logger.error(f"Domain parameter must be a string, got {type(value)}")
                    raise ValueError('Domain must be a string when provided.')
                if not value.strip():
                    logger.error("Domain parameter cannot be empty")
                    raise ValueError('Domain cannot be empty when provided.')
        
        elif key == "comment":
            if value is not None:
                if not isinstance(value, str):
                    logger.error(f"Comment parameter must be a string, got {type(value)}")
                    raise ValueError('Comment must be a string when provided.')
        
        elif key == "setmembers":
            if value is not None:
                if not isinstance(value, list):
                    logger.error(f"SetMembers parameter must be a list, got {type(value)}")
                    raise ValueError(f'setmembers must be a list of host names. Current provided type is {type(value)}.')
                for h in value:
                    if not isinstance(h, str) or not h.strip():
                        logger.error(f"Invalid member in setmembers list: {h}")
                        raise ValueError('Each set member must be a non-empty string.')
    
    logger.info("Completed validating host set parameters")
    return True
