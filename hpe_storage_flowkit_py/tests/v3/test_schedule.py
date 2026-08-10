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
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hpe_storage_flowkit_py.v3.src.workflows.schedule import ScheduleWorkflow
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, ScheduleDoesNotExist
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, ScheduleAlreadyExists
from hpe_storage_flowkit_py.v3.src.validators.schedule_validator import validate_modify_schedule_params, validate_schedule_params, validate_suspend_resume_schedule_params
from hpe_storage_flowkit_py.v3.src.workflows.schedule import ScheduleWorkflow, _convert_to_seconds


class MockSessionManager:
    """Mock session manager for testing"""
    def __init__(self):
        self.rest_client = MockRestClient()


class MockTaskManager:
    """Mock task manager for testing"""
    def __init__(self, session_mgr=None):
        self.session_mgr = session_mgr
    
    def wait_for_task_to_end(self, task_uri, poll_rate_secs=15):
        """Mock wait for task completion"""
        return {'status': 'completed', 'taskUri': task_uri}


class MockRestClient:
    """Mock REST client for testing"""
    def __init__(self):
        self.responses = {}
        self.posted_data = []
        self.deleted_endpoints = []
        self.patched_data = []
        self.existing_schedules = []  # Track created schedules
        
    def post(self, endpoint, payload):
        self.posted_data.append({'endpoint': endpoint, 'payload': payload})
        
        # Track schedule creation
        if endpoint == '/schedules':
            schedule_name = payload.get('name')
            if schedule_name:
                self.existing_schedules.append({
                    'uid': f'schedule-{schedule_name}-uid',
                    'name': schedule_name
                })
        
        return {'status': 'created', 'name': payload.get('name'), 'payload': payload}
    
    def delete(self, endpoint):
        self.deleted_endpoints.append(endpoint)
        
        # Remove schedule from tracking if deleted
        if '/schedules/' in endpoint:
            schedule_uid = endpoint.split('/')[-1]
            self.existing_schedules = [s for s in self.existing_schedules if s['uid'] != schedule_uid]
        
        return {'status': 'deleted', 'endpoint': endpoint}
    
    def patch(self, endpoint, payload):
        self.patched_data.append({'endpoint': endpoint, 'payload': payload})
        return {'status': 'modified', 'payload': payload}
    
    def get(self, endpoint, headers=None):
        if '/schedules?name=' in endpoint:
            name = endpoint.split('=')[1]
            # Only return schedule if it exists in our tracking
            matching = [s for s in self.existing_schedules if s['name'] == name]
            return matching
        elif endpoint == '/schedules':
            return {'members': self.existing_schedules}
        return {}


