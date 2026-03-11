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

Rules:
    - `name` always required.
    - `appSetType` required only when operation == 'create'.
    - Supported optional kwargs: domain, comments, members, setmembers.
    - Unknown kwargs raise ValueError.
    - If both members & setmembers provided they are merged logically by caller.
"""


from hpe_storage_flowkit_py.v3.src.core.logger import Logger

logger = Logger()

NAME_MIN = 1
NAME_MAX = 27
OPTIONAL_PARAMS = {"domain", "comments", "setmembers", "newName"}


def validate_volumeset_params(name: str, appSetType: str = None, operation: str = None, **kwargs) -> bool:
    """Validate volume set parameters.

    Parameters:
      name: volume set name.
      appSetType: application set type (mandatory only for create).
      operation: context indicator ('create', 'delete', 'get', etc.). If 'create', appSetType enforced.
      kwargs: optional params (domain, comments, members).
    """
    logger.info("Started validating volume set parameters")
    # Validate required: name
    if name is None:
        logger.error("Volume set name parameter is null")
        raise ValueError("Volume set name cannot be null")
    if not isinstance(name, str) or not name.strip():
        logger.error(f"Volume set name is not a valid string: {name}")
        raise ValueError("Volume set name must be a non-empty string")
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        logger.error(f"Volume set name length ({len(name)}) is outside valid range {NAME_MIN}-{NAME_MAX}")
        raise ValueError(f"Volume set name length must be between {NAME_MIN} and {NAME_MAX} characters")

    # Validate appSetType only for create or if explicitly provided
    if operation == 'create':
        if appSetType is None:
            logger.error("appSetType is required for create operation but is null")
            raise ValueError("appSetType is required for create operation")
    if appSetType is not None:
        if not isinstance(appSetType, str) or not appSetType.strip():
            logger.error(f"appSetType must be a non-empty string, got: {appSetType}")
            raise ValueError("appSetType must be a non-empty string when provided")

    # Iterate kwargs for validation
    for key, value in kwargs.items():
        if key not in OPTIONAL_PARAMS:
            logger.error(f"Unsupported parameter '{key}' for volume set operation")
            raise ValueError(f"Unsupported parameter '{key}' for volume set operation")
        if key == "domain":
            if value is not None:
                if not isinstance(value, str):
                    logger.error(f"Domain parameter must be a string, got {type(value)}")
                    raise ValueError("Domain must be a string")
                if not value.strip():
                    logger.error("Domain parameter cannot be empty")
                    raise ValueError("Domain, if provided, cannot be empty")
        elif key == "comments":
            if value is not None and not isinstance(value, str):
                logger.error(f"Comments parameter must be a string, got {type(value)}")
                raise ValueError("Comments must be a string")
        elif key == "newName":
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    logger.error(f"newName must be a non-empty string, got: {value}")
                    raise ValueError("newName must be a non-empty string when provided")
        elif key == "setmembers":
            if value is not None:
                if not isinstance(value, list):
                    logger.error(f"{key} parameter must be a list, got {type(value)}")
                    raise ValueError(f"{key} must be a list")
                for m in value:
                    if not isinstance(m, str) or not m.strip():
                        logger.error(f"Invalid member in {key} list: {m}")
                        raise ValueError("Each member must be a non-empty string")
    
    logger.info("Completed validating volume set parameters")
    return True
