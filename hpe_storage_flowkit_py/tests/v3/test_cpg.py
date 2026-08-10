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

from hpe_storage_flowkit_py.v3.src.workflows.cpg import CpgWorkflow
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException
from hpe_storage_flowkit_py.v3.src.validators.cpg_validator import validate_cpg_params


class MockSessionManager:
    """Mock session manager for testing"""
    def __init__(self):
        self.rest_client = MockRestClient()


class MockTaskManager:
    """Mock task manager for testing"""
    def __init__(self, session_mgr=None):
        self.session_mgr = session_mgr
    
    def waitForTaskToEnd(self, task_id, poll_rate_secs=15):
        """Mock wait for task completion"""
        return {'status': 'completed', 'taskId': task_id}


class MockRestClient:
    """Mock REST client for testing"""
    def __init__(self):
        self.responses = {}
        self.posted_data = []
        self.deleted_endpoints = []
        self.existing_cpgs = set()  # Track which CPGs "exist"
        
    def post(self, endpoint, payload):
        self.posted_data.append({'endpoint': endpoint, 'payload': payload})
        name = payload.get('name')
        if name:
            self.existing_cpgs.add(name)
        return {'status': 'created', 'name': name, 'payload': payload}
    
    def delete(self, endpoint):
        self.deleted_endpoints.append(endpoint)
        return {'status': 'deleted', 'endpoint': endpoint}
    
    def get(self, endpoint, headers=None):
        if '/cpgs?name=' in endpoint:
            name = endpoint.split('=')[1]
            # Return empty list if CPG doesn't exist (for existence check)
            if name in self.existing_cpgs:
                return [{'uid': f'cpg-{name}-uid', 'name': name}]
            else:
                return []
        elif endpoint == '/cpgs':
            return {'members': [
                {'uid': 'cpg-1', 'name': 'CPG1'},
                {'uid': 'cpg-2', 'name': 'CPG2'}
            ]}
        return {}


