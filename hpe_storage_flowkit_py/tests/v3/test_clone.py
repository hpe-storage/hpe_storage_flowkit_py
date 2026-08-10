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

from hpe_storage_flowkit_py.v3.src.workflows.clone import CloneWorkflow
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, VolumeDoesNotExist
from hpe_storage_flowkit_py.v3.src.validators.clone_validator import validate_clone_params, validate_resync_physical_copy


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
    
    def get_all_tasks(self):
        """Return mock tasks for offline/online physical copy tests"""
        return {
            'members': {
                'task-123': {
                    'status': 'TASK_ACTIVE',
                    'detailsMap': {
                        'detail-1': {
                            'message': {
                                'default': 'createvvcopy offline_source offline_dest'
                            }
                        }
                    }
                },
                'task-456': {
                    'status': 'TASK_ACTIVE',
                    'detailsMap': {
                        'detail-1': {
                            'message': {
                                'default': 'createvvcopy -online source_vol clone_vol'
                            }
                        }
                    }
                }
            }
        }


class MockRestClient:
    """Mock REST client for testing"""
    def __init__(self):
        self.responses = {}
        self.posted_data = []
        self.tasks = {}
        self.existing_volumes = {'offline_source', 'offline_dest', 'clone_vol', 'dest_vol', 'test_vol'}
        
    def post(self, endpoint, payload):
        self.posted_data.append({'endpoint': endpoint, 'payload': payload})
        
        if 'CREATE_VVCOPY' in str(payload):
            dest_name = payload.get('parameters', {}).get('destination')
            if dest_name:
                self.existing_volumes.add(dest_name)
            return {
                'status': 'created',
                'taskUid': 'task-12345',
                'message': 'Volume copy initiated'
            }
        elif 'HALT_VVCOPY' in str(payload):
            return {'status': 'halted', 'message': 'Volume copy halted'}
        elif 'RESYNC_VVCOPY' in str(payload):
            return {'status': 'resynced', 'message': 'Volume copy resynced'}
        
        return {'status': 'success'}
    
    def get(self, endpoint, headers=None):
        if '/volumes?name=' in endpoint:
            name = endpoint.split('=')[1]
            if name in self.existing_volumes or name == 'source_vol':
                return [{'uid': f'volume-{name}-uid', 'name': name, 'type': 'VVTYPE_BASE'}]
            return []
        elif endpoint == '/tasks':
            return {
                'members': {
                    'task-1': {
                        'status': 'STATE_FINISHED',
                        'detailsMap': {
                            'detail-1': {
                                'message': {
                                    'args': ['createvvcopy -online -tpvv -p source_vol clone_vol']
                                }
                            }
                        }
                    },
                    'task-2': {
                        'status': 'STATE_FINISHED',
                        'detailsMap': {
                            'detail-1': {
                                'message': {
                                    'args': ['createvvcopy -tpvv -p offline_source offline_dest']
                                }
                            }
                        }
                    }
                }
            }
        return {}