class TestScheduleWorkflow(unittest.TestCase):
    """Comprehensive unit tests for Schedule workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = ScheduleWorkflow(self.session_mgr, self.task_mgr)
    
    def test_create_schedule_basic(self):
        """Test creating schedule with createsv"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP'
        }
        result = self.workflow.create_schedule('test_schedule', hour='12', minute='0', createsv=createsv_params)
        self.assertEqual(result['status'], 'created')
        self.assertEqual(result['name'], 'test_schedule')
    
    def test_create_schedule_with_time_parameters(self):
        """Test creating schedule with time parameters"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP'
        }
        result = self.workflow.create_schedule(
            'test_schedule',
            hour='12',
            minute='30',
            dayofmonth='15',
            month='6',
            year='2025',
            dayofweek='1',
            createsv=createsv_params
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['hour'], '12')
        self.assertEqual(payload['minute'], '30')
        self.assertEqual(payload['dayofmonth'], '15')
        self.assertEqual(payload['month'], '6')
        self.assertEqual(payload['year'], '2025')
        self.assertEqual(payload['dayofweek'], '1')
    
    def test_create_schedule_with_interval(self):
        """Test creating schedule with interval"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP'
        }
        result = self.workflow.create_schedule(
            'test_schedule',
            interval='60',
            minute='*',
            createsv=createsv_params
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('interval', posted['payload'])
        self.assertEqual(posted['payload']['interval'], '60')
    
    def test_create_schedule_with_runonce(self):
        """Test creating schedule with runonce flag"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP'
        }
        result = self.workflow.create_schedule(
            'test_schedule',
            hour='10',
            minute='0',
            runonce=True,
            createsv=createsv_params
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('runonce', posted['payload'])
        self.assertTrue(posted['payload']['runonce'])
    
    def test_create_schedule_with_command(self):
        """Test creating schedule with command instead of createsv"""
        result = self.workflow.create_schedule(
            'test_schedule',
            hour='10',
            minute='0',
            command='createsvcopies -ro test_volume snapshot_$DATE'
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('command', posted['payload'])
        self.assertNotIn('createsv', posted['payload'])
    
    def test_create_schedule_with_time_units(self):
        """Test creating schedule with time unit conversions"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP',
            'expiration_time': 2,
            'expiration_unit': 'hours',
            'retention_time': 7,
            'retention_unit': 'days'
        }
        result = self.workflow.create_schedule(
            'test_schedule',
            hour='2',
            minute='0',
            createsv=createsv_params
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        # Verify time conversions occurred
        self.assertIn('createsv', payload)
        self.assertEqual(payload['createsv']['expireSecs'], 7200)  # 2 hours = 7200 seconds
        self.assertEqual(payload['createsv']['retainSecs'], 604800)  # 7 days = 604800 seconds
    
    def test_create_schedule_with_expiration_only(self):
        """Test creating schedule with only expiration time"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP',
            'expiration_time': 48,
            'expiration_unit': 'hours'
        }
        result = self.workflow.create_schedule(
            'test_schedule',
            hour='2',
            minute='0',
            createsv=createsv_params
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        # Verify only expiration was converted
        self.assertIn('createsv', payload)
        self.assertEqual(payload['createsv']['expireSecs'], 172800)  # 48 hours
        self.assertNotIn('retainSecs', payload['createsv'])
    
    def test_create_schedule_with_retention_only(self):
        """Test creating schedule with only retention time"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP',
            'retention_time': 14,
            'retention_unit': 'days'
        }
        result = self.workflow.create_schedule(
            'test_schedule',
            hour='2',
            minute='0',
            createsv=createsv_params
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        # Verify only retention was converted
        self.assertIn('createsv', payload)
        self.assertEqual(payload['createsv']['retainSecs'], 1209600)  # 14 days
        self.assertNotIn('expireSecs', payload['createsv'])
    
    def test_create_schedule_with_createsv_none(self):
        """Test creating schedule with None createsv"""
        result = self.workflow.create_schedule(
            'test_schedule',
            hour='10',
            minute='0',
            command='test_command'
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertNotIn('createsv', posted['payload'])
        self.assertIn('command', posted['payload'])
    
    def test_modify_schedule(self):
        """Test modifying schedule"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-test_schedule-uid', 'name': 'test_schedule'})
        
        result = self.workflow.modify_schedule(
            'test_schedule',
            hour='15',
            minute='00'
        )
        
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        
        self.assertEqual(payload['hour'], '15')
        self.assertEqual(payload['minute'], '00')
    
    def test_delete_schedule(self):
        """Test deleting schedule"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-test_schedule-uid', 'name': 'test_schedule'})
        
        result = self.workflow.delete_schedule('test_schedule')
        
        self.assertEqual(result['status'], 'deleted')
        self.assertIn('schedule-test_schedule-uid', self.session_mgr.rest_client.deleted_endpoints[0])
    
    def test_suspend_schedule(self):
        """Test suspending schedule"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-test_schedule-uid', 'name': 'test_schedule'})
        
        result = self.workflow.suspend_schedule('test_schedule')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('/schedules/schedule-test_schedule-uid', posted['endpoint'])
    
    def test_resume_schedule(self):
        """Test resuming schedule"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-test_schedule-uid', 'name': 'test_schedule'})
        
        result = self.workflow.resume_schedule('test_schedule')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('/schedules/schedule-test_schedule-uid', posted['endpoint'])
    
    def test_get_schedule_info(self):
        """Test getting schedule info"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-test_schedule-uid', 'name': 'test_schedule'})
        
        result = self.workflow.get_schedule_info('test_schedule')
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['uid'], 'schedule-test_schedule-uid')
        self.assertEqual(result[0]['name'], 'test_schedule')


class TestScheduleValidator(unittest.TestCase):
    """Comprehensive tests for schedule parameter validation"""
    
    def test_validate_schedule_name_valid(self):
        """Test validating schedule with valid name"""
        params = {'minute': '0', 'hour': '12', 'command': 'test_command'}
        validate_schedule_params('valid_schedule', params)  # Should not raise
    
    def test_validate_schedule_name_empty(self):
        """Test validating schedule with empty name"""
        params = {'minute': '0', 'hour': '12', 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('', params)
        self.assertIn('name is required', str(context.exception))
    
    def test_validate_schedule_name_too_long(self):
        """Test validating schedule with name > 127 characters"""
        params = {'minute': '0', 'hour': '12', 'command': 'test_command'}
        long_name = 'a' * 128
        with self.assertRaises(ValueError) as context:
            validate_schedule_params(long_name, params)
        self.assertIn('127 characters', str(context.exception))
    
    def test_validate_schedule_name_invalid_chars(self):
        """Test validating schedule with invalid characters in name"""
        params = {'minute': '0', 'hour': '12', 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('invalid@schedule!', params)
        self.assertIn('alphanumeric', str(context.exception))
    
    def test_validate_schedule_no_time_fields(self):
        """Test validating schedule without any time fields"""
        params = {'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('At least one of', str(context.exception))
    
    def test_validate_schedule_all_wildcard_no_interval(self):
        """Test validating schedule with all wildcards and no interval"""
        params = {'minute': '*', 'hour': '*', 'dayofmonth': '*', 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('specific value', str(context.exception))
    
    def test_validate_schedule_month_valid(self):
        """Test validating month with valid value"""
        params = {'minute': '0', 'hour': '12', 'month': 6, 'command': 'test_command'}
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_schedule_month_invalid(self):
        """Test validating month with invalid value"""
        params = {'minute': '0', 'hour': '12', 'month': 13, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Month must be', str(context.exception))
    
    def test_validate_schedule_minute_valid(self):
        """Test validating minute with valid values"""
        params = {'minute': 30, 'hour': '12', 'command': 'test_command'}
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_schedule_minute_invalid(self):
        """Test validating minute with invalid value"""
        params = {'minute': 60, 'hour': '12', 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Minute must be', str(context.exception))
    
    def test_validate_schedule_hour_valid(self):
        """Test validating hour with valid value"""
        params = {'minute': '0', 'hour': 23, 'command': 'test_command'}
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_schedule_hour_invalid(self):
        """Test validating hour with invalid value"""
        params = {'minute': '0', 'hour': 24, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Hour must be', str(context.exception))
    
    def test_validate_schedule_dayofmonth_valid(self):
        """Test validating dayofmonth with valid value"""
        params = {'minute': '0', 'hour': '12', 'dayofmonth': 31, 'command': 'test_command'}
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_schedule_dayofmonth_invalid(self):
        """Test validating dayofmonth with invalid value"""
        params = {'minute': '0', 'hour': '12', 'dayofmonth': 32, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Day of month must be', str(context.exception))
    
    def test_validate_schedule_dayofweek_valid(self):
        """Test validating dayofweek with valid value"""
        params = {'minute': '0', 'hour': '12', 'dayofweek': 5, 'command': 'test_command'}
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_schedule_dayofweek_invalid(self):
        """Test validating dayofweek with invalid value"""
        params = {'minute': '0', 'hour': '12', 'dayofweek': 7, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Day of week must be', str(context.exception))
    
    def test_validate_schedule_year_valid(self):
        """Test validating year with valid value"""
        params = {'minute': '0', 'hour': '12', 'year': 2025, 'command': 'test_command'}
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_schedule_year_invalid_low(self):
        """Test validating year with too low value"""
        params = {'minute': '0', 'hour': '12', 'year': 1969, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Year must be', str(context.exception))
    
    def test_validate_schedule_year_invalid_high(self):
        """Test validating year with too high value"""
        params = {'minute': '0', 'hour': '12', 'year': 2101, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Year must be', str(context.exception))
    
    def test_validate_schedule_interval_valid(self):
        """Test validating interval with valid value"""
        params = {'minute': '*', 'hour': '*', 'interval': 60, 'command': 'test_command'}
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_schedule_interval_too_low(self):
        """Test validating interval with too low value"""
        params = {'minute': '*', 'hour': '*', 'interval': 10, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Interval must be 15-1440', str(context.exception))
    
    def test_validate_schedule_interval_too_high(self):
        """Test validating interval with too high value"""
        params = {'minute': '*', 'hour': '*', 'interval': 1500, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Interval must be 15-1440', str(context.exception))
    
    def test_validate_schedule_interval_with_non_wildcard_minute(self):
        """Test validating interval with non-wildcard minute"""
        params = {'minute': '30', 'hour': '*', 'interval': 60, 'command': 'test_command'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('minute field must be', str(context.exception))
    
    def test_validate_schedule_no_command_or_createsv(self):
        """Test validating schedule without command or createsv"""
        params = {'minute': '0', 'hour': '12'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('command', str(context.exception))
    
    def test_validate_schedule_both_command_and_createsv(self):
        """Test validating schedule with both command and createsv"""
        params = {
            'minute': '0',
            'hour': '12',
            'command': 'test_command',
            'createsv': {'vvOrVvset': 'test', 'namePattern': 'PARENT_TIMESTAMP'}
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Only one of', str(context.exception))
    
    def test_validate_createsv_missing_vvOrVvset(self):
        """Test validating createsv without vvOrVvset"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {'namePattern': 'PARENT_TIMESTAMP'}
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('vvOrVvset is required', str(context.exception))
    
    def test_validate_createsv_missing_namePattern(self):
        """Test validating createsv without namePattern"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {'vvOrVvset': 'test_volume'}
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('namePattern is required', str(context.exception))
    
    def test_validate_createsv_invalid_namePattern(self):
        """Test validating createsv with invalid namePattern"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_volume',
                'namePattern': 'INVALID_PATTERN'
            }
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('namePattern must be one of', str(context.exception))
    
    def test_validate_createsv_expireSecs_valid(self):
        """Test validating createsv with valid expireSecs"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_volume',
                'namePattern': 'PARENT_TIMESTAMP',
                'expireSecs': 3600
            }
        }
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_createsv_retainSecs_valid(self):
        """Test validating createsv with valid retainSecs"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_volume',
                'namePattern': 'PARENT_TIMESTAMP',
                'retainSecs': 7200
            }
        }
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_createsv_id_valid(self):
        """Test validating createsv with valid id"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_volume',
                'namePattern': 'PARENT_TIMESTAMP',
                'id': 100
            }
        }
        validate_schedule_params('test_schedule', params)  # Should not raise
    
    def test_validate_norebalance_with_interval(self):
        """Test validating norebalance with interval option"""
        params = {
            'minute': '*',
            'hour': '*',
            'interval': 60,
            'norebalance': True,
            'command': 'test_command'
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('norebalance option is not allowed with', str(context.exception))
    
    def test_validate_boolean_field_char_substitution_invalid(self):
        """Test validating charSubstitution with non-boolean value"""
        params = {'minute': '0', 'hour': '12', 'command': 'test', 'charSubstitution': 'yes'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('charSubstitution must be a boolean', str(context.exception))
    
    def test_validate_boolean_field_noalert_invalid(self):
        """Test validating noalert with non-boolean value"""
        params = {'minute': '0', 'hour': '12', 'command': 'test', 'noalert': 'no'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('noalert must be a boolean', str(context.exception))
    
    def test_validate_boolean_field_runonce_invalid(self):
        """Test validating runonce with non-boolean value"""
        params = {'minute': '0', 'hour': '12', 'command': 'test', 'runonce': 1}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('runonce must be a boolean', str(context.exception))
    
    def test_validate_month_invalid_type(self):
        """Test validating month with invalid type"""
        params = {'minute': '0', 'hour': '12', 'month': 'invalid', 'command': 'test'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Month must be', str(context.exception))
    
    def test_validate_minute_invalid_type(self):
        """Test validating minute with invalid type"""
        params = {'minute': 'abc', 'hour': '12', 'command': 'test'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Minute must be', str(context.exception))
    
    def test_validate_hour_invalid_type(self):
        """Test validating hour with invalid type"""
        params = {'minute': '0', 'hour': 'abc', 'command': 'test'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Hour must be', str(context.exception))
    
    def test_validate_dayofmonth_invalid_type(self):
        """Test validating dayofmonth with invalid type"""
        params = {'minute': '0', 'hour': '12', 'dayofmonth': 'xyz', 'command': 'test'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Day of month must be', str(context.exception))
    
    def test_validate_dayofweek_invalid_type(self):
        """Test validating dayofweek with invalid type"""
        params = {'minute': '0', 'hour': '12', 'dayofweek': 'monday', 'command': 'test'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Day of week must be', str(context.exception))
    
    def test_validate_year_invalid_type(self):
        """Test validating year with invalid type"""
        params = {'minute': '0', 'hour': '12', 'year': 'abc', 'command': 'test'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Year must be', str(context.exception))
    
    def test_validate_interval_invalid_type(self):
        """Test validating interval with invalid type"""
        params = {'minute': '*', 'hour': '*', 'interval': 'every_hour', 'command': 'test'}
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('Interval must be 15-1440', str(context.exception))
    
    def test_validate_createsv_vvOrVvset_too_long(self):
        """Test validating createsv with vvOrVvset too long"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'a' * 256,
                'namePattern': 'CUSTOM'
            }
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('vvOrVvset must be up to 255 characters', str(context.exception))
    
    def test_validate_createsv_vvOrVvset_invalid_pattern(self):
        """Test validating createsv with invalid vvOrVvset pattern"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'invalid name!',
                'namePattern': 'CUSTOM'
            }
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('vvOrVvset must be a valid object name', str(context.exception))
    
    def test_validate_createsv_addToSet_invalid_pattern(self):
        """Test validating createsv with invalid addToSet pattern"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_vol',
                'namePattern': 'CUSTOM',
                'addToSet': 'invalid set!'
            }
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('addToSet must be a valid object name', str(context.exception))
    
    def test_validate_createsv_comment_too_long(self):
        """Test validating createsv with comment too long"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_vol',
                'namePattern': 'CUSTOM',
                'comment': 'a' * 10025
            }
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('comment is too long', str(context.exception))
    
    def test_validate_createsv_customName_too_long(self):
        """Test validating createsv with customName too long"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_vol',
                'namePattern': 'CUSTOM',
                'customName': 'a' * 256
            }
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('customName must be up to 255 characters', str(context.exception))
    
    def test_validate_createsv_expireSecs_invalid_type(self):
        """Test validating createsv with expireSecs invalid type"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_vol',
                'namePattern': 'CUSTOM',
                'expireSecs': 'invalid'
            }
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('expireSecs must be a valid integer', str(context.exception))
    
    def test_validate_createsv_retainSecs_invalid_type(self):
        """Test validating createsv with retainSecs invalid type"""
        params = {
            'minute': '0',
            'hour': '12',
            'createsv': {
                'vvOrVvset': 'test_vol',
                'namePattern': 'CUSTOM',
                'retainSecs': 'forever'
            }
        }
        with self.assertRaises(ValueError) as context:
            validate_schedule_params('test_schedule', params)
        self.assertIn('retainSecs must be a valid integer', str(context.exception))
    
    def test_validate_modify_schedule_with_interval(self):
        """Test validating modify schedule with interval parameter"""
        params = {'interval': 60}
        validate_modify_schedule_params('test_sched', params)  # Should not raise
    
    def test_validate_modify_schedule_with_time_fields(self):
        """Test validating modify schedule with various time fields"""
        params = {
            'month': '6',
            'minute': '30',
            'hour': '14',
            'dayofmonth': '15',
            'dayofweek': '3',
            'year': '2027'
        }
        validate_modify_schedule_params('test_sched', params)  # Should not raise
    
    def test_validate_suspend_resume_with_parameters(self):
        """Test validating suspend/resume with parameters dict"""
        params = {
            'parameters': {
                'month': '6',
                'minute': '30',
                'hour': '14',
                'command': 'test command'
            }
        }
        validate_suspend_resume_schedule_params('test_sched', params)  # Should not raise
    
    def test_validate_suspend_resume_with_boolean_fields(self):
        """Test validating suspend/resume with boolean fields"""
        params = {
            'isalertenabled': True,
            'ispaused': False,
            'issystemtask': True
        }
        validate_suspend_resume_schedule_params('test_sched', params)  # Should not raise
    
    def test_validate_suspend_resume_with_status(self):
        """Test validating suspend/resume with status field"""
        params = {'status': 'SCHED_SUSPENDED'}
        validate_suspend_resume_schedule_params('test_sched', params)  # Should not raise
    
    def test_validate_suspend_resume_status_invalid(self):
        """Test validating suspend/resume with invalid status"""
        params = {'status': 'INVALID_STATUS'}
        with self.assertRaises(ValueError) as context:
            validate_suspend_resume_schedule_params('test_sched', params)
        self.assertIn('status must be one of', str(context.exception))


class TestScheduleWorkflowErrorHandling(unittest.TestCase):
    """Test error handling in schedule workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = ScheduleWorkflow(self.session_mgr, self.task_mgr)
    
    def test_create_schedule_with_exception(self):
        """Test create_schedule handles exceptions"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP'
        }
        # Make API call fail
        self.session_mgr.rest_client.post = Mock(side_effect=Exception("API Error"))
        
        with self.assertRaises(Exception) as context:
            self.workflow.create_schedule('test_schedule', hour='12', minute='0', createsv=createsv_params)
        self.assertIn("API Error", str(context.exception))
    
    def test_modify_schedule_not_found(self):
        """Test modify_schedule when schedule doesn't exist"""
        # Make get return empty list
        self.session_mgr.rest_client.get = Mock(return_value=[])
        
        with self.assertRaises(ScheduleDoesNotExist):
            self.workflow.modify_schedule('nonexistent', hour='12')
    
    def test_modify_schedule_multiple_found(self):
        """Test modify_schedule when multiple schedules found"""
        # Make get return multiple schedules
        self.session_mgr.rest_client.get = Mock(return_value=[
            {'uid': 'schedule-1-uid', 'name': 'schedule1'},
            {'uid': 'schedule-2-uid', 'name': 'schedule2'}
        ])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.modify_schedule('test_schedule', hour='12')
        self.assertIn('Multiple schedules found', str(context.exception))
    
    def test_modify_schedule_no_uid(self):
        """Test modify_schedule when UID is missing"""
        # Return response without UID
        self.session_mgr.rest_client.get = Mock(return_value=[{'name': 'test'}])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.modify_schedule('test', hour='12')
        self.assertIn('UID missing', str(context.exception))
    
    def test_delete_schedule_not_found(self):
        """Test delete_schedule when schedule doesn't exist"""
        # Make get return empty list
        self.session_mgr.rest_client.get = Mock(return_value=[])
        
        with self.assertRaises(ScheduleDoesNotExist):
            self.workflow.delete_schedule('nonexistent')
    
    def test_delete_schedule_multiple_found(self):
        """Test delete_schedule when multiple schedules found"""
        # Make get return multiple schedules
        self.session_mgr.rest_client.get = Mock(return_value=[
            {'uid': 'schedule-1-uid', 'name': 'schedule1'},
            {'uid': 'schedule-2-uid', 'name': 'schedule2'}
        ])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.delete_schedule('test_schedule')
        self.assertIn('Multiple schedules found', str(context.exception))
    
    def test_delete_schedule_no_uid(self):
        """Test delete_schedule when UID is missing"""
        # Return response without UID
        self.session_mgr.rest_client.get = Mock(return_value=[{'name': 'test'}])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.delete_schedule('test')
        self.assertIn('UID missing', str(context.exception))
    
    def test_suspend_schedule_not_found(self):
        """Test suspend_schedule when schedule doesn't exist"""
        # Make get return empty list
        self.session_mgr.rest_client.get = Mock(return_value=[])
        
        with self.assertRaises(Exception):
            self.workflow.suspend_schedule('nonexistent')
    
    def test_resume_schedule_not_found(self):
        """Test resume_schedule when schedule doesn't exist"""
        # Make get return empty list
        self.session_mgr.rest_client.get = Mock(return_value=[])
        
        with self.assertRaises(Exception):
            self.workflow.resume_schedule('nonexistent')
    
    def test_get_schedule_info_with_exception(self):
        """Test get_schedule_info handles exceptions"""
        self.session_mgr.rest_client.get = Mock(side_effect=HPEStorageException("API Error"))
        
        with self.assertRaises(HPEStorageException):
            self.workflow.get_schedule_info('test_schedule')
    
    def test_suspend_schedule_multiple_found(self):
        """Test suspend_schedule when multiple schedules found"""
        # Make get return multiple schedules
        self.session_mgr.rest_client.get = Mock(return_value=[
            {'uid': 'schedule-1-uid', 'name': 'schedule1'},
            {'uid': 'schedule-2-uid', 'name': 'schedule2'}
        ])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.suspend_schedule('test_schedule')
        self.assertIn('Multiple schedules found', str(context.exception))
    
    def test_resume_schedule_multiple_found(self):
        """Test resume_schedule when multiple schedules found"""
        # Make get return multiple schedules
        self.session_mgr.rest_client.get = Mock(return_value=[
            {'uid': 'schedule-1-uid', 'name': 'schedule1'},
            {'uid': 'schedule-2-uid', 'name': 'schedule2'}
        ])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.resume_schedule('test_schedule')
        self.assertIn('Multiple schedules found', str(context.exception))
    
    def test_suspend_schedule_no_uid(self):
        """Test suspend_schedule when UID is missing"""
        # Return response without UID
        self.session_mgr.rest_client.get = Mock(return_value=[{'name': 'test'}])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.suspend_schedule('test')
        self.assertIn('UID missing', str(context.exception))
    
    def test_resume_schedule_no_uid(self):
        """Test resume_schedule when UID is missing"""
        # Return response without UID
        self.session_mgr.rest_client.get = Mock(return_value=[{'name': 'test'}])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.resume_schedule('test')
        self.assertIn('UID missing', str(context.exception))


