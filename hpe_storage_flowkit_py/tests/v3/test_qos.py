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

from hpe_storage_flowkit_py.v3.src.workflows.qos import QosWorkflow
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, QosAlreadyExists, QosDoesNotExist
from hpe_storage_flowkit_py.v3.src.validators.qos_validator import validate_qos_params


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
        self.patched_data = []
        self.deleted_endpoints = []
        self.existing_qos = set()  # Track created QoS rules
        
    def post(self, endpoint, payload):
        self.posted_data.append({'endpoint': endpoint, 'payload': payload})
        # Add to existing QoS when created
        if '/qosconfigs' in endpoint:
            target_name = payload.get('targetName')
            if target_name:
                self.existing_qos.add(target_name)
        return {
            'status': 'created',
            'uid': 'qos-rule-123',
            'targetName': payload.get('targetName'),
            'payload': payload
        }
    
    def patch(self, endpoint, payload):
        self.patched_data.append({'endpoint': endpoint, 'payload': payload})
        return {
            'status': 'modified',
            'endpoint': endpoint,
            'payload': payload
        }
    
    def delete(self, endpoint):
        self.deleted_endpoints.append(endpoint)
        # Remove from existing QoS when deleted
        # Extract target name from UID pattern if needed
        return {'status': 'deleted', 'endpoint': endpoint}
    
    def get(self, endpoint, headers=None):
        if '/qosconfigs?targetName=' in endpoint:
            name = endpoint.split('=')[1]
            # Return existing only if it was created or is in existing_qos set
            if name in self.existing_qos:
                return [{
                    'uid': f'qos-{name}-uid',
                    'targetName': name,
                    'targetType': 'QOS_TGT_VVSET',
                    'iopsMaxLimit': 10000,
                    'bandwidthMaxLimitKiB': 102400
                }]
            return []
        elif endpoint == '/qosconfigs':
            # List all QoS - return based on existing_qos
            members = []
            for idx, name in enumerate(self.existing_qos, start=1):
                members.append({
                    'uid': f'qos-{idx}',
                    'targetName': name,
                    'targetType': 'QOS_TGT_VVSET'
                })
            return {'members': members}
        return {}