class TestCloneWorkflow(unittest.TestCase):
    """Comprehensive unit tests for Clone workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = CloneWorkflow(self.session_mgr, self.task_mgr)
    
    def test_copy_volume_online_basic(self):
        """Test online volume copy with required parameters"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', online=True)
        
        self.assertEqual(result['status'], 'created')
        self.assertIn('taskUid', result)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['action'], 'CREATE_VVCOPY')
        self.assertEqual(payload['parameters']['destination'], 'dest_vol')
        self.assertEqual(payload['parameters']['destinationCpg'], 'cpg1')
        self.assertTrue(payload['parameters']['online'])
    
    def test_copy_volume_offline(self):
        """Test offline volume copy"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', online=False)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['action'], 'CREATE_VVCOPY')
        self.assertFalse(payload['parameters']['online'])
        # destinationCpg should not be mandatory for offline
        self.assertNotIn('destinationCpg', payload['parameters'])
    
    def test_copy_volume_offline_with_cpg(self):
        """Test offline volume copy with optional CPG"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', online=False)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertFalse(payload['parameters']['online'])
        self.assertEqual(payload['parameters']['destinationCpg'], 'cpg1')
    
    def test_copy_volume_with_priority_string(self):
        """Test volume copy with priority as string"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', priority='PRIORITYTYPE_HIGH', online=True)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['parameters']['priority'], 'PRIORITYTYPE_HIGH')
    
    def test_copy_volume_with_priority_medium(self):
        """Test volume copy with medium priority"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', priority='PRIORITYTYPE_MED', online=True)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['parameters']['priority'], 'PRIORITYTYPE_MED')
    
    def test_copy_volume_with_priority_low(self):
        """Test volume copy with low priority"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', priority='PRIORITYTYPE_LOW', online=True)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['parameters']['priority'], 'PRIORITYTYPE_LOW')
    
    def test_copy_volume_with_priority_enum(self):
        """Test volume copy with priority as enum value"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', priority='PRIORITYTYPE_HIGH')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['parameters']['priority'], 'PRIORITYTYPE_HIGH')
    
    def test_copy_volume_with_skip_zero(self):
        """Test volume copy with skipZero option"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', skipZero=True)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertTrue(payload['parameters']['skipZero'])
    
    def test_copy_volume_with_reduce(self):
        """Test volume copy with reduce option"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', reduce=True)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertTrue(payload['parameters']['reduce'])
    
    def test_copy_volume_with_enable_resync(self):
        """Test volume copy with enableResync option"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', enableResync=True)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertTrue(payload['parameters']['enableResync'])
    
    def test_copy_volume_with_appset_parameters(self):
        """Test volume copy with application set parameters"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', online=True,
                                          addToSet='app_set_1',
                                          appSetType='APPSET_USER',
                                          appSetBusinessUnit='Finance',
                                          appSetComments='Test clone',
                                          appSetImportance='APPSET_IMPORTANCE_MEDIUM')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['parameters']['addToSet'], 'app_set_1')
        self.assertEqual(payload['parameters']['appSetType'], 'APPSET_USER')
        self.assertEqual(payload['parameters']['appSetBusinessUnit'], 'Finance')
        self.assertEqual(payload['parameters']['appSetComments'], 'Test clone')
        self.assertEqual(payload['parameters']['appSetImportance'], 'APPSET_IMPORTANCE_MEDIUM')
    
    def test_copy_volume_with_expiration_and_retention(self):
        """Test volume copy with expiration and retention"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', online=True,
                                          expireSecs=86400,  # 1 day
                                          retainSecs=3600)   # 1 hour
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['parameters']['expireSecs'], 86400)
        self.assertEqual(payload['parameters']['retainSecs'], 3600)
    
    def test_copy_volume_with_all_parameters(self):
        """Test volume copy with all possible parameters"""
        result = self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1',
                                          online=True,
                                          priority='PRIORITYTYPE_HIGH',
                                          reduce=True,
                                          skipZero=True,
                                          enableResync=True,
                                          addToSet='app_set',
                                          appSetType='APPSET_USER',
                                          expireSecs=86400,
                                          retainSecs=3600)
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['action'], 'CREATE_VVCOPY')
        self.assertEqual(payload['parameters']['destination'], 'dest_vol')
        self.assertEqual(payload['parameters']['destinationCpg'], 'cpg1')
        self.assertTrue(payload['parameters']['online'])
        self.assertEqual(payload['parameters']['priority'], 'PRIORITYTYPE_HIGH')
        self.assertTrue(payload['parameters']['reduce'])
        self.assertTrue(payload['parameters']['skipZero'])
        self.assertTrue(payload['parameters']['enableResync'])
    
    def test_copy_volume_online_without_cpg_raises_error(self):
        """Test that online copy without CPG raises error"""
        optional = {'online': True}
        with self.assertRaises(ValueError):
            self.workflow.copy_volume('source_vol', 'dest_vol', optional=optional)
    
    def test_stop_physical_copy(self):
        """Test stopping physical copy"""
        result = self.workflow.stop_physical_copy('dest_vol')
        
        self.assertEqual(result['status'], 'halted')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['action'], 'HALT_VVCOPY')
        self.assertIn('/volumes/volume-dest_vol-uid', posted['endpoint'])
    
    def test_resync_physical_copy_without_priority(self):
        """Test resyncing physical copy without priority"""
        result = self.workflow.resync_physical_copy('dest_vol')
        
        self.assertEqual(result['status'], 'resynced')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['action'], 'RESYNC_VVCOPY')
        self.assertNotIn('priority', payload['parameters'])
    
    def test_resync_physical_copy_with_priority(self):
        """Test resyncing physical copy with priority"""
        result = self.workflow.resync_physical_copy('dest_vol', priority='PRIORITYTYPE_HIGH')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['action'], 'RESYNC_VVCOPY')
        self.assertEqual(payload['parameters']['priority'], 'PRIORITYTYPE_HIGH')
    
    def test_get_volume_uid(self):
        """Test getting volume info (UID)"""
        result = self.workflow.get_volume_info('test_vol')
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['uid'], 'volume-test_vol-uid')
        self.assertEqual(result[0]['name'], 'test_vol')
    
    def test_copy_volume_invalid_source(self):
        """Test copy volume with invalid source name"""
        with self.assertRaises(Exception):
            self.workflow.copy_volume('', 'dest_vol', destinationCpg='cpg1')
    
    def test_copy_volume_invalid_destination(self):
        """Test copy volume with invalid destination name"""
        with self.assertRaises(Exception):
            self.workflow.copy_volume('source_vol', '', destinationCpg='cpg1')
    
    def test_stop_physical_copy_invalid_name(self):
        """Test stop physical copy with invalid name"""
        with self.assertRaises(Exception):
            self.workflow.stop_physical_copy('')
    
    def test_resync_physical_copy_invalid_name(self):
        """Test resync physical copy with invalid name"""
        with self.assertRaises(Exception):
            self.workflow.resync_physical_copy('')    
    def test_copy_volume_source_not_found(self):
        """Test copy volume when source doesn't exist"""
        # Mock get_volume_info to return empty list
        original_get = self.workflow.volume_workflow.get_volume_info
        self.workflow.volume_workflow.get_volume_info = lambda name: []
        
        with self.assertRaises(VolumeDoesNotExist):
            self.workflow.copy_volume('nonexistent', 'dest_vol', destinationCpg='cpg1', online=True)
        
        # Restore
        self.workflow.volume_workflow.get_volume_info = original_get
    
    def test_copy_volume_source_missing_uid(self):
        """Test copy volume when source UID is missing"""
        # Mock get_volume_info to return volume without UID
        original_get = self.workflow.get_volume_info
        self.workflow.get_volume_info = lambda volume_name: [{'name': volume_name}]
        
        with self.assertRaises(ValueError) as context:
            self.workflow.copy_volume('source_vol', 'dest_vol', destinationCpg='cpg1', online=True)
        
        self.assertIn('UID missing', str(context.exception))
        
        # Restore
        self.workflow.get_volume_info = original_get
    
    def test_stop_physical_copy_volume_not_found(self):
        """Test stop physical copy when volume doesn't exist"""
        # Mock get_volume_info to return empty list
        original_get = self.workflow.volume_workflow.get_volume_info
        self.workflow.volume_workflow.get_volume_info = lambda name: []
        
        with self.assertRaises(VolumeDoesNotExist):
            self.workflow.stop_physical_copy('nonexistent_vol')
        
        # Restore
        self.workflow.volume_workflow.get_volume_info = original_get
    
    def test_stop_physical_copy_missing_uid(self):
        """Test stop physical copy when UID is missing"""
        # Mock get_volume_info to return volume without UID
        original_get = self.workflow.get_volume_info
        self.workflow.get_volume_info = lambda volume_name: [{'name': volume_name}]
        
        with self.assertRaises(ValueError) as context:
            self.workflow.stop_physical_copy('dest_vol')
        
        self.assertIn('UID missing', str(context.exception))
        
        # Restore
        self.workflow.get_volume_info = original_get
    
    def test_resync_physical_copy_volume_not_found(self):
        """Test resync physical copy when volume doesn't exist"""
        # Mock get_volume_info to return empty list
        original_get = self.workflow.volume_workflow.get_volume_info
        self.workflow.volume_workflow.get_volume_info = lambda name: []
        
        with self.assertRaises(VolumeDoesNotExist):
            self.workflow.resync_physical_copy('nonexistent_vol')
        
        # Restore
        self.workflow.volume_workflow.get_volume_info = original_get
    
    def test_resync_physical_copy_missing_uid(self):
        """Test resync physical copy when UID is missing"""
        # Mock get_volume_info to return volume without UID
        original_get = self.workflow.get_volume_info
        self.workflow.get_volume_info = lambda volume_name: [{'name': volume_name}]
        
        with self.assertRaises(ValueError) as context:
            self.workflow.resync_physical_copy('dest_vol')
        
        self.assertIn('UID missing', str(context.exception))
        
        # Restore
        self.workflow.volume_workflow.get_volume_info = original_get
    
    def test_copy_volume_with_time_conversion(self):
        """Test copy volume with time unit conversion"""
        result = self.workflow.copy_volume(
            'source_vol', 'dest_vol',
            destinationCpg='cpg1',
            online=True,
            expiration_time=7, expiration_unit='days',
            retention_time=1, retention_unit='days'
        )
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertEqual(payload['parameters']['expireSecs'], 604800)  # 7 days
        self.assertEqual(payload['parameters']['retainSecs'], 86400)   # 1 day
    
    def test_copy_volume_preprocess_with_none_times(self):
        """Test copy volume preprocessing with None time values"""
        result = self.workflow._preprocess_copy_volume({
            'expiration_time': None,
            'retention_time': None
        })
        
        self.assertNotIn('expireSecs', result)
        self.assertNotIn('retainSecs', result)
    
    def test_copy_volume_preprocess_no_params(self):
        """Test copy volume preprocessing with None params"""
        result = self.workflow._preprocess_copy_volume(None)
        
        self.assertEqual(result, {})
    
    def test_offline_physical_copy_exist(self):
        """Test checking if offline physical copy exists"""
        result = self.workflow.offline_physical_copy_exist('offline_source', 'offline_dest')
        
        # Should check for existence of source, dest, and task
        self.assertIsInstance(result, bool)
    
    def test_online_physical_copy_exist(self):
        """Test checking if online physical copy exists"""
        result = self.workflow.online_physical_copy_exist('source_vol', 'clone_vol')
        
        # Should check for existence of source, dest, and task with -online
        self.assertIsInstance(result, bool)

