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
"""Validator for schedule parameters"""

import re


def validate_schedule_params(name,params):
    """
    Validate schedule creation/modification parameters
    
    Args:
        params: Dictionary containing schedule parameters
        
    Raises:
        ValueError: If validation fails
    """
    
    # Required fields
    if not name:
        raise ValueError("Schedule name is required")
    
    if len(name) > 127:
        raise ValueError("Schedule name must be up to 127 characters in length")
    
    # Validate name format (tpd_obj_name pattern)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
        raise ValueError("Schedule name must contain only alphanumeric characters, hyphens, underscores, and periods")
    
    # At least one time field must be provided
    time_fields = ['month', 'minute', 'hour', 'dayofmonth', 'dayofweek']
    if not any(params.get(field) for field in time_fields):
        raise ValueError(f"At least one of {', '.join(time_fields)} must be provided")
    
    
    # Check that not all time fields are '*' or '-' 
    # At least one field must have a specific value
    # EXCEPTION: If interval is provided, all time fields can be '*' or '-'
    if 'interval' not in params:
        all_wildcard = True
        for field in time_fields:
            if field in params:
                value = str(params[field])
                if value not in ['*', '-']:
                    all_wildcard = False
                    break
        
        if all_wildcard:
            raise ValueError("At least one time field (month, minute, hour, dayofmonth, dayofweek) must have a specific value, not all can be '*' or '-' (unless interval is specified)")
    
    # Validate individual time fields
    if 'month' in params:
        _validate_month(params['month'])
    
    if 'minute' in params:
        _validate_minute(params['minute'])
    
    if 'hour' in params:
        _validate_hour(params['hour'])
    
    if 'dayofmonth' in params:
        _validate_dayofmonth(params['dayofmonth'])
    
    if 'dayofweek' in params:
        _validate_dayofweek(params['dayofweek'])
    
    if 'year' in params:
        _validate_year(params['year'])
    
    if 'interval' in params:
        _validate_interval(params['interval'])
        # When interval is used, minute field must be "*" or "-"
        if 'minute' in params:
            minute = params['minute']
            if minute not in ['*', '-']:
                raise ValueError("When using interval, the minute field must be '*' or '-'")
    
    # Either command or createsv must be specified
    if not params.get('command') and not params.get('createsv'):
        raise ValueError("Either 'command' or 'createsv' must be specified")
    
    if params.get('command') and params.get('createsv'):
        raise ValueError("Only one of 'command' or 'createsv' can be specified, not both")
    
    # Validate createsv parameters if present
    if params.get('createsv'):
        _validate_createsv_params(params['createsv'])
    
    # Validate boolean fields
    for bool_field in ['charSubstitution', 'noalert', 'norebalance', 'runonce', 'useNetworkNode']:
        if bool_field in params and not isinstance(params[bool_field], bool):
            raise ValueError(f"{bool_field} must be a boolean value")
    
    # norebalance is not allowed with interval option
    if params.get('norebalance') and params.get('interval'):
        raise ValueError("norebalance option is not allowed with schedules using the interval option")


def _validate_month(month):
    """Validate month field: * or 1-12"""
    month_str = str(month)
    if month_str == '*':
        return
    try:
        month_int = int(month_str)
        if month_int < 1 or month_int > 12:
            raise ValueError("Month must be * or 1-12")
    except (ValueError, TypeError):
        raise ValueError("Month must be * or 1-12")


def _validate_minute(minute):
    """Validate minute field: * or - or 0-59"""
    minute_str = str(minute)
    if minute_str in ['*', '-']:
        return
    try:
        minute_int = int(minute_str)
        if minute_int < 0 or minute_int > 59:
            raise ValueError("Minute must be *, -, or 0-59")
    except (ValueError, TypeError):
        raise ValueError("Minute must be *, -, or 0-59")


def _validate_hour(hour):
    """Validate hour field: * or 0-23"""
    hour_str = str(hour)
    if hour_str == '*':
        return
    try:
        hour_int = int(hour_str)
        if hour_int < 0 or hour_int > 23:
            raise ValueError("Hour must be * or 0-23")
    except (ValueError, TypeError):
        raise ValueError("Hour must be * or 0-23")


