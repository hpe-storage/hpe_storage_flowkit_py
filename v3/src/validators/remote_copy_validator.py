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
"""Validator functions for Remote Copy Group operations."""

from hpe_storage_flowkit_py.v3.src.core.logger import Logger

logger = Logger()

VALID_PROXIMITY_VALUES = {"primary", "secondary", "all"}


def validate_admit_rcopy_host_params(rcg_name, proximity,
                                     host_names=None, hostset_names=None):
    """Validate parameters for admitting hosts to a remote copy group.

    Parameters:
      rcg_name: remote copy group name (required).
      proximity: proximity setting (required). Must be 'primary', 'secondary', or 'all'.
      host_names: optional list of host name strings.
      hostset_names: optional list of host set name strings.

    Raises:
      ValueError: When any parameter is invalid.

    Returns:
      bool: True if all validations pass.
    """
    logger.info("Started validating admit rcopy host parameters")

    if rcg_name is None:
        logger.error("Remote copy group name is null")
        raise ValueError('Remote copy group name cannot be null.')
    if not isinstance(rcg_name, str) or rcg_name.strip() == "":
        logger.error(f"Remote copy group name is not a valid string: {rcg_name}")
        raise ValueError(f"Remote copy group name must be a non-empty string, got '{rcg_name}'.")

    if proximity is None:
        logger.error("Proximity parameter is null")
        raise ValueError('Proximity cannot be null.')
    if not isinstance(proximity, str) or proximity.lower() not in VALID_PROXIMITY_VALUES:
        logger.error(f"Invalid proximity value: {proximity}")
        raise ValueError(
            f"Proximity must be one of {VALID_PROXIMITY_VALUES}, got '{proximity}'.")

    if host_names is not None:
        if not isinstance(host_names, list):
            logger.error(f"host_names is not a list: {type(host_names)}")
            raise ValueError('host_names must be a list of strings.')
        for name in host_names:
            if not isinstance(name, str) or name.strip() == "":
                logger.error(f"Invalid host name in host_names: {name}")
                raise ValueError(f"Each host name must be a non-empty string, got '{name}'.")

    if hostset_names is not None:
        if not isinstance(hostset_names, list):
            logger.error(f"hostset_names is not a list: {type(hostset_names)}")
            raise ValueError('hostset_names must be a list of strings.')
        for name in hostset_names:
            if not isinstance(name, str) or not name.strip():
                logger.error(f"Invalid hostset name in hostset_names: {name}")
                raise ValueError(f"Each hostset name must be a non-empty string, got '{name}'.")

    if not host_names and not hostset_names:
        logger.error("Neither host_names nor hostset_names provided")
        raise ValueError('At least one of host_names or hostset_names must be provided.')

    if host_names and hostset_names:
        logger.error("Both host_names and hostset_names provided")
        raise ValueError('Cannot mix host_names and hostset_names in the same command. '
                         'Provide only one of them.')

    logger.info("Admit rcopy host parameter validation passed")
    return True