class TestQosWorkflow(unittest.TestCase):
    """Comprehensive unit tests for QoS workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = QosWorkflow(self.session_mgr, self.task_mgr)
        # Pre-create some QoS rules for modify/delete/get tests
        self.session_mgr.rest_client.existing_qos.add('existing_vvset')
        self.session_mgr.rest_client.existing_qos.add('vvset2')
    
    def test_create_qos_basic(self):
        """Test creating QoS rule with basic parameters"""
        qos = {
            'iopsMaxLimit': 5000,
            'bandwidthMaxLimitKiB': 51200
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        self.assertEqual(result['status'], 'created')
        self.assertEqual(result['targetName'], 'vvset1')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['targetName'], 'vvset1')
        self.assertEqual(payload['iopsMaxLimit'], 5000)
        self.assertEqual(payload['bandwidthMaxLimitKiB'], 51200)
    
    def test_create_qos_with_default_target_type(self):
        """Test creating QoS with default target type"""
        qos = {
            'iopsMaxLimit': 10000
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        # Should default to QOS_TGT_VVSET
        self.assertEqual(payload['targetType'], 'QOS_TGT_VVSET')
    
    def test_create_qos_with_custom_target_type(self):
        """Test creating QoS with custom target type"""
        qos = {
            'iopsMaxLimit': 5000,
            'targetType': 'QOS_TGT_VV'
        }
        result = self.workflow.create_qos('volume1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['targetType'], 'QOS_TGT_VV')
        self.assertEqual(payload['targetName'], 'volume1')
    
    def test_create_qos_only_iops(self):
        """Test creating QoS with only IOPS limit"""
        qos = {
            'iopsMaxLimit': 8000
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['iopsMaxLimit'], 8000)
        self.assertNotIn('bandwidthMaxLimitKiB', payload)
    
    def test_create_qos_only_bandwidth(self):
        """Test creating QoS with only bandwidth limit"""
        qos = {
            'bandwidthMaxLimitKiB': 204800
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['bandwidthMaxLimitKiB'], 204800)
        self.assertNotIn('iopsMaxLimit', payload)
    
    def test_create_qos_with_both_limits(self):
        """Test creating QoS with both IOPS and bandwidth limits"""
        qos = {
            'iopsMaxLimit': 15000,
            'bandwidthMaxLimitKiB': 307200
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['iopsMaxLimit'], 15000)
        self.assertEqual(payload['bandwidthMaxLimitKiB'], 307200)
    
    def test_create_qos_converts_to_int(self):
        """Test that QoS values are converted to integers"""
        qos = {
            'iopsMaxLimit': 5000,
            'bandwidthMaxLimitKiB': 51200
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        # Should be integers
        self.assertIsInstance(payload['iopsMaxLimit'], int)
        self.assertIsInstance(payload['bandwidthMaxLimitKiB'], int)
        self.assertEqual(payload['iopsMaxLimit'], 5000)
        self.assertEqual(payload['bandwidthMaxLimitKiB'], 51200)
    
    def test_modify_qos_enable(self):
        """Test modifying QoS to enable"""
        result = self.workflow.modify_qos('existing_vvset', enable=True)
        
        self.assertEqual(result['status'], 'modified')
        
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        
        self.assertTrue(payload['enable'])
    
    def test_modify_qos_disable(self):
        """Test modifying QoS to disable"""
        result = self.workflow.modify_qos('existing_vvset', enable=False)
        
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        
        self.assertFalse(payload['enable'])
    
    def test_modify_qos_iops(self):
        """Test modifying QoS IOPS limit"""
        result = self.workflow.modify_qos('existing_vvset', iopsMaxLimit=20000)
        
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        
        self.assertEqual(payload['iopsMaxLimit'], 20000)
    
    def test_modify_qos_bandwidth(self):
        """Test modifying QoS bandwidth limit"""
        result = self.workflow.modify_qos('existing_vvset', bandwidthMaxLimitKiB=409600)
        
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        
        self.assertEqual(payload['bandwidthMaxLimitKiB'], 409600)
    
    def test_modify_qos_all_parameters(self):
        """Test modifying QoS with all parameters"""
        result = self.workflow.modify_qos('existing_vvset', enable=True, iopsMaxLimit=25000, bandwidthMaxLimitKiB=512000)
        
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        
        self.assertTrue(payload['enable'])
        self.assertEqual(payload['iopsMaxLimit'], 25000)
        self.assertEqual(payload['bandwidthMaxLimitKiB'], 512000)
    
    def test_modify_qos_partial_update(self):
        """Test modifying QoS with partial parameters"""
        result = self.workflow.modify_qos('existing_vvset', iopsMaxLimit=30000)
        
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        
        # Only IOPS should be in the payload
        self.assertIn('iopsMaxLimit', payload)
        self.assertNotIn('enable', payload)
        self.assertNotIn('bandwidthMaxLimitKiB', payload)
    
    def test_delete_qos(self):
        """Test deleting QoS rule"""
        result = self.workflow.delete_qos('existing_vvset')
        
        self.assertEqual(result['status'], 'deleted')
        self.assertIn('qos-existing_vvset-uid', self.session_mgr.rest_client.deleted_endpoints[0])
    
    def test_get_qos(self):
        """Test getting QoS rule by target name"""
        result = self.workflow.get_qos('existing_vvset')
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['uid'], 'qos-existing_vvset-uid')
        self.assertEqual(result[0]['targetName'], 'existing_vvset')
        self.assertEqual(result[0]['iopsMaxLimit'], 10000)
        self.assertEqual(result[0]['bandwidthMaxLimitKiB'], 102400)
    
    def test_list_qos(self):
        """Test listing all QoS rules"""
        result = self.workflow.list_qos()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        # Check that our pre-existing QoS rules are there
        target_names = [qos['targetName'] for qos in result]
        self.assertIn('existing_vvset', target_names)
        self.assertIn('vvset2', target_names)
    
    def test_create_qos_with_vvset_target(self):
        """Test creating QoS for volume set target"""
        qos = {
            'iopsMaxLimit': 12000,
            'targetType': 'QOS_TGT_VVSET'
        }
        result = self.workflow.create_qos('prod_vvset', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['targetType'], 'QOS_TGT_VVSET')
        self.assertEqual(payload['targetName'], 'prod_vvset')
    
    def test_create_qos_with_vv_target(self):
        """Test creating QoS for volume target"""
        qos = {
            'iopsMaxLimit': 5000,
            'targetType': 'QOS_TGT_VV'
        }
        result = self.workflow.create_qos('prod_volume', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['targetType'], 'QOS_TGT_VV')
        self.assertEqual(payload['targetName'], 'prod_volume')
    
    def test_create_qos_high_iops_limit(self):
        """Test creating QoS with high IOPS limit"""
        qos = {
            'iopsMaxLimit': 100000,
            'bandwidthMaxLimitKiB': 1048576  # 1 GiB/s in KiB
        }
        result = self.workflow.create_qos('high_perf_vvset', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['iopsMaxLimit'], 100000)
        self.assertEqual(payload['bandwidthMaxLimitKiB'], 1048576)
    
    def test_create_qos_with_kwargs(self):
        """Test creating QoS successfully"""
        qos = {
            'iopsMaxLimit': 8000,
            'targetType': 'QOS_TGT_VVSET'
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        # Should succeed
        self.assertEqual(result['status'], 'created')
    
    def test_create_qos_with_enable_parameter(self):
        """Test creating QoS with enable parameter in qos dict"""
        qos = {
            'iopsMaxLimit': 5000,
            'enable': True
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertTrue(payload['enable'])
    
    def test_create_qos_with_allow_ai_qos_parameter(self):
        """Test creating QoS with allowAIQoS parameter in qos dict"""
        qos = {
            'iopsMaxLimit': 5000,
            'allowAIQoS': False
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertFalse(payload['allowAIQoS'])
    
    def test_create_qos_with_enable_and_allow_ai(self):
        """Test creating QoS with both enable and allowAIQoS"""
        qos = {
            'iopsMaxLimit': 5000,
            'bandwidthMaxLimitKiB': 102400,
            'enable': True,
            'allowAIQoS': True
        }
        result = self.workflow.create_qos('vvset1', qos)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertTrue(payload['enable'])
        self.assertTrue(payload['allowAIQoS'])
        self.assertEqual(payload['iopsMaxLimit'], 5000)
        self.assertEqual(payload['bandwidthMaxLimitKiB'], 102400)
    
    def test_create_qos_invalid_target_name(self):
        """Test creating QoS with invalid target name"""
        qos = {'iopsMaxLimit': 5000}
        with self.assertRaises(Exception):
            self.workflow.create_qos('', qos)
    
    def test_create_qos_no_limits(self):
        """Test creating QoS with no limits should raise error"""
        qos = {}
        with self.assertRaises(Exception):
            self.workflow.create_qos('vvset1', qos)
    
    def test_modify_qos_empty_params(self):
        """Test modifying QoS with empty parameters"""
        result = self.workflow.modify_qos('existing_vvset')
        
        patched = self.session_mgr.rest_client.patched_data[-1]
        payload = patched['payload']
        
        # Payload should be empty
        self.assertEqual(len(payload), 0)


class TestQosValidator(unittest.TestCase):
    """Comprehensive tests for QoS parameter validation"""
    
    def test_validate_qos_allow_ai_qos_valid(self):
        """Test validating allowAIQoS with valid boolean"""
        params = {'allowAIQoS': True, 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_allow_ai_qos_invalid_type(self):
        """Test validating allowAIQoS with invalid type"""
        params = {'allowAIQoS': 'true', 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('allowAIQoS must be a boolean', str(context.exception))
    
    def test_validate_qos_bandwidth_valid(self):
        """Test validating bandwidthMaxLimitKiB with valid int64"""
        params = {'bandwidthMaxLimitKiB': 102400, 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_bandwidth_invalid_type(self):
        """Test validating bandwidthMaxLimitKiB with invalid type"""
        params = {'bandwidthMaxLimitKiB': 'not_a_number', 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('bandwidthMaxLimitKiB must be a number', str(context.exception))
    
    def test_validate_qos_bandwidth_negative(self):
        """Test validating bandwidthMaxLimitKiB with negative value"""
        params = {'bandwidthMaxLimitKiB': -1000, 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('positive', str(context.exception))
    
    def test_validate_qos_enable_valid(self):
        """Test validating enable with valid boolean"""
        params = {'enable': False, 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_enable_invalid_type(self):
        """Test validating enable with invalid type"""
        params = {'enable': 1, 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('enable must be a boolean', str(context.exception))
    
    def test_validate_qos_iops_valid(self):
        """Test validating iopsMaxLimit with valid int64"""
        params = {'iopsMaxLimit': 50000, 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_iops_invalid_type(self):
        """Test validating iopsMaxLimit with invalid type"""
        params = {'iopsMaxLimit': '5000', 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('iopsMaxLimit must be a number', str(context.exception))
    
    def test_validate_qos_iops_negative(self):
        """Test validating iopsMaxLimit with negative value"""
        params = {'iopsMaxLimit': -5000, 'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('positive', str(context.exception))
    
    def test_validate_qos_target_name_valid(self):
        """Test validating targetName with valid string"""
        params = {'targetName': 'my_vvset', 'targetType': 'QOS_TGT_VVSET', 'iopsMaxLimit': 1000}
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_target_name_empty(self):
        """Test validating targetName with empty string"""
        params = {'targetName': '', 'targetType': 'QOS_TGT_VVSET', 'iopsMaxLimit': 1000}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('targetName cannot be empty', str(context.exception))
    
    def test_validate_qos_target_name_invalid_type(self):
        """Test validating targetName with invalid type"""
        params = {'targetName': 123, 'targetType': 'QOS_TGT_VVSET', 'iopsMaxLimit': 1000}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('targetName must be a string', str(context.exception))
    
    def test_validate_qos_target_type_valid_vvset(self):
        """Test validating targetType with valid VVSET type"""
        params = {'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET', 'iopsMaxLimit': 1000}
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_target_type_valid_vv(self):
        """Test validating targetType with valid VV type"""
        params = {'targetName': 'volume1', 'targetType': 'QOS_TGT_VV', 'iopsMaxLimit': 1000}
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_target_type_valid_domain(self):
        """Test validating targetType with valid DOMAIN type"""
        params = {'targetName': 'domain1', 'targetType': 'QOS_TGT_DOMAIN', 'iopsMaxLimit': 1000}
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_target_type_invalid(self):
        """Test validating targetType with invalid value"""
        params = {'targetName': 'vvset1', 'targetType': 'INVALID_TYPE', 'iopsMaxLimit': 1000}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('targetType must be one of', str(context.exception))
    
    def test_validate_qos_target_type_invalid_type(self):
        """Test validating targetType with invalid type"""
        params = {'targetName': 'vvset1', 'targetType': 123, 'iopsMaxLimit': 1000}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('targetType must be a string', str(context.exception))
    
    def test_validate_qos_unknown_parameter(self):
        """Test validating with unknown parameter"""
        params = {'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET', 'unknownParam': 'value', 'iopsMaxLimit': 1000}
        with self.assertRaises(ValueError) as context:
            validate_qos_params(params)
        self.assertIn('Unknown QoS parameter', str(context.exception))
    
    def test_validate_qos_no_limits_specified(self):
        """Test validating without any limits - should pass as limits are optional in validator"""
        params = {'targetName': 'vvset1', 'targetType': 'QOS_TGT_VVSET'}
        # This should pass - validator doesn't require limits, workflow does
        validate_qos_params(params)
    
    def test_validate_qos_with_all_valid_params(self):
        """Test validating with all valid parameters"""
        params = {
            'allowAIQoS': True,
            'bandwidthMaxLimitKiB': 204800,
            'enable': True,
            'iopsMaxLimit': 15000,
            'targetName': 'prod_vvset',
            'targetType': 'QOS_TGT_VVSET'
        }
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_bandwidth_only(self):
        """Test validating with bandwidth limit only"""
        params = {
            'bandwidthMaxLimitKiB': 102400,
            'targetName': 'vvset1',
            'targetType': 'QOS_TGT_VVSET'
        }
        validate_qos_params(params)  # Should not raise
    
    def test_validate_qos_iops_only(self):
        """Test validating with IOPS limit only"""
        params = {
            'iopsMaxLimit': 10000,
            'targetName': 'vvset1',
            'targetType': 'QOS_TGT_VVSET'
        }
        validate_qos_params(params)  # Should not raise


class TestQosWorkflowErrorHandling(unittest.TestCase):
    """Test error handling in QoS workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = QosWorkflow(self.session_mgr, self.task_mgr)
    
    def test_create_qos_with_exception(self):
        """Test create_qos handles exceptions"""
        qos = {'iopsMaxLimit': 5000}
        # Make API call fail
        self.session_mgr.rest_client.post = Mock(side_effect=Exception("API Error"))
        
        with self.assertRaises(Exception) as context:
            self.workflow.create_qos('vvset1', qos)
        self.assertIn("API Error", str(context.exception))
    
    def test_modify_qos_with_exception(self):
        """Test modify_qos handles exceptions"""
        # Make get fail
        self.session_mgr.rest_client.get = Mock(return_value=[])
        
        with self.assertRaises(Exception):
            self.workflow.modify_qos('nonexistent', enable=True)
    
    def test_delete_qos_with_exception(self):
        """Test delete_qos handles exceptions"""
        # Make get fail
        self.session_mgr.rest_client.get = Mock(return_value=[])
        
        with self.assertRaises(Exception):
            self.workflow.delete_qos('nonexistent')
    
    def test_get_qos_returns_empty_list(self):
        """Test get_qos when rule doesn't exist"""
        self.session_mgr.rest_client.get = Mock(return_value=[])
        result = self.workflow.get_qos('nonexistent')
        self.assertEqual(result, [])
    
    def test_list_qos_returns_empty_dict(self):
        """Test list_qos when no rules exist"""
        self.session_mgr.rest_client.get = Mock(return_value={})
        result = self.workflow.list_qos()
        self.assertEqual(result, [])
    
    def test_list_qos_without_members(self):
        """Test list_qos when response has no members key"""
        self.session_mgr.rest_client.get = Mock(return_value={'status': 'ok'})
        result = self.workflow.list_qos()
        self.assertEqual(result, [])
    
    def test_create_qos_invalid_validation(self):
        """Test create_qos with invalid parameters"""
        qos = {'iopsMaxLimit': 'invalid'}
        with self.assertRaises(ValueError):
            self.workflow.create_qos('vvset1', qos)
    
    def test_modify_qos_invalid_validation(self):
        """Test modify_qos with invalid parameters"""
        with self.assertRaises(ValueError):
            self.workflow.modify_qos('vvset1', iopsMaxLimit='invalid')
    
    def test_create_qos_empty_target_name(self):
        """Test create_qos with empty target name"""
        qos = {'iopsMaxLimit': 5000}
        with self.assertRaises(ValueError):
            self.workflow.create_qos('', qos)
    
    def test_modify_qos_no_uid_in_response(self):
        """Test modify_qos when UID is missing"""
        # Return response without UID
        self.session_mgr.rest_client.get = Mock(return_value=[{'name': 'test'}])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.modify_qos('test', enable=True)
        self.assertIn('UID missing', str(context.exception))
    
    def test_delete_qos_no_uid_in_response(self):
        """Test delete_qos when UID is missing"""
        # Return response without UID
        self.session_mgr.rest_client.get = Mock(return_value=[{'name': 'test'}])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.delete_qos('test')
        self.assertIn('UID missing', str(context.exception))
    
    def test_create_qos_already_exists(self):
        """Test create_qos when QoS already exists"""
        # Make get return existing QoS
        self.session_mgr.rest_client.get = Mock(return_value=[{
            'uid': 'existing-qos-uid',
            'targetName': 'vvset1'
        }])
        
        qos = {'iopsMaxLimit': 5000}
        with self.assertRaises(QosAlreadyExists):
            self.workflow.create_qos('vvset1', qos)
    
    def test_modify_qos_does_not_exist(self):
        """Test modify_qos when QoS doesn't exist"""
        # Make get return empty list
        self.session_mgr.rest_client.get = Mock(return_value=[])
        
        with self.assertRaises(QosDoesNotExist):
            self.workflow.modify_qos('nonexistent', enable=True)
    
    def test_delete_qos_does_not_exist(self):
        """Test delete_qos when QoS doesn't exist"""
        # Make get return empty list
        self.session_mgr.rest_client.get = Mock(return_value=[])
        
        with self.assertRaises(QosDoesNotExist):
            self.workflow.delete_qos('nonexistent')
    
    def test_create_qos_returns_exception_response(self):
        """Test create_qos when API returns exception"""
        qos = {'iopsMaxLimit': 5000}
        # Mock _execute_create_qos to return an exception
        with patch.object(self.workflow, '_execute_create_qos', return_value=Exception("API Error")):
            with self.assertRaises(Exception) as context:
                self.workflow.create_qos('vvset1', qos)
            self.assertIn("API Error", str(context.exception))
    
    def test_modify_qos_returns_exception_response(self):
        """Test modify_qos when API returns exception"""
        # Mock _execute_modify_qos to return an exception
        with patch.object(self.workflow, '_execute_modify_qos', return_value=Exception("Modify Error")):
            with self.assertRaises(Exception) as context:
                self.workflow.modify_qos('vvset1', enable=True)
            self.assertIn("Modify Error", str(context.exception))
    
    def test_delete_qos_returns_exception_response(self):
        """Test delete_qos when API returns exception"""
        # Mock _execute_delete_qos to return an exception
        with patch.object(self.workflow, '_execute_delete_qos', return_value=Exception("Delete Error")):
            with self.assertRaises(Exception) as context:
                self.workflow.delete_qos('vvset1')
            self.assertIn("Delete Error", str(context.exception))
    
    def test_get_qos_with_hpe_storage_exception(self):
        """Test get_qos handles HPEStorageException"""
        self.session_mgr.rest_client.get = Mock(side_effect=HPEStorageException("API Error"))
        
        with self.assertRaises(HPEStorageException) as context:
            self.workflow.get_qos('vvset1')
        self.assertIn("API Error", str(context.exception))
    
    def test_list_qos_with_hpe_storage_exception(self):
        """Test list_qos handles HPEStorageException"""
        self.session_mgr.rest_client.get = Mock(side_effect=HPEStorageException("API Error"))
        
        with self.assertRaises(HPEStorageException) as context:
            self.workflow.list_qos()
        self.assertIn("API Error", str(context.exception))