def _validate_dayofmonth(dayofmonth):
    """Validate dayofmonth field: * or 1-31"""
    day_str = str(dayofmonth)
    if day_str == '*':
        return
    try:
        day_int = int(day_str)
        if day_int < 1 or day_int > 31:
            raise ValueError("Day of month must be * or 1-31")
    except (ValueError, TypeError):
        raise ValueError("Day of month must be * or 1-31")


def _validate_dayofweek(dayofweek):
    """Validate dayofweek field: * or 0-6 (Sunday is 0)"""
    day_str = str(dayofweek)
    if day_str == '*':
        return
    try:
        day_int = int(day_str)
        if day_int < 0 or day_int > 6:
            raise ValueError("Day of week must be * or 0-6 (Sunday is 0)")
    except (ValueError, TypeError):
        raise ValueError("Day of week must be * or 0-6 (Sunday is 0)")


def _validate_year(year):
    """Validate year field: * or valid year value"""
    year_str = str(year)
    if year_str == '*':
        return
    try:
        year_int = int(year_str)
        if year_int < 1970 or year_int > 2100:
            raise ValueError("Year must be * or between 1970 and 2100")
    except (ValueError, TypeError):
        raise ValueError("Year must be * or a valid year value")


def _validate_interval(interval):
    """Validate interval field: 15-1440"""
    try:
        interval_int = int(interval)
        if interval_int < 15 or interval_int > 1440:
            raise ValueError("Interval must be 15-1440 minutes")
    except (ValueError, TypeError):
        raise ValueError("Interval must be 15-1440 minutes")


def _validate_createsv_params(createsv):
    """
    Validate createsv (snapshot creation) parameters
    
    Args:
        createsv: Dictionary containing createsv parameters
        
    Raises:
        ValueError: If validation fails
    """
    
    # Required fields
    if not createsv.get('vvOrVvset'):
        raise ValueError("createsv.vvOrVvset is required (parent volume name or volume set name)")
    
    vv_or_vvset = createsv['vvOrVvset']
    if len(vv_or_vvset) > 255:
        raise ValueError("createsv.vvOrVvset must be up to 255 characters")
    
    # Validate tpd_obj_name pattern
    if not re.match(r'^(set:|rcgroup:)?[a-zA-Z0-9_\-\.@]+$', vv_or_vvset):
        raise ValueError("createsv.vvOrVvset must be a valid object name")
    
    if not createsv.get('namePattern'):
        raise ValueError("createsv.namePattern is required")
    
    # Validate namePattern enum
    valid_name_patterns = ['PARENT_TIMESTAMP', 'PARENT_SEC_SINCE_EPOCH', 'CUSTOM']
    if createsv['namePattern'] not in valid_name_patterns:
        raise ValueError(f"createsv.namePattern must be one of {', '.join(valid_name_patterns)}")
    
    
    # Validate optional string fields
    if 'addToSet' in createsv:
        add_to_set = createsv['addToSet']
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', add_to_set):
            raise ValueError("createsv.addToSet must be a valid object name")
    
    if 'comment' in createsv:
        comment = createsv['comment']
        if len(comment) > 1024:  # Reasonable limit
            raise ValueError("createsv.comment is too long (max 1024 characters)")
    
    if 'customName' in createsv:
        custom_name = createsv['customName']
        if len(custom_name) > 255:
            raise ValueError("createsv.customName must be up to 255 characters")
    
    # Validate expireSecs range
    if 'expireSecs' in createsv:
        expire_secs = createsv['expireSecs']
        try:
            expire_int = int(expire_secs)
            if expire_int < 60 or expire_int > 157680000:
                raise ValueError("createsv.expireSecs must be in range [60-157680000]")
        except (ValueError, TypeError):
            raise ValueError("createsv.expireSecs must be a valid integer")
    
    # Validate retainSecs range
    if 'retainSecs' in createsv:
        retain_secs = createsv['retainSecs']
        try:
            retain_int = int(retain_secs)
            if retain_int < 60 or retain_int > 157680000:
                raise ValueError("createsv.retainSecs must be in range [60-157680000]")
        except (ValueError, TypeError):
            raise ValueError("createsv.retainSecs must be a valid integer")
    
    # Validate id range
    if 'id' in createsv:
        snap_id = createsv['id']
        try:
            id_int = int(snap_id)
            if id_int < 1 or id_int > 131071:
                raise ValueError("createsv.id must be in range [1-131071]")
        except (ValueError, TypeError):
            raise ValueError("createsv.id must be a valid integer")
    
    # Validate boolean fields
    for bool_field in ['rcopy', 'readOnly']:
        if bool_field in createsv and not isinstance(createsv[bool_field], bool):
            raise ValueError(f"createsv.{bool_field} must be a boolean value")
    
    # Validate keyValuePairs is a dict
    if 'keyValuePairs' in createsv:
        if not isinstance(createsv['keyValuePairs'], dict):
            raise ValueError("createsv.keyValuePairs must be a dictionary")