class TestCpgWorkflow(unittest.TestCase):
    """Comprehensive unit tests for CPG workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = CpgWorkflow(self.session_mgr, self.task_mgr)
    
    def _simulate_cpg_exists(self, name):
        """Helper to mark a CPG as existing"""
        self.session_mgr.rest_client.existing_cpgs.add(name)
    
    def test_create_cpg_basic(self):
        """Test creating CPG with only name"""
        result = self.workflow.create_cpg('test_cpg')
        self.assertEqual(result['status'], 'created')
        self.assertEqual(result['name'], 'test_cpg')
    
    def test_create_cpg_with_domain(self):
        """Test creating CPG with domain"""
        result = self.workflow.create_cpg('test_cpg', domain='test_domain')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('domain', posted['payload'])
        self.assertEqual(posted['payload']['domain'], 'test_domain')
    
    def test_create_cpg_with_growth_size(self):
        """Test creating CPG with growthSizeMiB"""
        result = self.workflow.create_cpg('test_cpg', growthSizeMiB=10240)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('growthSizeMiB', posted['payload'])
        self.assertEqual(posted['payload']['growthSizeMiB'], 10240)
    
    def test_create_cpg_with_growth_limit(self):
        """Test creating CPG with growthLimitMiB"""
        result = self.workflow.create_cpg('test_cpg', growthLimitMiB=102400)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('growthLimitMiB', posted['payload'])
        self.assertEqual(posted['payload']['growthLimitMiB'], 102400)
    
    def test_create_cpg_with_growth_warning(self):
        """Test creating CPG with growthWarnMiB"""
        result = self.workflow.create_cpg('test_cpg', growthWarnMiB=51200)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('growthWarnMiB', posted['payload'])
        self.assertEqual(posted['payload']['growthWarnMiB'], 51200)
    
    def test_create_cpg_with_ha(self):
        """Test creating CPG with high availability setting"""
        result = self.workflow.create_cpg('test_cpg', ha='HAJBOD_JBOD')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('ha', posted['payload'])
        self.assertEqual(posted['payload']['ha'], 'HAJBOD_JBOD')
    
    def test_create_cpg_with_cage(self):
        """Test creating CPG with cage parameter"""
        result = self.workflow.create_cpg('test_cpg', cage='cage1')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('cage', posted['payload'])
        self.assertEqual(posted['payload']['cage'], 'cage1')
    
    def test_create_cpg_with_position(self):
        """Test creating CPG with position parameter"""
        result = self.workflow.create_cpg('test_cpg', position='POSITION_FIRST')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('position', posted['payload'])
        self.assertEqual(posted['payload']['position'], 'POSITION_FIRST')
    
    def test_create_cpg_with_key_value_pairs(self):
        """Test creating CPG with keyValuePairs"""
        kvp = {'env': 'production', 'owner': 'team1'}
        result = self.workflow.create_cpg('test_cpg', keyValuePairs=kvp)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertIn('keyValuePairs', posted['payload'])
        self.assertEqual(posted['payload']['keyValuePairs'], kvp)
    
    def test_create_cpg_with_all_parameters(self):
        """Test creating CPG with all possible parameters"""
        result = self.workflow.create_cpg(
            'test_cpg',
            domain='production',
            growthSizeMiB=10240,
            growthLimitMiB=102400,
            growthWarnMiB=81920,
            ha='HAJBOD_DISK',
            cage='cage1',
            position='POSITION_FIRST',
            keyValuePairs={'env': 'prod'}
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['name'], 'test_cpg')
        self.assertEqual(payload['domain'], 'production')
        self.assertEqual(payload['growthSizeMiB'], 10240)
        self.assertEqual(payload['growthLimitMiB'], 102400)
        self.assertEqual(payload['growthWarnMiB'], 81920)
        self.assertEqual(payload['ha'], 'HAJBOD_DISK')
        self.assertEqual(payload['cage'], 'cage1')
        self.assertEqual(payload['position'], 'POSITION_FIRST')
        self.assertEqual(payload['keyValuePairs'], {'env': 'prod'})
    
    def test_list_cpgs(self):
        """Test listing all CPGs"""
        result = self.workflow.list_cpgs()
        
        self.assertIn('members', result)
        self.assertEqual(len(result['members']), 2)
        self.assertEqual(result['members'][0]['name'], 'CPG1')
        self.assertEqual(result['members'][1]['name'], 'CPG2')
    
    def test_create_cpg_invalid_name(self):
        """Test creating CPG with invalid name should raise error"""
        with self.assertRaises(Exception):
            self.workflow.create_cpg('')
    
    def test_create_cpg_none_name(self):
        """Test creating CPG with None name should raise error"""
        with self.assertRaises(Exception):
            self.workflow.create_cpg(None)
    
    def test_delete_cpg_invalid_name(self):
        """Test deleting CPG with invalid name should raise error"""
        with self.assertRaises(Exception):
            self.workflow.delete_cpg('')
    
    def test_create_cpg_with_unknown_parameter(self):
        """Test creating CPG with unknown parameter should raise error"""
        with self.assertRaises(ValueError):
            self.workflow.create_cpg('test_cpg', unknown_param='value')
    
    def test_create_cpg_multiple_kwargs(self):
        """Test creating CPG with multiple kwargs"""
        result = self.workflow.create_cpg(
            'test_cpg',
            domain='test_domain',
            growthSizeMiB=5120,
            ha='HAJBOD_JBOD'
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['domain'], 'test_domain')
        self.assertEqual(payload['growthSizeMiB'], 5120)
        self.assertEqual(payload['ha'], 'HAJBOD_JBOD')
    
    # ===================================================================
    # CPG ALREADY EXISTS TESTS
    # ===================================================================
    
    def test_create_cpg_already_exists(self):
        """Test creating CPG that already exists raises error"""
        self._simulate_cpg_exists('existing_cpg')
        with self.assertRaises(Exception) as context:
            self.workflow.create_cpg('existing_cpg')
        self.assertIn("already exists", str(context.exception))
    
    # ===================================================================
    # DELETE CPG TESTS
    # ===================================================================
    
    def test_delete_cpg_success(self):
        """Test deleting existing CPG"""
        self._simulate_cpg_exists('test_cpg')
        result = self.workflow.delete_cpg('test_cpg')
        
        self.assertEqual(result['status'], 'deleted')
        self.assertIn('cpg-test_cpg-uid', self.session_mgr.rest_client.deleted_endpoints[0])
    
    def test_delete_cpg_not_exists(self):
        """Test deleting non-existent CPG raises error"""
        with self.assertRaises(Exception) as context:
            self.workflow.delete_cpg('nonexistent_cpg')
        self.assertIn("does not exist", str(context.exception).lower())
    
    # ===================================================================
    # VALIDATOR TESTS - NAME VALIDATION
    # ===================================================================
    
    def test_create_cpg_name_too_long(self):
        """Test CPG name longer than 31 characters"""
        long_name = 'a' * 32
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg(long_name)
        self.assertIn("31 characters", str(context.exception))
    
    def test_create_cpg_name_not_string(self):
        """Test CPG name as non-string type"""
        with self.assertRaises(ValueError):
            self.workflow.create_cpg(123)
    
    # ===================================================================
    # VALIDATOR TESTS - DOMAIN VALIDATION
    # ===================================================================
    
    def test_create_cpg_domain_not_string(self):
        """Test domain parameter as non-string"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', domain=123)
        self.assertIn("domain must be a string", str(context.exception))
    
    def test_create_cpg_domain_empty_string(self):
        """Test domain parameter as empty string"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', domain='')
        self.assertIn("domain name cannot be empty", str(context.exception))
    
    # ===================================================================
    # VALIDATOR TESTS - CAGE VALIDATION
    # ===================================================================
    
    def test_create_cpg_cage_not_string(self):
        """Test cage parameter as non-string"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', cage=123)
        self.assertIn("cage must be a string", str(context.exception))
    
    def test_create_cpg_cage_empty_string(self):
        """Test cage parameter as empty string"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', cage='')
        self.assertIn("cage cannot be empty", str(context.exception))
    
    # ===================================================================
    # VALIDATOR TESTS - POSITION VALIDATION
    # ===================================================================
    
    def test_create_cpg_position_not_string(self):
        """Test position parameter as non-string"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', position=123)
        self.assertIn("position must be a string", str(context.exception))
    
    def test_create_cpg_position_empty_string(self):
        """Test position parameter as empty string"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', position='')
        self.assertIn("position cannot be empty", str(context.exception))
    
    # ===================================================================
    # VALIDATOR TESTS - GROWTH SIZE VALIDATION
    # ===================================================================
    
    def test_create_cpg_growthSizeMiB_not_number(self):
        """Test growthSizeMiB as non-numeric"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', growthSizeMiB='invalid')
        self.assertIn("growthSizeMiB must be a number", str(context.exception))
    
    def test_create_cpg_growthSizeMiB_negative(self):
        """Test growthSizeMiB as negative value"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', growthSizeMiB=-100)
        self.assertIn("growthSizeMiB must be a non-negative", str(context.exception))
    
    def test_create_cpg_growthSizeMiB_zero(self):
        """Test growthSizeMiB as zero (valid)"""
        result = self.workflow.create_cpg('test_cpg', growthSizeMiB=0)
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertEqual(posted['payload']['growthSizeMiB'], 0)
    
    def test_create_cpg_growthSizeMiB_float(self):
        """Test growthSizeMiB as float value"""
        result = self.workflow.create_cpg('test_cpg', growthSizeMiB=5120.5)
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertEqual(posted['payload']['growthSizeMiB'], 5120.5)
    
    # ===================================================================
    # VALIDATOR TESTS - GROWTH LIMIT VALIDATION
    # ===================================================================
    
    def test_create_cpg_growthLimitMiB_not_number(self):
        """Test growthLimitMiB as non-numeric"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', growthLimitMiB='invalid')
        self.assertIn("growthLimitMiB must be a number", str(context.exception))
    
    def test_create_cpg_growthLimitMiB_negative(self):
        """Test growthLimitMiB as negative value"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', growthLimitMiB=-100)
        self.assertIn("growthLimitMiB must be a non-negative", str(context.exception))
    
    def test_create_cpg_growthLimitMiB_zero(self):
        """Test growthLimitMiB as zero (valid)"""
        result = self.workflow.create_cpg('test_cpg', growthLimitMiB=0)
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertEqual(posted['payload']['growthLimitMiB'], 0)
    
    # ===================================================================
    # VALIDATOR TESTS - GROWTH WARNING VALIDATION
    # ===================================================================
    
    def test_create_cpg_growthWarnMiB_not_number(self):
        """Test growthWarnMiB as non-numeric"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', growthWarnMiB='invalid')
        self.assertIn("growthWarnMiB must be a number", str(context.exception))
    
    def test_create_cpg_growthWarnMiB_negative(self):
        """Test growthWarnMiB as negative value"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', growthWarnMiB=-100)
        self.assertIn("growthWarnMiB must be a non-negative", str(context.exception))
    
    def test_create_cpg_growthWarnMiB_zero(self):
        """Test growthWarnMiB as zero (valid)"""
        result = self.workflow.create_cpg('test_cpg', growthWarnMiB=0)
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertEqual(posted['payload']['growthWarnMiB'], 0)
    
    # ===================================================================
    # VALIDATOR TESTS - HA VALIDATION
    # ===================================================================
    
    def test_create_cpg_ha_not_string(self):
        """Test ha parameter as non-string"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', ha=123)
        self.assertIn("ha must be a string", str(context.exception))
    
    def test_create_cpg_ha_invalid_value(self):
        """Test ha parameter with invalid value"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', ha='INVALID_HA')
        self.assertIn("ha must be one of", str(context.exception))
    
    def test_create_cpg_ha_valid_HAJBOD_DISK(self):
        """Test ha parameter with valid HAJBOD_DISK value"""
        result = self.workflow.create_cpg('test_cpg', ha='HAJBOD_DISK')
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertEqual(posted['payload']['ha'], 'HAJBOD_DISK')
    
    # ===================================================================
    # VALIDATOR TESTS - KEY VALUE PAIRS VALIDATION
    # ===================================================================
    
    def test_create_cpg_keyValuePairs_not_dict(self):
        """Test keyValuePairs as non-dict"""
        with self.assertRaises(ValueError) as context:
            self.workflow.create_cpg('test_cpg', keyValuePairs='invalid')
        self.assertIn("keyValuePairs must be a dictionary", str(context.exception))
    
    def test_create_cpg_keyValuePairs_empty_dict(self):
        """Test keyValuePairs as empty dict (valid)"""
        result = self.workflow.create_cpg('test_cpg', keyValuePairs={})
        posted = self.session_mgr.rest_client.posted_data[-1]
        self.assertEqual(posted['payload']['keyValuePairs'], {})
    
    # ===================================================================
    # PREPROCESSING TESTS - UNIT CONVERSION
    # ===================================================================
    
    def test_preprocess_growth_increment_with_unit(self):
        """Test preprocessing growth_increment with unit conversion"""
        params = {
            'growth_increment': 10,
            'growth_increment_unit': 'GiB'
        }
        result = self.workflow._preprocess_create_cpg(params)
        self.assertIn('growthSizeMiB', result)
        self.assertNotIn('growth_increment', result)
        self.assertNotIn('growth_increment_unit', result)
        self.assertEqual(result['growthSizeMiB'], 10240)  # 10 GiB = 10240 MiB
    
    def test_preprocess_growth_limit_with_unit(self):
        """Test preprocessing growth_limit with unit conversion"""
        params = {
            'growth_limit': 100,
            'growth_limit_unit': 'GiB'
        }
        result = self.workflow._preprocess_create_cpg(params)
        self.assertIn('growthLimitMiB', result)
        self.assertNotIn('growth_limit', result)
        self.assertNotIn('growth_limit_unit', result)
        self.assertEqual(result['growthLimitMiB'], 102400)  # 100 GiB = 102400 MiB
    
    def test_preprocess_growth_warning_with_unit(self):
        """Test preprocessing growth_warning with unit conversion"""
        params = {
            'growth_warning': 80,
            'growth_warning_unit': 'GiB'
        }
        result = self.workflow._preprocess_create_cpg(params)
        self.assertIn('growthWarnMiB', result)
        self.assertNotIn('growth_warning', result)
        self.assertNotIn('growth_warning_unit', result)
        self.assertEqual(result['growthWarnMiB'], 81920)  # 80 GiB = 81920 MiB
    
    def test_preprocess_none_params(self):
        """Test preprocessing with None params"""
        result = self.workflow._preprocess_create_cpg(None)
        self.assertEqual(result, {})
    
    def test_preprocess_mixed_unit_and_direct_params(self):
        """Test preprocessing with both unit conversion and direct MiB params"""
        params = {
            'growth_increment': 5,
            'growth_increment_unit': 'GiB',
            'growthLimitMiB': 102400,
            'domain': 'production'
        }
        result = self.workflow._preprocess_create_cpg(params)
        self.assertEqual(result['growthSizeMiB'], 5120)
        self.assertEqual(result['growthLimitMiB'], 102400)
        self.assertEqual(result['domain'], 'production')
    
    def test_preprocess_growth_increment_none_value(self):
        """Test preprocessing when growth_increment is None"""
        params = {
            'growth_increment': None,
            'growth_increment_unit': 'GiB'
        }
        result = self.workflow._preprocess_create_cpg(params)
        self.assertNotIn('growthSizeMiB', result)
    
    # ===================================================================
    # GET CPG INFO TESTS
    # ===================================================================
    
    def test_get_cpg_info_exists(self):
        """Test getting info for existing CPG"""
        self._simulate_cpg_exists('test_cpg')
        result = self.workflow.get_cpg_info('test_cpg')
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'test_cpg')
    
    def test_get_cpg_info_not_exists(self):
        """Test getting info for non-existent CPG returns empty list"""
        result = self.workflow.get_cpg_info('nonexistent')
        self.assertEqual(result, [])
    
    # ===================================================================
    # LIST CPGS TESTS
    # ===================================================================
    
    def test_list_cpgs_returns_members(self):
        """Test list_cpgs returns proper structure"""
        result = self.workflow.list_cpgs()
        self.assertIn('members', result)
        self.assertIsInstance(result['members'], list)
    
    # ===================================================================
    # EDGE CASES
    # ===================================================================
    
    def test_create_cpg_with_none_optional_params(self):
        """Test creating CPG with None values for optional params"""
        result = self.workflow.create_cpg('test_cpg', domain=None, growthSizeMiB=None)
        # None values should be included but validation should pass
        self.assertEqual(result['status'], 'created')
    
    def test_create_cpg_validation_params_not_dict(self):
        """Test validation with non-dict params raises error"""
        with self.assertRaises(ValueError) as context:
            validate_cpg_params('test', 'not_a_dict')
        self.assertIn("params must be a dictionary", str(context.exception))


class TestCpgWorkflowIntegration(unittest.TestCase):
    """Integration tests for CPG workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = CpgWorkflow(self.session_mgr, self.task_mgr)
    
    def _simulate_cpg_exists(self, name):
        """Helper to mark a CPG as existing"""
        self.session_mgr.rest_client.existing_cpgs.add(name)
    
    def test_create_and_delete_cpg_flow(self):
        """Test complete create and delete flow"""
        # Create CPG
        create_result = self.workflow.create_cpg('integration_cpg')
        self.assertEqual(create_result['status'], 'created')
        
        # Verify CPG was marked as existing by create operation
        self.assertIn('integration_cpg', self.session_mgr.rest_client.existing_cpgs)
        
        # Get CPG info
        info_result = self.workflow.get_cpg_info('integration_cpg')
        self.assertEqual(info_result[0]['name'], 'integration_cpg')
        
        # Delete CPG
        delete_result = self.workflow.delete_cpg('integration_cpg')
        self.assertEqual(delete_result['status'], 'deleted')
    
    def test_create_cpg_with_complex_configuration(self):
        """Test creating CPG with complex real-world configuration"""
        result = self.workflow.create_cpg(
            'prod_cpg',
            domain='production',
            growthSizeMiB=5120,
            growthLimitMiB=512000,
            growthWarnMiB=409600,
            ha='HAJBOD_JBOD',
            cage='cage1',
            keyValuePairs={'env': 'prod', 'team': 'storage'}
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        # Verify all parameters
        self.assertEqual(payload['name'], 'prod_cpg')
        self.assertEqual(payload['domain'], 'production')
        self.assertEqual(payload['growthSizeMiB'], 5120)
        self.assertEqual(payload['growthLimitMiB'], 512000)
        self.assertEqual(payload['growthWarnMiB'], 409600)
        self.assertEqual(payload['ha'], 'HAJBOD_JBOD')
        self.assertEqual(payload['cage'], 'cage1')
        self.assertEqual(payload['keyValuePairs']['env'], 'prod')
        self.assertEqual(payload['keyValuePairs']['team'], 'storage')
    
    def test_delete_cpg_missing_uid(self):
        """Test delete CPG when UID is missing from response"""
        # Mock get_cpg_info to return CPG without UID
        original_get = self.workflow.get_cpg_info
        self.workflow.get_cpg_info = lambda name: [{'name': name}]
        
        with self.assertRaises(ValueError) as context:
            self.workflow.delete_cpg('test_cpg')
        
        self.assertIn('UID missing', str(context.exception))
        
        # Restore
        self.workflow.get_cpg_info = original_get
    
    def test_get_cpg_info_hpe_storage_exception(self):
        """Test get_cpg_info when HPEStorageException is raised"""
        # Mock rest_client.get to raise HPEStorageException
        original_get = self.session_mgr.rest_client.get
        
        def mock_get_exception(endpoint, headers=None):
            raise HPEStorageException("Storage subsystem error")
        
        self.session_mgr.rest_client.get = mock_get_exception
        
        with self.assertRaises(HPEStorageException):
            self.workflow.get_cpg_info('test_cpg')
        
        # Restore
        self.session_mgr.rest_client.get = original_get
    
    def test_list_cpgs_hpe_storage_exception(self):
        """Test list_cpgs when HPEStorageException is raised"""
        # Mock rest_client.get to raise HPEStorageException
        original_get = self.session_mgr.rest_client.get
        
        def mock_get_exception(endpoint, headers=None):
            raise HPEStorageException("Storage subsystem error")
        
        self.session_mgr.rest_client.get = mock_get_exception
        
        with self.assertRaises(HPEStorageException):
            self.workflow.list_cpgs()
        
        # Restore
        self.session_mgr.rest_client.get = original_get
    
    def test_create_cpg_rest_client_exception(self):
        """Test create_cpg when REST client post raises exception"""
        # Mock rest_client.post to raise an exception
        original_post = self.session_mgr.rest_client.post
        
        def mock_post_exception(endpoint, payload):
            raise RuntimeError("Network error")
        
        self.session_mgr.rest_client.post = mock_post_exception
        
        with self.assertRaises(Exception):
            self.workflow.create_cpg('test_cpg')
        
        # Restore
        self.session_mgr.rest_client.post = original_post
    
    def test_delete_cpg_rest_client_exception(self):
        """Test delete_cpg when REST client delete raises exception"""
        # First ensure the CPG exists
        self.session_mgr.rest_client.existing_cpgs.add('test_cpg')
        
        # Mock rest_client.delete to raise an exception
        original_delete = self.session_mgr.rest_client.delete
        
        def mock_delete_exception(endpoint):
            raise RuntimeError("Network error")
        
        self.session_mgr.rest_client.delete = mock_delete_exception
        
        with self.assertRaises(Exception):
            self.workflow.delete_cpg('test_cpg')
        
        # Restore
        self.session_mgr.rest_client.delete = original_delete


if __name__ == '__main__':
    unittest.main()