class TestCloneWorkflowIntegration(unittest.TestCase):
    """Integration tests for Clone workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.task_mgr = MockTaskManager(self.session_mgr)
        self.workflow = CloneWorkflow(self.session_mgr, self.task_mgr)
    
    def test_complete_clone_lifecycle(self):
        """Test complete clone lifecycle: create, stop, resync"""
        # Create online clone
        create_result = self.workflow.copy_volume('source_vol', 'clone_vol', destinationCpg='cpg1', online=True)
        self.assertEqual(create_result['status'], 'created')
        
        # Stop the clone
        stop_result = self.workflow.stop_physical_copy('clone_vol')
        self.assertEqual(stop_result['status'], 'halted')
        
        # Resync the clone
        resync_result = self.workflow.resync_physical_copy('clone_vol')
        self.assertEqual(resync_result['status'], 'resynced')
    
    def test_offline_clone_workflow(self):
        """Test offline clone workflow"""
        result = self.workflow.copy_volume('source_vol', 'offline_clone',
                                          online=False,
                                          priority='PRIORITYTYPE_HIGH',
                                          skipZero=True)
        
        self.assertEqual(result['status'], 'created')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertFalse(payload['parameters']['online'])
        self.assertEqual(payload['parameters']['priority'], 'PRIORITYTYPE_HIGH')
        self.assertTrue(payload['parameters']['skipZero'])
    
    def test_online_clone_with_resync_enabled(self):
        """Test online clone with resync enabled"""
        result = self.workflow.copy_volume('source_vol', 'resync_clone', destinationCpg='cpg1',
                                          online=True,
                                          enableResync=True,
                                          priority='PRIORITYTYPE_MED')
        
        posted = self.session_mgr.rest_client.posted_data[-1]
        payload = posted['payload']
        
        self.assertTrue(payload['parameters']['online'])
        self.assertTrue(payload['parameters']['enableResync'])
        self.assertEqual(payload['parameters']['priority'], 'PRIORITYTYPE_MED')


class TestCloneValidator(unittest.TestCase):
    """Comprehensive tests for clone validator"""
    
    def test_validate_clone_params_src_name_type(self):
        """Test clone validation checks src_name type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params(123, 'dest', {'destination': 'dest'})
        self.assertIn('non-empty string', str(context.exception))
    
    def test_validate_clone_params_src_name_empty(self):
        """Test clone validation checks src_name not empty"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('  ', 'dest', {'destination': 'dest'})
        self.assertIn('non-empty string', str(context.exception))
    
    def test_validate_clone_params_dest_name_type(self):
        """Test clone validation checks dest_name type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 123, {'destination': 'dest'})
        self.assertIn('non-empty string', str(context.exception))
    
    def test_validate_clone_params_dest_name_empty(self):
        """Test clone validation checks dest_name not empty"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', '  ', {'destination': 'dest'})
        self.assertIn('non-empty string', str(context.exception))
    
    def test_validate_clone_params_dict_type(self):
        """Test clone validation checks params is dict"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', 'not_a_dict')
        self.assertIn('must be a dictionary', str(context.exception))
    
    def test_validate_clone_params_unknown_param(self):
        """Test clone validation rejects unknown parameters"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'invalidParam': 'value'})
        self.assertIn('Unknown clone parameter', str(context.exception))
    
    def test_validate_clone_params_destination_type(self):
        """Test clone validation checks destination type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 123})
        self.assertIn('non-empty string', str(context.exception))
    
    def test_validate_clone_params_destination_empty(self):
        """Test clone validation checks destination not empty"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': '  '})
        self.assertIn('non-empty string', str(context.exception))
    
    def test_validate_clone_params_destination_set_prefix_only(self):
        """Test clone validation checks volume set name has content"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'set:'})
        self.assertIn('must have content after', str(context.exception))
    
    def test_validate_clone_params_destinationCpg_type(self):
        """Test clone validation checks destinationCpg type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'destinationCpg': 123})
        self.assertIn('non-empty string', str(context.exception))
    
    def test_validate_clone_params_destinationCpg_empty(self):
        """Test clone validation checks destinationCpg not empty"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'destinationCpg': '  '})
        self.assertIn('non-empty string', str(context.exception))
    
    def test_validate_clone_params_online_type(self):
        """Test clone validation checks online type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'online': 'yes'})
        self.assertIn('must be a boolean', str(context.exception))
    
    def test_validate_clone_params_online_requires_cpg(self):
        """Test clone validation checks online requires destinationCpg"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'online': True})
        self.assertIn('mandatory when online=True', str(context.exception))
    
    def test_validate_clone_params_addToSet_type(self):
        """Test clone validation checks addToSet type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'online': True, 'destinationCpg': 'cpg1', 'addToSet': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_clone_params_addToSet_empty(self):
        """Test clone validation checks addToSet not empty"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'online': True, 'destinationCpg': 'cpg1', 'addToSet': ''})
        self.assertIn('cannot be empty', str(context.exception))
    
    def test_validate_clone_params_addToSet_requires_online(self):
        """Test clone validation checks addToSet requires online"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'addToSet': 'app_set'})
        self.assertIn('can only be used with online', str(context.exception))
    
    def test_validate_clone_params_appSetBusinessUnit_type(self):
        """Test clone validation checks appSetBusinessUnit type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'appSetBusinessUnit': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_clone_params_appSetComments_type(self):
        """Test clone validation checks appSetComments type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'appSetComments': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_clone_params_appSetExcludeAIQoS_type(self):
        """Test clone validation checks appSetExcludeAIQoS type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'appSetExcludeAIQoS': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_clone_params_appSetExcludeAIQoS_invalid_value(self):
        """Test clone validation checks appSetExcludeAIQoS value"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'appSetExcludeAIQoS': 'invalid'})
        self.assertIn('must be one of', str(context.exception))
    
    def test_validate_clone_params_appSetImportance_type(self):
        """Test clone validation checks appSetImportance type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'appSetImportance': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_clone_params_appSetType_type(self):
        """Test clone validation checks appSetType type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'appSetType': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_clone_params_bulkvv_type(self):
        """Test clone validation checks bulkvv type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'bulkvv': 'yes'})
        self.assertIn('must be a boolean', str(context.exception))
    
    def test_validate_clone_params_enableResync_type(self):
        """Test clone validation checks enableResync type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'enableResync': 'yes'})
        self.assertIn('must be a boolean', str(context.exception))
    
    def test_validate_clone_params_expireSecs_type(self):
        """Test clone validation checks expireSecs type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'expireSecs': 'invalid'})
        self.assertIn('must be a number', str(context.exception))
    
    def test_validate_clone_params_expireSecs_negative(self):
        """Test clone validation checks expireSecs is non-negative"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'expireSecs': -1})
        self.assertIn('non-negative', str(context.exception))
    
    def test_validate_clone_params_priority_type(self):
        """Test clone validation checks priority type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'priority': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_clone_params_priority_invalid_value(self):
        """Test clone validation checks priority value"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'priority': 'INVALID_PRIORITY'})
        self.assertIn('PRIORITYTYPE_', str(context.exception))
    
    def test_validate_clone_params_reduce_type(self):
        """Test clone validation checks reduce type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'reduce': 'yes'})
        self.assertIn('must be a boolean', str(context.exception))
    
    def test_validate_clone_params_retainSecs_type(self):
        """Test clone validation checks retainSecs type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'retainSecs': 'invalid'})
        self.assertIn('must be a number', str(context.exception))
    
    def test_validate_clone_params_retainSecs_negative(self):
        """Test clone validation checks retainSecs is non-negative"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'retainSecs': -1})
        self.assertIn('non-negative', str(context.exception))
    
    def test_validate_clone_params_selectionType_type(self):
        """Test clone validation checks selectionType type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'selectionType': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_clone_params_selectionType_invalid_value(self):
        """Test clone validation checks selectionType value"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'selectionType': 'INVALID_TYPE'})
        self.assertIn('PARENTVV_', str(context.exception))
    
    def test_validate_clone_params_skipZero_type(self):
        """Test clone validation checks skipZero type"""
        with self.assertRaises(ValueError) as context:
            validate_clone_params('src', 'dest', {'destination': 'dest', 'skipZero': 'yes'})
        self.assertIn('must be a boolean', str(context.exception))
    
    def test_validate_resync_physical_copy_volume_name_type(self):
        """Test resync validation checks volume name type"""
        with self.assertRaises(ValueError) as context:
            validate_resync_physical_copy(123, {})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_resync_physical_copy_volume_name_empty(self):
        """Test resync validation checks volume name not empty"""
        with self.assertRaises(ValueError) as context:
            validate_resync_physical_copy('  ', {})
        self.assertIn('cannot be empty', str(context.exception))
    
    def test_validate_resync_physical_copy_dict_type(self):
        """Test resync validation checks params is dict"""
        with self.assertRaises(ValueError) as context:
            validate_resync_physical_copy('vol1', 'not_a_dict')
        self.assertIn('must be a dictionary', str(context.exception))
    
    def test_validate_resync_physical_copy_unknown_param(self):
        """Test resync validation rejects unknown parameters"""
        with self.assertRaises(ValueError) as context:
            validate_resync_physical_copy('vol1', {'invalidParam': 'value'})
        self.assertIn('Unknown resync parameter', str(context.exception))
    
    def test_validate_resync_physical_copy_priority_type(self):
        """Test resync validation checks priority type"""
        with self.assertRaises(ValueError) as context:
            validate_resync_physical_copy('vol1', {'priority': 123})
        self.assertIn('must be a string', str(context.exception))
    
    def test_validate_resync_physical_copy_priority_invalid_value(self):
        """Test resync validation checks priority value"""
        with self.assertRaises(ValueError) as context:
            validate_resync_physical_copy('vol1', {'priority': 'INVALID_PRIORITY'})
        self.assertIn('PRIORITYTYPE_', str(context.exception))


if __name__ == '__main__':
    unittest.main()
