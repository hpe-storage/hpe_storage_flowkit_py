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
"""NTP Configuration Validator.

This module provides validation functions for NTP and datetime configuration parameters.
"""

from hpe_storage_flowkit_py.v3.src.core import exceptions


def validate_ntp_addresses(ntp_addresses):
    """Validate NTP server addresses.
    
    Args:
        ntp_addresses (list or str): NTP server addresses to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not ntp_addresses:
        return
        
    if not isinstance(ntp_addresses, (list, str)):
        raise exceptions.InvalidInput("ntp_addresses must be a string or list of strings")
    
    if isinstance(ntp_addresses, str):
        if not ntp_addresses.strip():
            raise exceptions.InvalidInput("NTP address cannot be empty")
    elif isinstance(ntp_addresses, list):
        for addr in ntp_addresses:
            if not isinstance(addr, str) or not addr.strip():
                raise exceptions.InvalidInput("All NTP addresses must be non-empty strings")


def validate_datetime_format(date_time):
    """Validate datetime format (MM/dd/yyyy HH:mm:ss).
    
    Args:
        date_time (str): DateTime string to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not date_time:
        return
        
    if not isinstance(date_time, str):
        raise exceptions.InvalidInput("date_time must be a string")
    
    # Validate MM/dd/yyyy HH:mm:ss format
    import re
    pattern = r'^(0[1-9]|1[0-2])/(0[1-9]|[12][0-9]|3[01])/\d{4} ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
    if not re.match(pattern, date_time):
        raise exceptions.InvalidInput("date_time must be in format 'MM/dd/yyyy HH:mm:ss'")


def validate_timezone(timezone):
    """Validate timezone format.
    
    Args:
        timezone (str): Timezone string to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not timezone:
        return
        
    if not isinstance(timezone, str):
        raise exceptions.InvalidInput("timezone must be a string")
    
    if not timezone.strip():
        raise exceptions.InvalidInput("timezone cannot be empty")


def validate_ntp_params(date_time=None, ntp_addresses=None, timezone=None):
    """Validate all NTP configuration parameters.
    
    Args:
        date_time (str, optional): DateTime string in MM/dd/yyyy HH:mm:ss format
        ntp_addresses (list or str, optional): NTP server addresses
        timezone (str, required): Timezone string
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    # Timezone is required
    if not timezone:
        raise exceptions.InvalidInput("timezone is required")
    
    # Either date_time OR ntp_addresses must be provided, but not both
    if date_time and ntp_addresses:
        raise exceptions.InvalidInput(
            "Cannot specify both date_time and ntp_addresses. Provide either one or the other."
        )
    
    if not date_time and not ntp_addresses:
        raise exceptions.InvalidInput(
            "Must specify either date_time or ntp_addresses (but not both)."
        )
    
    validate_datetime_format(date_time)
    validate_ntp_addresses(ntp_addresses)
    validate_timezone(timezone)