class TestQosWorkflowIntegration(unittest.TestCase):
    """Integration tests for QoS workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = QosWorkflow(self.session_mgr, self.task_mgr)
    
    def test_qos_lifecycle(self):
        """Test complete QoS lifecycle: create, get, modify, delete"""
        # Create QoS rule
        qos = {
            'iopsMaxLimit': 10000,
            'bandwidthMaxLimitKiB': 102400,
            'targetType': 'QOS_TGT_VVSET'
        }
        create_result = self.workflow.create_qos('test_vvset', qos)
        self.assertEqual(create_result['status'], 'created')
        
        # Get QoS rule
        get_result = self.workflow.get_qos('test_vvset')
        self.assertEqual(get_result[0]['targetName'], 'test_vvset')
        
        # Modify QoS rule
        modify_result = self.workflow.modify_qos('test_vvset', iopsMaxLimit=15000, enable=True)
        self.assertEqual(modify_result['status'], 'modified')
        
        # Delete QoS rule
        delete_result = self.workflow.delete_qos('test_vvset')
        self.assertEqual(delete_result['status'], 'deleted')
    
    def test_create_multiple_qos_rules(self):
        """Test creating multiple QoS rules"""
        # Create first rule
        qos1 = {'iopsMaxLimit': 5000, 'targetType': 'QOS_TGT_VVSET'}
        result1 = self.workflow.create_qos('vvset1', qos1)
        self.assertEqual(result1['status'], 'created')
        
        # Create second rule
        qos2 = {'iopsMaxLimit': 10000, 'targetType': 'QOS_TGT_VVSET'}
        result2 = self.workflow.create_qos('vvset2', qos2)
        self.assertEqual(result2['status'], 'created')
        
        # List all QoS rules
        all_qos = self.workflow.list_qos()
        self.assertGreaterEqual(len(all_qos), 2)
    
    def test_modify_qos_incrementally(self):
        """Test modifying QoS rule incrementally"""
        # Create QoS rule
        qos = {'iopsMaxLimit': 5000}
        self.workflow.create_qos('vvset1', qos)
        
        # Modify IOPS
        self.workflow.modify_qos('vvset1', iopsMaxLimit=8000)
        
        # Modify bandwidth
        self.workflow.modify_qos('vvset1', bandwidthMaxLimitKiB=102400)
        
        # Enable the rule
        result = self.workflow.modify_qos('vvset1', enable=True)
        self.assertEqual(result['status'], 'modified')
    
    def test_qos_for_different_target_types(self):
        """Test creating QoS for different target types"""
        # QoS for volume set
        qos_vvset = {'iopsMaxLimit': 10000, 'targetType': 'QOS_TGT_VVSET'}
        result1 = self.workflow.create_qos('prod_vvset', qos_vvset)
        self.assertEqual(result1['targetName'], 'prod_vvset')
        
        # QoS for single volume
        qos_vv = {'iopsMaxLimit': 5000, 'targetType': 'QOS_TGT_VV'}
        result2 = self.workflow.create_qos('prod_volume', qos_vv)
        self.assertEqual(result2['targetName'], 'prod_volume')
    
    def test_create_qos_without_limits_should_fail(self):
        """Test creating QoS without any limits raises ValueError"""
        qos = {'targetType': 'QOS_TGT_VVSET'}  # No iopsMaxLimit or bandwidthMaxLimitKiB
        with self.assertRaises(ValueError) as context:
            self.workflow.create_qos('vvset_no_limits', qos)
        self.assertIn('At least one of iopsMaxLimit or bandwidthMaxLimitKiB must be provided', str(context.exception))
    
    def test_create_qos_with_only_iops_limit(self):
        """Test creating QoS with only iopsMaxLimit (no bandwidth)"""
        qos = {'iopsMaxLimit': 5000}  # No bandwidthMaxLimitKiB
        result = self.workflow.create_qos('vvset_iops_only', qos)
        self.assertEqual(result['status'], 'created')
        self.assertEqual(result['targetName'], 'vvset_iops_only')
        # Verify payload has iopsMaxLimit but not bandwidthMaxLimitKiB
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        self.assertEqual(posted['iopsMaxLimit'], 5000)
        self.assertNotIn('bandwidthMaxLimitKiB', posted)
    
    def test_create_qos_with_only_bandwidth_limit(self):
        """Test creating QoS with only bandwidthMaxLimitKiB (no IOPS)"""
        qos = {'bandwidthMaxLimitKiB': 51200}  # No iopsMaxLimit
        result = self.workflow.create_qos('vvset_bw_only', qos)
        self.assertEqual(result['status'], 'created')
        self.assertEqual(result['targetName'], 'vvset_bw_only')
        # Verify payload has bandwidthMaxLimitKiB but not iopsMaxLimit
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        self.assertEqual(posted['bandwidthMaxLimitKiB'], 51200)
        self.assertNotIn('iopsMaxLimit', posted)
    
    def test_create_qos_with_enable_true(self):
        """Test creating QoS with enable=True"""
        qos = {'iopsMaxLimit': 5000, 'enable': True}
        result = self.workflow.create_qos('vvset_enabled', qos)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        self.assertEqual(posted['enable'], True)
    
    def test_create_qos_with_enable_false(self):
        """Test creating QoS with enable=False"""
        qos = {'iopsMaxLimit': 5000, 'enable': False}
        result = self.workflow.create_qos('vvset_disabled', qos)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        self.assertEqual(posted['enable'], False)
    
    def test_create_qos_with_allow_ai_qos_true(self):
        """Test creating QoS with allowAIQoS=True"""
        qos = {'iopsMaxLimit': 5000, 'allowAIQoS': True}
        result = self.workflow.create_qos('vvset_ai_allowed', qos)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        self.assertEqual(posted['allowAIQoS'], True)
    
    def test_create_qos_with_allow_ai_qos_false(self):
        """Test creating QoS with allowAIQoS=False"""
        qos = {'iopsMaxLimit': 5000, 'allowAIQoS': False}
        result = self.workflow.create_qos('vvset_ai_denied', qos)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        self.assertEqual(posted['allowAIQoS'], False)
    
    def test_create_qos_with_explicit_vv_target_type(self):
        """Test creating QoS with explicit QOS_TGT_VV target type"""
        qos = {'iopsMaxLimit': 3000, 'targetType': 'QOS_TGT_VV'}
        result = self.workflow.create_qos('single_volume', qos)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        self.assertEqual(posted['targetType'], 'QOS_TGT_VV')
    
    def test_create_qos_with_default_target_type(self):
        """Test creating QoS uses default targetType if not provided"""
        qos = {'iopsMaxLimit': 3000}
        result = self.workflow.create_qos('default_target', qos)
        posted = self.session_mgr.rest_client.posted_data[-1]['payload']
        # Default should be QOS_TGT_VVSET per code at line 48
        self.assertEqual(posted['targetType'], 'QOS_TGT_VVSET')
    
    def test_modify_qos_with_missing_uid(self):
        """Test modifying QoS when response has no UID raises ValueError"""
        # Add test_qos to existing so it "exists" but mock get to return no UID
        self.session_mgr.rest_client.existing_qos.add('test_qos')
        # Mock get to return response without uid
        original_get = self.session_mgr.rest_client.get
        self.session_mgr.rest_client.get = Mock(return_value=[{'targetName': 'test_qos'}])
        
        with self.assertRaises(ValueError) as context:
            self.workflow.modify_qos('test_qos', iopsMaxLimit=8000)
        self.assertIn('QoS UID missing', str(context.exception))
        
        # Restore
        self.session_mgr.rest_client.get = original_get
    
    def test_execute_create_qos_exception_handling(self):
        """Test that _execute_create_qos returns Exception on POST failure"""
        # Mock POST to raise exception
        self.session_mgr.rest_client.post = Mock(side_effect=Exception("API Error"))
        
        qos = {'iopsMaxLimit': 5000}
        result = self.workflow._execute_create_qos('error_vvset', qos)
        
        # Should return the exception, not raise it
        self.assertIsInstance(result, Exception)
        self.assertIn('API Error', str(result))
    
    def test_execute_modify_qos_exception_handling(self):
        """Test that _execute_modify_qos returns Exception on PATCH failure"""
        # Add existing_vvset so the check passes, then make PATCH fail
        self.session_mgr.rest_client.existing_qos.add('vvset1')
        # Mock PATCH to raise exception
        self.session_mgr.rest_client.patch = Mock(side_effect=Exception("PATCH Error"))
        
        result = self.workflow._execute_modify_qos('vvset1', iopsMaxLimit=8000)
        
        # Should return the exception, not raise it
        self.assertIsInstance(result, Exception)
        self.assertIn('PATCH Error', str(result))
    
    def test_create_qos_with_string_limits_converts_to_int(self):
        """Test that string limits cause validation error (validator expects numbers)"""
        qos = {'iopsMaxLimit': '7500', 'bandwidthMaxLimitKiB': '102400'}
        # Strings should be rejected by validator
        with self.assertRaises(ValueError) as context:
            self.workflow.create_qos('vvset_string_limits', qos)
        self.assertIn('must be a number', str(context.exception))


if __name__ == '__main__':
    unittest.main()