def validate_modify_schedule_params(name ,params):
    """
    Validate schedule modification parameters
    
    Args:
        params: Dictionary containing schedule modification parameters
        
    Raises:
        ValueError: If validation fails
    """
    
    # For modify, name is not required but if provided should be valid
    
    if len(name) > 127:
            raise ValueError("Schedule name must be up to 127 characters in length")
        
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
            raise ValueError("Schedule name must contain only alphanumeric characters, hyphens, underscores, and periods")
    
    # Validate time fields if provided
    if 'interval' in params:
        _validate_interval(params['interval'])
    if 'month' in params:
        _validate_month(params['month'])
    
    if 'minute' in params:
        _validate_minute(params['minute'])
    
    if 'hour' in params:
        _validate_hour(params['hour'])
    
    if 'dayofmonth' in params:
        _validate_dayofmonth(params['dayofmonth'])
    
    if 'dayofweek' in params:
        _validate_dayofweek(params['dayofweek'])
    
    if 'year' in params:
        _validate_year(params['year'])
    

def validate_suspend_resume_schedule_params(name, params=None):
    """
    Validate suspend schedule action parameters
    
    Args:
        name: Schedule name to suspend
        params: Optional dictionary containing suspend action parameters
        
    Raises:
        ValueError: If validation fails
    """
    
    # Validate schedule name
    if not name:
        raise ValueError("Schedule name is required")
    
    if len(name) > 127:
        raise ValueError("Schedule name must be up to 127 characters in length")
    
    # Validate name format (tpd_obj_name pattern)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
        raise ValueError("Schedule name must contain only alphanumeric characters, hyphens, underscores, and periods")
    
    # If no params provided, just validate name
    if params is None:
        return
    

    
    # Validate parameters object if present (contains schedule details)
    if 'parameters' in params:
        parameters = params['parameters']
        
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be a dictionary")
        
        # Validate time fields in parameters if provided (reuse existing validators)
        if 'month' in parameters:
            _validate_month(parameters['month'])
        
        if 'minute' in parameters:
            _validate_minute(parameters['minute'])
        
        if 'hour' in parameters:
            _validate_hour(parameters['hour'])
        
        if 'dayofmonth' in parameters:
            _validate_dayofmonth(parameters['dayofmonth'])
        
        if 'dayofweek' in parameters:
            _validate_dayofweek(parameters['dayofweek'])
        
        if 'interval' in parameters:
            _validate_interval(parameters['interval'])
        
        # Validate command if present
        if 'command' in parameters:
            if not isinstance(parameters['command'], str):
                raise ValueError("parameters.command must be a string")
    
    # Validate boolean fields at top level if present
    for bool_field in ['isalertenabled', 'ispaused', 'issystemtask']:
        if bool_field in params:
            if not isinstance(params[bool_field], bool):
                raise ValueError(f"{bool_field} must be a boolean value")
    
    # Validate status enum if present
    if 'status' in params:
        valid_statuses = ['SCHED_ACTIVE', 'SCHED_SUSPENDED', 'SCHED_UNKNOWN']
        if params['status'] not in valid_statuses:
            raise ValueError(f"status must be one of {', '.join(valid_statuses)}")