class TestScheduleWorkflowIntegration(unittest.TestCase):
    """Integration tests for Schedule workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = ScheduleWorkflow(self.session_mgr, self.task_mgr)
    
    def test_schedule_lifecycle(self):
        """Test complete schedule lifecycle: create, get, modify, suspend, resume, dele"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_TIMESTAMP'
        }
        
        # Create
        create_result = self.workflow.create_schedule(
            'lifecycle_schedule',
            hour='10',
            minute='00',
            createsv=createsv_params
        )
        self.assertEqual(create_result['status'], 'created')
        
        # Get
        get_result = self.workflow.get_schedule_info('lifecycle_schedule')
        self.assertEqual(get_result[0]['name'], 'lifecycle_schedule')
        
        # Modify
        modify_result = self.workflow.modify_schedule(
            'lifecycle_schedule',
            hour='11',
            minute='30'
        )
        self.assertEqual(modify_result['status'], 'modified')
        
        # Suspend
        suspend_result = self.workflow.suspend_schedule('lifecycle_schedule')
        self.assertEqual(suspend_result['status'], 'created')
        
        # Resume
        resume_result = self.workflow.resume_schedule('lifecycle_schedule')
        self.assertEqual(resume_result['status'], 'created')
        
        # Delete
        delete_result = self.workflow.delete_schedule('lifecycle_schedule')
        self.assertEqual(delete_result['status'], 'deleted')
    
    def test_create_daily_backup_schedule(self):
        """Test creating a realistic daily backup schedule"""
        createsv_params = {
            'readOnly': True,
            'vvOrVvset': 'production_volumes',
            'namePattern': 'PARENT_TIMESTAMP',
            'expireSecs': 2592000,  # 30 days in seconds
            'retainSecs': 604800    # 7 days in seconds
        }
        
        result = self.workflow.create_schedule(
            'daily_backup',
            hour='2',
            minute='0',
            dayofmonth='*',
            month='*',
            createsv=createsv_params
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['hour'], '2')
        self.assertEqual(payload['minute'], '0')
        self.assertIn('createsv', payload)
        self.assertTrue(payload['createsv']['readOnly'])
    
    def test_create_hourly_snapshot_schedule(self):
        """Test creating an hourly snapshot schedule"""
        createsv_params = {
            'readOnly': False,
            'vvOrVvset': 'test_volume',
            'namePattern': 'PARENT_SEC_SINCE_EPOCH'
        }
        
        result = self.workflow.create_schedule(
            'hourly_snapshots',
            interval='60',
            minute='*',
            createsv=createsv_params
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertEqual(posted['payload']['interval'], '60')
    
    def test_preprocess_createsv_with_expiration_seconds(self):
        """Test preprocessing with explicit seconds unit for expiration"""
        createsv = {
            'vvOrVvset': 'test_vol',
            'namePattern': 'CUSTOM',
            'expiration_time': 7200,
            'expiration_unit': 'seconds'
        }
        result = self.workflow.create_schedule('test_sched', hour='12', minute='0', createsv=createsv)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        # Should have expireSecs and unit params removed
        self.assertEqual(posted['createsv']['expireSecs'], 7200)
        self.assertNotIn('expiration_time', posted['createsv'])
        self.assertNotIn('expiration_unit', posted['createsv'])
    
    def test_preprocess_createsv_with_expiration_days(self):
        """Test preprocessing with days unit for expiration"""
        createsv = {
            'vvOrVvset': 'test_vol',
            'namePattern': 'CUSTOM',
            'expiration_time': 2,
            'expiration_unit': 'days'
        }
        result = self.workflow.create_schedule('test_sched_days', hour='12', minute='0', createsv=createsv)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        # 2 days = 2 * 86400 = 172800 seconds
        self.assertEqual(posted['createsv']['expireSecs'], 172800)
    
    def test_preprocess_createsv_with_retention_seconds(self):
        """Test preprocessing with explicit seconds unit for retention"""
        createsv = {
            'vvOrVvset': 'test_vol',
            'namePattern': 'CUSTOM',
            'retention_time': 3600,
            'retention_unit': 'seconds'
        }
        result = self.workflow.create_schedule('test_sched_ret', hour='12', minute='0', createsv=createsv)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        self.assertEqual(posted['createsv']['retainSecs'], 3600)
        self.assertNotIn('retention_time', posted['createsv'])
        self.assertNotIn('retention_unit', posted['createsv'])
    
    def test_preprocess_createsv_with_retention_days(self):
        """Test preprocessing with days unit for retention"""
        createsv = {
            'vvOrVvset': 'test_vol',
            'namePattern': 'CUSTOM',
            'retention_time': 7,
            'retention_unit': 'days'
        }
        result = self.workflow.create_schedule('test_sched_ret_days', hour='12', minute='0', createsv=createsv)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        # 7 days = 7 * 86400 = 604800 seconds
        self.assertEqual(posted['createsv']['retainSecs'], 604800)
    
    def test_preprocess_createsv_with_both_times(self):
        """Test preprocessing with both expiration and retention"""
        createsv = {
            'vvOrVvset': 'test_vol',
            'namePattern': 'CUSTOM',
            'expiration_time': 12,
            'expiration_unit': 'hours',
            'retention_time': 3,
            'retention_unit': 'days'
        }
        result = self.workflow.create_schedule('test_both_times', hour='12', minute='0', createsv=createsv)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        # 12 hours = 43200, 3 days = 259200
        self.assertEqual(posted['createsv']['expireSecs'], 43200)
        self.assertEqual(posted['createsv']['retainSecs'], 259200)
    
    def test_preprocess_createsv_none_returns_none(self):
        """Test that preprocessing None createsv returns None"""
        result = self.workflow._preprocess_createsv_params(None)
        self.assertIsNone(result)
    
    def test_preprocess_createsv_empty_dict(self):
        """Test preprocessing empty createsv dict"""
        result = self.workflow._preprocess_createsv_params({})
        self.assertEqual(result, {})
    
    def test_create_schedule_with_createsv_dict(self):
        """Test creating schedule with createsv as dictionary"""
        createsv = {
            'vvOrVvset': 'prod_vol',
            'namePattern': 'CUSTOM',
            'readOnly': True,
            'expiration_time': 24,
            'expiration_unit': 'hours'
        }
        result = self.workflow.create_schedule(
            'dict_createsv_sched',
            hour='3',
            minute='0',
            createsv=createsv
        )
        self.assertEqual(result['status'], 'created')
    
    def test_execute_create_schedule_exception_handling(self):
        """Test that _execute_create_schedule returns Exception on POST failure"""
        # Mock POST to raise exception
        self.session_mgr.rest_client.post = Mock(side_effect=Exception("API Error"))
        
        createsv = {
            'vvOrVvset': 'test_vol',
            'namePattern': 'CUSTOM'
        }
        result = self.workflow._execute_create_schedule('error_schedule', hour='2', minute='0', createsv=createsv)
        
        # Should return the exception, not raise it
        self.assertIsInstance(result, Exception)
        self.assertIn('API Error', str(result))
    
    def test_modify_schedule_exception_handling(self):
        """Test modify_schedule with Exception result from _execute"""
        # Mock _execute_modify_schedule to return Exception
        error = Exception("Modification failed")
        with patch.object(self.workflow, '_execute_modify_schedule', return_value=error):
            with self.assertRaises(Exception) as context:
                self.workflow.modify_schedule('test_sched', hour='5')
            self.assertIn('Modification failed', str(context.exception))
    
    def test_delete_schedule_exception_handling(self):
        """Test delete_schedule with Exception result from _execute"""
        # Mock _execute_delete_schedule to return Exception
        error = Exception("Deletion failed")
        with patch.object(self.workflow, '_execute_delete_schedule', return_value=error):
            with self.assertRaises(Exception) as context:
                self.workflow.delete_schedule('test_sched')
            self.assertIn('Deletion failed', str(context.exception))
    
    def test_create_schedule_raises_hpe_storage_exception(self):
        """Test create_schedule raises HPEStorageException"""
        # Mock to raise HPEStorageException
        with patch.object(self.workflow, '_execute_create_schedule', side_effect=HPEStorageException("Storage error")):
            with self.assertRaises(HPEStorageException) as context:
                self.workflow.create_schedule('error_sched', hour='1')
            self.assertIn('Storage error', str(context.exception))
    
    def test_create_schedule_raises_generic_exception(self):
        """Test create_schedule raises generic Exception"""
        # Mock to raise generic Exception
        with patch.object(self.workflow, '_execute_create_schedule', side_effect=Exception("Generic error")):
            with self.assertRaises(Exception) as context:
                self.workflow.create_schedule('error_sched', hour='1')
            self.assertIn('Generic error', str(context.exception))
    
    def test_modify_schedule_raises_hpe_storage_exception(self):
        """Test modify_schedule raises HPEStorageException"""
        # Mock to raise HPEStorageException
        with patch.object(self.workflow, '_execute_modify_schedule', side_effect=HPEStorageException("Storage error")):
            with self.assertRaises(HPEStorageException) as context:
                self.workflow.modify_schedule('test_sched', hour='2')
            self.assertIn('Storage error', str(context.exception))
    
    def test_modify_schedule_raises_generic_exception(self):
        """Test modify_schedule raises generic Exception"""
        # Mock to raise generic Exception
        with patch.object(self.workflow, '_execute_modify_schedule', side_effect=Exception("Generic error")):
            with self.assertRaises(Exception) as context:
                self.workflow.modify_schedule('test_sched', hour='2')
            self.assertIn('Generic error', str(context.exception))
    
    def test_modify_schedule_with_createsv(self):
        """Test modifying schedule with createsv parameters"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-daily_sched-uid', 'name': 'daily_sched'})
        
        createsv = {
            'vvOrVvset': 'test_vol',
            'expiration_time': 12,
            'expiration_unit': 'hours'
        }
        result = self.workflow.modify_schedule('daily_sched', hour='5', createsv=createsv)
        
        # Verify preprocessing occurred
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        self.assertIn('createsv', payload)
        # 12 hours = 43200 seconds
        self.assertEqual(payload['createsv']['expireSecs'], 43200)
    
    def test_delete_schedule_multiple_found(self):
        """Test deleting schedule when multiple schedules found raises ValueError"""
        # Mock get_schedule_info to return multiple schedules
        with patch.object(self.workflow, 'get_schedule_info', return_value=[
            {'uid': 'sched-1', 'name': 'test_sched'},
            {'uid': 'sched-2', 'name': 'test_sched'}
        ]):
            with self.assertRaises(ValueError) as context:
                self.workflow.delete_schedule('test_sched')
            self.assertIn('Multiple schedules found', str(context.exception))
    
    def test_delete_schedule_missing_uid(self):
        """Test deleting schedule with missing UID raises ValueError"""
        # Mock get_schedule_info to return schedule without uid
        with patch.object(self.workflow, 'get_schedule_info', return_value=[{'name': 'test_sched'}]):
            with self.assertRaises(ValueError) as context:
                self.workflow.delete_schedule('test_sched')
            self.assertIn('schedule UID missing', str(context.exception))
    
    def test_delete_schedule_raises_hpe_storage_exception(self):
        """Test delete_schedule raises HPEStorageException"""
        # Mock to raise HPEStorageException
        with patch.object(self.workflow, '_execute_delete_schedule', side_effect=HPEStorageException("Storage error")):
            with self.assertRaises(HPEStorageException) as context:
                self.workflow.delete_schedule('test_sched')
            self.assertIn('Storage error', str(context.exception))
    
    def test_delete_schedule_raises_generic_exception(self):
        """Test delete_schedule raises generic Exception"""
        # Mock to raise generic Exception
        with patch.object(self.workflow, '_execute_delete_schedule', side_effect=Exception("Generic error")):
            with self.assertRaises(Exception) as context:
                self.workflow.delete_schedule('test_sched')
            self.assertIn('Generic error', str(context.exception))
    
    def test_suspend_schedule_raises_hpe_storage_exception(self):
        """Test suspend_schedule raises HPEStorageException"""
        # Mock to raise HPEStorageException
        with patch.object(self.workflow, '_execute_suspend_schedule', side_effect=HPEStorageException("Storage error")):
            with self.assertRaises(HPEStorageException) as context:
                self.workflow.suspend_schedule('test_sched')
            self.assertIn('Storage error', str(context.exception))
    
    def test_suspend_schedule_raises_generic_exception(self):
        """Test suspend_schedule raises generic Exception"""
        # Mock to raise generic Exception
        with patch.object(self.workflow, '_execute_suspend_schedule', side_effect=Exception("Generic error")):
            with self.assertRaises(Exception) as context:
                self.workflow.suspend_schedule('test_sched')
            self.assertIn('Generic error', str(context.exception))
    
    def test_resume_schedule_raises_hpe_storage_exception(self):
        """Test resume_schedule raises HPEStorageException"""
        # Mock to raise HPEStorageException
        with patch.object(self.workflow, '_execute_resume_schedule', side_effect=HPEStorageException("Storage error")):
            with self.assertRaises(HPEStorageException) as context:
                self.workflow.resume_schedule('test_sched')
            self.assertIn('Storage error', str(context.exception))
    
    def test_resume_schedule_raises_generic_exception(self):
        """Test resume_schedule raises generic Exception"""
        # Mock to raise generic Exception
        with patch.object(self.workflow, '_execute_resume_schedule', side_effect=Exception("Generic error")):
            with self.assertRaises(Exception) as context:
                self.workflow.resume_schedule('test_sched')
            self.assertIn('Generic error', str(context.exception))
    
    def test_execute_action_schedule_missing_uid(self):
        """Test _execute_action_schedule with missing UID raises ValueError"""
        # Mock get_schedule_info to return schedule without uid
        with patch.object(self.workflow, 'get_schedule_info', return_value=[{'name': 'test_sched'}]):
            with self.assertRaises(ValueError) as context:
                self.workflow._execute_action_schedule('test_sched', 'suspend_schedule')
            self.assertIn('Schedule UID missing', str(context.exception))
    
    def test_execute_action_schedule_exception_handling(self):
        """Test that _execute_action_schedule returns Exception on POST failure"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-daily_sched-uid', 'name': 'daily_sched'})
        
        # Mock POST to raise exception
        original_post = self.session_mgr.rest_client.post
        self.session_mgr.rest_client.post = Mock(side_effect=Exception("Action Error"))
        
        result = self.workflow._execute_action_schedule('daily_sched', 'suspend_schedule')
        
        # Restore original post
        self.session_mgr.rest_client.post = original_post
        
        # Should return the exception, not raise it
        self.assertIsInstance(result, Exception)
        self.assertIn('Action Error', str(result))
    
    def test_execute_delete_schedule_exception_returns(self):
        """Test that _execute_delete_schedule returns Exception on DELETE failure"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-daily_sched-uid', 'name': 'daily_sched'})
        
        # Mock DELETE to raise exception
        original_delete = self.session_mgr.rest_client.delete
        self.session_mgr.rest_client.delete = Mock(side_effect=Exception("Delete Error"))
        
        result = self.workflow._execute_delete_schedule('daily_sched')
        
        # Restore original delete
        self.session_mgr.rest_client.delete = original_delete
        
        # Should return the exception, not raise it
        self.assertIsInstance(result, Exception)
        self.assertIn('Delete Error', str(result))
    
    def test_execute_modify_schedule_exception_returns(self):
        """Test that _execute_modify_schedule returns Exception on PATCH failure"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-daily_sched-uid', 'name': 'daily_sched'})
        
        # Mock PATCH to raise exception
        original_patch = self.session_mgr.rest_client.patch
        self.session_mgr.rest_client.patch = Mock(side_effect=Exception("Modify Error"))
        
        result = self.workflow._execute_modify_schedule('daily_sched', hour='3')
        
        # Restore original patch
        self.session_mgr.rest_client.patch = original_patch
        
        # Should return the exception, not raise it
        self.assertIsInstance(result, Exception)
        self.assertIn('Modify Error', str(result))
    
    def test_preprocess_createsv_with_none_expiration_result(self):
        """Test preprocessing when time conversion returns None for expiration"""
        # Mock _convert_to_seconds to return None
        with patch('hpe_storage_flowkit_py.v3.src.workflows.schedule._convert_to_seconds', return_value=None):
            createsv = {
                'vvOrVvset': 'test_vol',
                'expiration_time': 12,
                'expiration_unit': 'invalid'
            }
            result = self.workflow._preprocess_createsv_params(createsv)
            # Should not have expireSecs key
            self.assertNotIn('expireSecs', result)
    
    def test_preprocess_createsv_with_none_retention_result(self):
        """Test preprocessing when time conversion returns None for retention"""
        # Mock _convert_to_seconds to return None
        with patch('hpe_storage_flowkit_py.v3.src.workflows.schedule._convert_to_seconds', return_value=None):
            createsv = {
                'vvOrVvset': 'test_vol',
                'retention_time': 24,
                'retention_unit': 'invalid'
            }
            result = self.workflow._preprocess_createsv_params(createsv)
            # Should not have retainSecs key
            self.assertNotIn('retainSecs', result)
    
    def test_create_schedule_with_existing_schedule(self):
        """Test creating schedule when it already exists raises exception"""
        # Mock get_schedule_info to return existing schedule
        with patch.object(self.workflow, 'get_schedule_info', return_value=[{'uid': 'sched-uid', 'name': 'existing_sched'}]):
            with self.assertRaises(ScheduleAlreadyExists) as context:
                self.workflow.create_schedule('existing_sched', hour='2')
            self.assertIn('existing_sched', str(context.exception))
    
    def test_execute_create_schedule_full_flow(self):
        """Test _execute_create_schedule with full parameter flow"""
        # Mock get_schedule_info to return None (schedule doesn't exist)
        with patch.object(self.workflow, 'get_schedule_info', return_value=None):
            createsv = {
                'vvOrVvset': 'test_vol',
                'namePattern': 'CUSTOM',
                'readOnly': True,
                'expiration_time': 24,
                'expiration_unit': 'hours'
            }
            result = self.workflow._execute_create_schedule(
                'new_schedule',
                hour='3',
                minute='30',
                createsv=createsv
            )
            
            # Verify POST was called
            self.assertEqual(len(self.session_mgr.rest_client.posted_data), 1)
            posted = self.session_mgr.rest_client.posted_data[-1]
            self.assertEqual(posted['endpoint'], '/schedules')
            self.assertIn('createsv', posted['payload'])
            # 24 hours = 86400 seconds
            self.assertEqual(posted['payload']['createsv']['expireSecs'], 86400)
    
    def test_create_schedule_wrapper_with_hpe_exception(self):
        """Test create_schedule wrapper catches and re-raises HPEStorageException"""
        # Make get_schedule_info return existing schedule to trigger ScheduleAlreadyExists
        # which is a subclass of HPEStorageException
        with patch.object(self.workflow, 'get_schedule_info', return_value=[{'uid': 'uid1'}]):
            try:
                self.workflow.create_schedule('duplicate_sched', hour='1')
                self.fail("Expected ScheduleAlreadyExists to be raised")
            except HPEStorageException as e:
                # Should catch and re-raise
                self.assertIn('duplicate_sched', str(e))
    
    def test_create_schedule_wrapper_with_generic_exception(self):
        """Test create_schedule wrapper catches and re-raises generic Exception"""
        # Make _execute_create_schedule raise a generic exception
        with patch.object(self.workflow, '_execute_create_schedule', side_effect=ValueError("Invalid param")):
            try:
                self.workflow.create_schedule('error_sched', hour='1')
                self.fail("Expected ValueError to be raised")
            except ValueError as e:
                # Should catch and re-raise
                self.assertIn('Invalid param', str(e))
    
    def test_action_schedule_with_kwargs(self):
        """Test _execute_action_schedule with additional kwargs parameters"""
        # Add schedule to existing schedules
        self.session_mgr.rest_client.existing_schedules.append(
            {'uid': 'schedule-daily_sched-uid', 'name': 'daily_sched'})
        
        result = self.workflow._execute_action_schedule('daily_sched', 'suspend_schedule', extra_param='value')
        
        # Verify POST was called with parameters
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertEqual(posted['payload']['action'], 'suspend_schedule')
        self.assertIn('extra_param', posted['payload']['parameters'])
        self.assertEqual(posted['payload']['parameters']['extra_param'], 'value')
    
    def test_suspend_schedule_wrapper_exception(self):
        """Test suspend_schedule wrapper with exception from _execute"""
        error = Exception("Suspend failed")
        with patch.object(self.workflow, '_execute_suspend_schedule', return_value=error):
            with self.assertRaises(Exception) as context:
                self.workflow.suspend_schedule('test_sched')
            self.assertIn('Suspend failed', str(context.exception))
    
    def test_resume_schedule_wrapper_exception(self):
        """Test resume_schedule wrapper with exception from _execute"""
        error = Exception("Resume failed")
        with patch.object(self.workflow, '_execute_resume_schedule', return_value=error):
            with self.assertRaises(Exception) as context:
                self.workflow.resume_schedule('test_sched')
            self.assertIn('Resume failed', str(context.exception))


if __name__ == '__main__':
    unittest.main()
