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
"""
Comprehensive unit tests for ansible_service.py module.
Tests cover all methods in AnsibleClient class with various scenarios
to achieve >90% code coverage.

This single file contains all test cases for:
- Client initialization and configuration
- VolumeSet, CPG, Volume, Snapshot operations
- QoS, Task, Clone, HostSet operations
- NTP/DateTime, DNS/Network configuration
- Schedule and User management
- Host operations and CHAP configuration
- VLUN export/unexport operations
- Remote Copy Group operations and management
- Logout functionality
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys

# Mock all external dependencies before importing the module under test
# Add parent modules first
sys.modules['hpe_storage_flowkit_py.v3.src.core'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.core'] = MagicMock()

# Create exception classes at module level BEFORE importing ansible_service
# Use types.ModuleType to create proper mock modules
from types import ModuleType

# Define actual exception classes
class VolumeSetAlreadyExists(Exception):
    pass

class VolumeSetDoesNotExist(Exception):
    pass

class VolumeSetMembersAlreadyPresent(Exception):
    pass

class VolumeSetMembersAlreadyRemoved(Exception):
    pass

class CpgAlreadyExists(Exception):
    pass

class CpgDoesNotExist(Exception):
    pass

class VolumeAlreadyExists(Exception):
    pass

class VolumeDoesNotExist(Exception):
    pass

class QosAlreadyExists(Exception):
    pass

class QosDoesNotExist(Exception):
    pass

class HostSetAlreadyExists(Exception):
    pass

class HostSetDoesNotExist(Exception):
    pass

class HostSetMembersAlreadyPresent(Exception):
    pass

class HostSetMembersAlreadyRemoved(Exception):
    pass

class SystemDoesNotExist(Exception):
    pass

class ScheduleAlreadyExists(Exception):
    pass

class ScheduleDoesNotExist(Exception):
    pass

class UserDoesNotExist(Exception):
    pass

class UserAlreadyExists(Exception):
    pass

class HTTPNotFound(Exception):
    pass

class SSHException(Exception):
    pass

# Create module-type objects
mock_exceptions_v3 = ModuleType('mock_exceptions_v3')
mock_exceptions_v3.VolumeSetAlreadyExists = VolumeSetAlreadyExists
mock_exceptions_v3.VolumeSetDoesNotExist = VolumeSetDoesNotExist
mock_exceptions_v3.VolumeSetMembersAlreadyPresent = VolumeSetMembersAlreadyPresent
mock_exceptions_v3.VolumeSetMembersAlreadyRemoved = VolumeSetMembersAlreadyRemoved
mock_exceptions_v3.CpgAlreadyExists = CpgAlreadyExists
mock_exceptions_v3.CpgDoesNotExist = CpgDoesNotExist
mock_exceptions_v3.VolumeAlreadyExists = VolumeAlreadyExists
mock_exceptions_v3.VolumeDoesNotExist = VolumeDoesNotExist
mock_exceptions_v3.QosAlreadyExists = QosAlreadyExists
mock_exceptions_v3.QosDoesNotExist = QosDoesNotExist
mock_exceptions_v3.HostSetAlreadyExists = HostSetAlreadyExists
mock_exceptions_v3.HostSetDoesNotExist = HostSetDoesNotExist
mock_exceptions_v3.HostSetMembersAlreadyPresent = HostSetMembersAlreadyPresent
mock_exceptions_v3.HostSetMembersAlreadyRemoved = HostSetMembersAlreadyRemoved
mock_exceptions_v3.SystemDoesNotExist = SystemDoesNotExist
mock_exceptions_v3.ScheduleAlreadyExists = ScheduleAlreadyExists
mock_exceptions_v3.ScheduleDoesNotExist = ScheduleDoesNotExist
mock_exceptions_v3.UserDoesNotExist = UserDoesNotExist
mock_exceptions_v3.UserAlreadyExists = UserAlreadyExists

mock_exceptions_v1 = ModuleType('mock_exceptions_v1')
mock_exceptions_v1.HTTPNotFound = HTTPNotFound
mock_exceptions_v1.SSHException = SSHException

sys.modules['hpe_storage_flowkit_py.v3.src.core.exceptions'] = mock_exceptions_v3
sys.modules['hpe_storage_flowkit_py.v3.src.core.session'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.core.logger'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.volumeset'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.cpg'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.volume'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.snapshot'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.qos'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.task'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.clone'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.hostset'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.ntp'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.dns'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.schedule'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v3.src.workflows.user'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.core.session'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.core.ssh'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.core.exceptions'] = mock_exceptions_v1
sys.modules['hpe_storage_flowkit_py.v1.src.workflows.remote_copy'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.workflows.system'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.utils.remote_copy_utils'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.validators.remote_copy_validator'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.workflows.host'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.utils.host_utils'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.validators.host_validator'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.workflows.vlun'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.utils.vlun_utils'] = MagicMock()
sys.modules['hpe_storage_flowkit_py.v1.src.validators.vlun_validator'] = MagicMock()


class TestAnsibleClient(unittest.TestCase):
    """Test cases for AnsibleClient class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset all mocks except the exception modules
        for key, module in sys.modules.items():
            if isinstance(module, MagicMock) and 'exceptions' not in key:
                module.reset_mock()
        
        # Reference the module-level exception mocks
        self.mock_exceptions_v3 = mock_exceptions_v3
        self.mock_exceptions_v1 = mock_exceptions_v1
        
        # Import the module under test and patch the exceptions in its namespace
        import hpe_storage_flowkit_py.services.src.ansible_service as ansible_module
        ansible_module.exceptions = mock_exceptions_v3
        ansible_module.exceptions_v1 = mock_exceptions_v1
        
        from hpe_storage_flowkit_py.services.src.ansible_service import AnsibleClient
        self.AnsibleClient = AnsibleClient
        
        # Create mock instances
        with patch.multiple('hpe_storage_flowkit_py.services.src.ansible_service',
                          SessionManagerV3=MagicMock(),
                          SessionManagerV1=MagicMock(),
                          SSHClient=MagicMock(),
                          Logger=MagicMock(),
                          VolumeSetWorkflow=MagicMock(),
                          CpgWorkflow=MagicMock(),
                          VolumeWorkflow=MagicMock(),
                          SnapshotWorkflow=MagicMock(),
                          QosWorkflow=MagicMock(),
                          TaskManager=MagicMock(),
                          CloneWorkflow=MagicMock(),
                          HostSetWorkflow=MagicMock(),
                          NTPWorkflow=MagicMock(),
                          DNSWorkflow=MagicMock(),
                          ScheduleWorkflow=MagicMock(),
                          UserWorkflow=MagicMock(),
                          RemoteCopyGroupWorkflow=MagicMock(),
                          SystemWorkflow=MagicMock(),
                          HostWorkflow=MagicMock(),
                          VLUNWorkflow=MagicMock()):
            self.client = self.AnsibleClient('10.0.0.1', 'admin', 'password', 'test.log')

    def test_init(self):
        """Test AnsibleClient initialization."""
        self.assertEqual(self.client.api_url_v3, 'https://10.0.0.1/api/v3')
        self.assertEqual(self.client.api_url_v1, 'https://10.0.0.1/api/v1')
        self.assertEqual(self.client.username, 'admin')
        self.assertEqual(self.client.password, 'password')

    def test_normalize_api_url(self):
        """Test API URL normalization."""
        url = self.client._normalize_api_url('192.168.1.1', 'v3')
        self.assertEqual(url, 'https://192.168.1.1/api/v3')

    # VolumeSet Tests
    def test_create_volumeset_success(self):
        """Test successful volumeset creation."""
        self.client.volumeset_workflow.create_volumeset = Mock(return_value={'id': 'vs1'})
        result = self.client.create_volumeset('test_vs', 'VIRTUAL_COPY')
        self.assertEqual(result, (True, True, 'Volume set test_vs created successfully', {}))

    def test_create_volumeset_already_exists(self):
        """Test volumeset creation when already exists."""
        self.client.volumeset_workflow.create_volumeset = Mock(
            side_effect=self.mock_exceptions_v3.VolumeSetAlreadyExists('Already exists'))
        result = self.client.create_volumeset('test_vs')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_create_volumeset_failure(self):
        """Test volumeset creation failure."""
        self.client.volumeset_workflow.create_volumeset = Mock(side_effect=Exception('Error'))
        result = self.client.create_volumeset('test_vs')
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], False)

    def test_modify_volumeset_success(self):
        """Test successful volumeset modification."""
        self.client.volumeset_workflow.modify_volumeset = Mock(return_value={'status': 'ok'})
        result = self.client.modify_volumeset('test_vs', new_name='new_vs')
        self.assertEqual(result, (True, True, 'Volume set test_vs modified successfully', {}))

    def test_modify_volumeset_failure(self):
        """Test volumeset modification failure."""
        self.client.volumeset_workflow.modify_volumeset = Mock(side_effect=Exception('Error'))
        result = self.client.modify_volumeset('test_vs')
        self.assertEqual(result[0], False)

    def test_delete_volumeset_success(self):
        """Test successful volumeset deletion."""
        self.client.volumeset_workflow.delete_volumeset = Mock(return_value={'status': 'ok'})
        result = self.client.delete_volumeset('test_vs')
        self.assertEqual(result, (True, True, 'Volume set test_vs deleted successfully', {}))

    def test_delete_volumeset_not_exists(self):
        """Test volumeset deletion when not exists."""
        self.client.volumeset_workflow.delete_volumeset = Mock(
            side_effect=self.mock_exceptions_v3.VolumeSetDoesNotExist('Not found'))
        result = self.client.delete_volumeset('test_vs')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_delete_volumeset_failure(self):
        """Test volumeset deletion failure."""
        self.client.volumeset_workflow.delete_volumeset = Mock(side_effect=Exception('Error'))
        result = self.client.delete_volumeset('test_vs')
        self.assertEqual(result[0], False)

    def test_add_volumes_to_volumeset_success(self):
        """Test successful adding volumes to volumeset."""
        self.client.volumeset_workflow.add_volumes_to_volumeset = Mock(return_value={'status': 'ok'})
        result = self.client.add_volumes_to_volumeset('test_vs', ['vol1', 'vol2'])
        self.assertEqual(result, (True, True, 'Volumes added to volume set test_vs successfully', {}))

    def test_add_volumes_to_volumeset_already_present(self):
        """Test adding volumes when already present."""
        self.client.volumeset_workflow.add_volumes_to_volumeset = Mock(
            side_effect=self.mock_exceptions_v3.VolumeSetMembersAlreadyPresent('Already present'))
        result = self.client.add_volumes_to_volumeset('test_vs', ['vol1'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_add_volumes_to_volumeset_not_exists(self):
        """Test adding volumes when volumeset doesn't exist."""
        self.client.volumeset_workflow.add_volumes_to_volumeset = Mock(
            side_effect=self.mock_exceptions_v3.VolumeSetDoesNotExist('Not found'))
        result = self.client.add_volumes_to_volumeset('test_vs', ['vol1'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_add_volumes_to_volumeset_failure(self):
        """Test adding volumes failure."""
        self.client.volumeset_workflow.add_volumes_to_volumeset = Mock(side_effect=Exception('Error'))
        result = self.client.add_volumes_to_volumeset('test_vs', ['vol1'])
        self.assertEqual(result[0], False)

    def test_remove_volumes_from_volumeset_success(self):
        """Test successful removing volumes from volumeset."""
        self.client.volumeset_workflow.remove_volumes_from_volumeset = Mock(return_value={'status': 'ok'})
        result = self.client.remove_volumes_from_volumeset('test_vs', ['vol1'])
        self.assertEqual(result, (True, True, 'Volumes removed from volume set test_vs successfully', {}))

    def test_remove_volumes_from_volumeset_already_removed(self):
        """Test removing volumes when already removed."""
        self.client.volumeset_workflow.remove_volumes_from_volumeset = Mock(
            side_effect=self.mock_exceptions_v3.VolumeSetMembersAlreadyRemoved('Already removed'))
        result = self.client.remove_volumes_from_volumeset('test_vs', ['vol1'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_remove_volumes_from_volumeset_not_exists(self):
        """Test removing volumes when volumeset doesn't exist."""
        self.client.volumeset_workflow.remove_volumes_from_volumeset = Mock(
            side_effect=self.mock_exceptions_v3.VolumeSetDoesNotExist('Not found'))
        result = self.client.remove_volumes_from_volumeset('test_vs', ['vol1'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_remove_volumes_from_volumeset_failure(self):
        """Test removing volumes failure."""
        self.client.volumeset_workflow.remove_volumes_from_volumeset = Mock(side_effect=Exception('Error'))
        result = self.client.remove_volumes_from_volumeset('test_vs', ['vol1'])
        self.assertEqual(result[0], False)

    # CPG Tests
    def test_create_cpg_success(self):
        """Test successful CPG creation."""
        self.client.cpg_workflow.create_cpg = Mock(return_value={'id': 'cpg1'})
        result = self.client.create_cpg('test_cpg')
        self.assertEqual(result, (True, True, 'CPG test_cpg created successfully', {}))

    def test_create_cpg_already_exists(self):
        """Test CPG creation when already exists."""
        self.client.cpg_workflow.create_cpg = Mock(
            side_effect=self.mock_exceptions_v3.CpgAlreadyExists('Already exists'))
        result = self.client.create_cpg('test_cpg')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_create_cpg_failure(self):
        """Test CPG creation failure."""
        self.client.cpg_workflow.create_cpg = Mock(side_effect=Exception('Error'))
        result = self.client.create_cpg('test_cpg')
        self.assertEqual(result[0], False)

    def test_delete_cpg_success(self):
        """Test successful CPG deletion."""
        self.client.cpg_workflow.delete_cpg = Mock(return_value={'status': 'ok'})
        result = self.client.delete_cpg('test_cpg')
        self.assertEqual(result, (True, True, 'CPG test_cpg deleted successfully', {}))

    def test_delete_cpg_not_exists(self):
        """Test CPG deletion when not exists."""
        self.client.cpg_workflow.delete_cpg = Mock(
            side_effect=self.mock_exceptions_v3.CpgDoesNotExist('Not found'))
        result = self.client.delete_cpg('test_cpg')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_delete_cpg_failure(self):
        """Test CPG deletion failure."""
        self.client.cpg_workflow.delete_cpg = Mock(side_effect=Exception('Error'))
        result = self.client.delete_cpg('test_cpg')
        self.assertEqual(result[0], False)

    # Volume Tests
    def test_create_volume_success(self):
        """Test successful volume creation."""
        self.client.volume_workflow.create_volume = Mock(return_value={'id': 'vol1'})
        result = self.client.create_volume('test_vol', 'cpg1', 1024)
        self.assertEqual(result, (True, True, 'Volume test_vol created successfully', {}))

    def test_create_volume_already_exists(self):
        """Test volume creation when already exists."""
        self.client.volume_workflow.create_volume = Mock(
            side_effect=self.mock_exceptions_v3.VolumeAlreadyExists('Already exists'))
        result = self.client.create_volume('test_vol', 'cpg1', 1024)
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_create_volume_failure(self):
        """Test volume creation failure."""
        self.client.volume_workflow.create_volume = Mock(side_effect=Exception('Error'))
        result = self.client.create_volume('test_vol', 'cpg1', 1024)
        self.assertEqual(result[0], False)

    def test_delete_volume_success(self):
        """Test successful volume deletion."""
        self.client.volume_workflow.delete_volume = Mock(return_value={'status': 'ok'})
        result = self.client.delete_volume('test_vol')
        self.assertEqual(result, (True, True, 'Volume test_vol deleted successfully', {}))

    def test_delete_volume_not_exists(self):
        """Test volume deletion when not exists."""
        self.client.volume_workflow.delete_volume = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.delete_volume('test_vol')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_delete_volume_failure(self):
        """Test volume deletion failure."""
        self.client.volume_workflow.delete_volume = Mock(side_effect=Exception('Error'))
        result = self.client.delete_volume('test_vol')
        self.assertEqual(result[0], False)

    def test_modify_volume_success(self):
        """Test successful volume modification."""
        self.client.volume_workflow.modify_volume = Mock(return_value={'status': 'ok'})
        result = self.client.modify_volume('test_vol', newName='new_vol')
        self.assertEqual(result, (True, True, 'Volume test_vol modified successfully', {}))

    def test_modify_volume_not_exists(self):
        """Test volume modification when not exists."""
        self.client.volume_workflow.modify_volume = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.modify_volume('test_vol')
        self.assertEqual(result[0], False)

    def test_modify_volume_failure(self):
        """Test volume modification failure."""
        self.client.volume_workflow.modify_volume = Mock(side_effect=Exception('Error'))
        result = self.client.modify_volume('test_vol')
        self.assertEqual(result[0], False)

    def test_is_volume_exists_true(self):
        """Test volume existence check returns True."""
        self.client.volume_workflow.get_volume_info = Mock(return_value={'name': 'test_vol'})
        result = self.client.is_volume_exists('test_vol')
        self.assertTrue(result)

    def test_is_volume_exists_false(self):
        """Test volume existence check returns False."""
        self.client.volume_workflow.get_volume_info = Mock(return_value=None)
        result = self.client.is_volume_exists('test_vol')
        self.assertFalse(result)

    def test_is_volume_exists_exception(self):
        """Test volume existence check raises exception."""
        self.client.volume_workflow.get_volume_info = Mock(side_effect=Exception('Error'))
        with self.assertRaises(Exception):
            self.client.is_volume_exists('test_vol')

    def test_grow_volume_success(self):
        """Test successful volume growth."""
        self.client.volume_workflow.grow_volume = Mock(return_value={'status': 'ok'})
        result = self.client.grow_volume('test_vol', 1024)
        self.assertEqual(result, (True, True, 'Volume test_vol size modified', {}))

    def test_grow_volume_not_exists(self):
        """Test volume growth when not exists."""
        self.client.volume_workflow.grow_volume = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.grow_volume('test_vol', 1024)
        self.assertEqual(result[0], False)

    def test_grow_volume_failure(self):
        """Test volume growth failure."""
        self.client.volume_workflow.grow_volume = Mock(side_effect=Exception('Error'))
        result = self.client.grow_volume('test_vol', 1024)
        self.assertEqual(result[0], False)

    def test_tune_volume_success(self):
        """Test successful volume tuning."""
        self.client.volume_workflow.tune_volume = Mock(return_value={'status': 'ok'})
        result = self.client.tune_volume('test_vol', 'cpg1')
        self.assertEqual(result, (True, True, 'Volume test_vol tuned successfully', {}))

    def test_tune_volume_not_exists(self):
        """Test volume tuning when not exists."""
        self.client.volume_workflow.tune_volume = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.tune_volume('test_vol', 'cpg1')
        self.assertEqual(result[0], False)

    def test_tune_volume_failure(self):
        """Test volume tuning failure."""
        self.client.volume_workflow.tune_volume = Mock(side_effect=Exception('Error'))
        result = self.client.tune_volume('test_vol', 'cpg1')
        self.assertEqual(result[0], False)

    # Snapshot Tests
    def test_create_snapshot_success(self):
        """Test successful snapshot creation."""
        self.client.snapshot_workflow.create_snapshot = Mock(return_value={'id': 'snap1'})
        result = self.client.create_snapshot('test_vol', 'test_snap')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], True)

    def test_create_snapshot_already_exists(self):
        """Test snapshot creation when already exists."""
        self.client.snapshot_workflow.create_snapshot = Mock(
            side_effect=self.mock_exceptions_v3.VolumeAlreadyExists('Already exists'))
        result = self.client.create_snapshot('test_vol', 'test_snap')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_create_snapshot_volume_not_exists(self):
        """Test snapshot creation when volume doesn't exist."""
        self.client.snapshot_workflow.create_snapshot = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.create_snapshot('test_vol', 'test_snap')
        self.assertEqual(result[0], False)

    def test_create_snapshot_failure(self):
        """Test snapshot creation failure."""
        self.client.snapshot_workflow.create_snapshot = Mock(side_effect=Exception('Error'))
        result = self.client.create_snapshot('test_vol', 'test_snap')
        self.assertEqual(result[0], False)

    def test_delete_snapshot_success(self):
        """Test successful snapshot deletion."""
        self.client.snapshot_workflow.delete_snapshot = Mock(return_value={'status': 'ok'})
        result = self.client.delete_snapshot('test_snap')
        self.assertEqual(result, (True, True, 'Snapshot test_snap deleted successfully', {}))

    def test_delete_snapshot_not_exists(self):
        """Test snapshot deletion when not exists."""
        self.client.snapshot_workflow.delete_snapshot = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.delete_snapshot('test_snap')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_delete_snapshot_failure(self):
        """Test snapshot deletion failure."""
        self.client.snapshot_workflow.delete_snapshot = Mock(side_effect=Exception('Error'))
        result = self.client.delete_snapshot('test_snap')
        self.assertEqual(result[0], False)

    def test_promote_snapshot_volume_success(self):
        """Test successful snapshot promotion."""
        self.client.snapshot_workflow.promote_snapshot_volume = Mock(return_value={'status': 'ok'})
        result = self.client.promote_snapshot_volume('test_snap')
        self.assertEqual(result, (True, True, 'Snapshot test_snap promoted successfully', {}))

    def test_promote_snapshot_volume_not_exists(self):
        """Test snapshot promotion when not exists."""
        self.client.snapshot_workflow.promote_snapshot_volume = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.promote_snapshot_volume('test_snap')
        self.assertEqual(result[0], False)

    def test_promote_snapshot_volume_failure(self):
        """Test snapshot promotion failure."""
        self.client.snapshot_workflow.promote_snapshot_volume = Mock(side_effect=Exception('Error'))
        result = self.client.promote_snapshot_volume('test_snap')
        self.assertEqual(result[0], False)

    # QoS Tests
    def test_create_qos_success(self):
        """Test successful QoS creation."""
        self.client.qos_workflow.create_qos = Mock(return_value={'id': 'qos1'})
        result = self.client.create_qos('vvs1', {'bwMinGoalKB': 1024})
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], True)

    def test_create_qos_already_exists(self):
        """Test QoS creation when already exists."""
        self.client.qos_workflow.create_qos = Mock(
            side_effect=self.mock_exceptions_v3.QosAlreadyExists('Already exists'))
        result = self.client.create_qos('vvs1', {})
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_create_qos_failure(self):
        """Test QoS creation failure."""
        self.client.qos_workflow.create_qos = Mock(side_effect=Exception('Error'))
        result = self.client.create_qos('vvs1', {})
        self.assertEqual(result[0], False)

    def test_modify_qos_success(self):
        """Test successful QoS modification."""
        self.client.qos_workflow.modify_qos = Mock(return_value={'status': 'ok'})
        result = self.client.modify_qos('qos1', bwMinGoalKB=2048)
        self.assertEqual(result, (True, True, 'QoS rule qos1 modified successfully', {}))

    def test_modify_qos_not_exists(self):
        """Test QoS modification when not exists."""
        self.client.qos_workflow.modify_qos = Mock(
            side_effect=self.mock_exceptions_v3.QosDoesNotExist('Not found'))
        result = self.client.modify_qos('qos1')
        self.assertEqual(result[0], False)

    def test_modify_qos_failure(self):
        """Test QoS modification failure."""
        self.client.qos_workflow.modify_qos = Mock(side_effect=Exception('Error'))
        result = self.client.modify_qos('qos1')
        self.assertEqual(result[0], False)

    def test_delete_qos_success(self):
        """Test successful QoS deletion."""
        self.client.qos_workflow.delete_qos = Mock(return_value={'status': 'ok'})
        result = self.client.delete_qos('qos1')
        self.assertEqual(result, (True, True, 'QoS rule qos1 deleted successfully', {}))

    def test_delete_qos_not_exists(self):
        """Test QoS deletion when not exists."""
        self.client.qos_workflow.delete_qos = Mock(
            side_effect=self.mock_exceptions_v3.QosDoesNotExist('Not found'))
        result = self.client.delete_qos('qos1')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_delete_qos_failure(self):
        """Test QoS deletion failure."""
        self.client.qos_workflow.delete_qos = Mock(side_effect=Exception('Error'))
        result = self.client.delete_qos('qos1')
        self.assertEqual(result[0], False)

    def test_get_qos_success(self):
        """Test successful QoS retrieval."""
        self.client.qos_workflow.get_qos = Mock(return_value={'name': 'qos1'})
        result = self.client.get_qos('qos1')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)
        self.assertIn('response', result[3])

    def test_get_qos_not_found(self):
        """Test QoS retrieval when not found."""
        self.client.qos_workflow.get_qos = Mock(return_value=None)
        result = self.client.get_qos('qos1')
        self.assertEqual(result[0], False)

    def test_get_qos_failure(self):
        """Test QoS retrieval failure."""
        self.client.qos_workflow.get_qos = Mock(side_effect=Exception('Error'))
        result = self.client.get_qos('qos1')
        self.assertEqual(result[0], False)

    def test_list_qos_success(self):
        """Test successful QoS listing."""
        self.client.qos_workflow.list_qos = Mock(return_value=[{'name': 'qos1'}])
        result = self.client.list_qos()
        self.assertEqual(result[0], True)
        self.assertIn('response', result[3])

    def test_list_qos_failure(self):
        """Test QoS listing failure."""
        self.client.qos_workflow.list_qos = Mock(side_effect=Exception('Error'))
        result = self.client.list_qos()
        self.assertEqual(result[0], False)

    # Task Tests
    def test_wait_for_task_success(self):
        """Test successful task wait."""
        self.client.task_workflow.wait_for_task_to_end = Mock(return_value={'status': 'done'})
        result = self.client.wait_for_task('task1')
        self.assertEqual(result[0], True)
        self.assertIn('response', result[3])

    def test_wait_for_task_failure(self):
        """Test task wait failure."""
        self.client.task_workflow.wait_for_task_to_end = Mock(side_effect=Exception('Error'))
        result = self.client.wait_for_task('task1')
        self.assertEqual(result[0], False)

    def test_get_task_success(self):
        """Test successful task retrieval."""
        self.client.task_workflow.get_task = Mock(return_value={'id': 'task1'})
        result = self.client.get_task('task1')
        self.assertEqual(result[0], True)
        self.assertIn('response', result[3])

    def test_get_task_failure(self):
        """Test task retrieval failure."""
        self.client.task_workflow.get_task = Mock(side_effect=Exception('Error'))
        result = self.client.get_task('task1')
        self.assertEqual(result[0], False)

    def test_get_all_task_success(self):
        """Test successful get all tasks."""
        self.client.task_workflow.get_all_tasks = Mock(return_value=[{'id': 'task1'}])
        result = self.client.get_all_task()
        self.assertEqual(result, [{'id': 'task1'}])

    def test_get_all_task_failure(self):
        """Test get all tasks failure."""
        self.client.task_workflow.get_all_tasks = Mock(side_effect=Exception('Error'))
        with self.assertRaises(Exception):
            self.client.get_all_task()

    # Clone Tests
    def test_copy_volume_success(self):
        """Test successful volume copy."""
        self.client.clone_workflow.copy_volume = Mock(return_value={'status': 'ok'})
        result = self.client.copy_volume('src_vol', 'dest_vol')
        self.assertEqual(result, (True, True, 'Clone created successfully', {}))

    def test_copy_volume_not_exists(self):
        """Test volume copy when source doesn't exist."""
        self.client.clone_workflow.copy_volume = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.copy_volume('src_vol', 'dest_vol')
        self.assertEqual(result[0], False)

    def test_copy_volume_failure(self):
        """Test volume copy failure."""
        self.client.clone_workflow.copy_volume = Mock(side_effect=Exception('Error'))
        result = self.client.copy_volume('src_vol', 'dest_vol')
        self.assertEqual(result[0], False)

    def test_online_phy_copy_exist(self):
        """Test online physical copy existence check."""
        self.client.clone_workflow.online_physical_copy_exist = Mock(return_value=True)
        result = self.client.online_phy_copy_exist('src_vol', 'phy_copy')
        self.assertTrue(result)

    def test_online_phy_copy_exist_exception(self):
        """Test online physical copy existence check with exception."""
        error = Exception('Error')
        self.client.clone_workflow.online_physical_copy_exist = Mock(side_effect=error)
        result = self.client.online_phy_copy_exist('src_vol', 'phy_copy')
        self.assertEqual(result, error)

    def test_offline_phy_copy_exist(self):
        """Test offline physical copy existence check."""
        self.client.clone_workflow.offline_physical_copy_exist = Mock(return_value=False)
        result = self.client.offline_phy_copy_exist('src_vol', 'phy_copy')
        self.assertFalse(result)

    def test_offline_phy_copy_exist_exception(self):
        """Test offline physical copy existence check with exception."""
        error = Exception('Error')
        self.client.clone_workflow.offline_physical_copy_exist = Mock(side_effect=error)
        result = self.client.offline_phy_copy_exist('src_vol', 'phy_copy')
        self.assertEqual(result, error)

    def test_resync_physical_copy_success(self):
        """Test successful physical copy resync."""
        self.client.clone_workflow.resync_physical_copy = Mock(return_value={'status': 'ok'})
        result = self.client.resync_physical_copy('vol1')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], True)

    def test_resync_physical_copy_not_exists(self):
        """Test physical copy resync when volume doesn't exist."""
        self.client.clone_workflow.resync_physical_copy = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.resync_physical_copy('vol1')
        self.assertEqual(result[0], False)

    def test_resync_physical_copy_failure(self):
        """Test physical copy resync failure."""
        self.client.clone_workflow.resync_physical_copy = Mock(side_effect=Exception('Error'))
        result = self.client.resync_physical_copy('vol1')
        self.assertEqual(result[0], False)

    def test_stop_physical_copy_success(self):
        """Test successful physical copy stop."""
        self.client.clone_workflow.stop_physical_copy = Mock(return_value={'status': 'ok'})
        result = self.client.stop_physical_copy('vol1')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], True)

    def test_stop_physical_copy_not_exists(self):
        """Test physical copy stop when volume doesn't exist."""
        self.client.clone_workflow.stop_physical_copy = Mock(
            side_effect=self.mock_exceptions_v3.VolumeDoesNotExist('Not found'))
        result = self.client.stop_physical_copy('vol1')
        self.assertEqual(result[0], False)

    def test_stop_physical_copy_failure(self):
        """Test physical copy stop failure."""
        self.client.clone_workflow.stop_physical_copy = Mock(side_effect=Exception('Error'))
        result = self.client.stop_physical_copy('vol1')
        self.assertEqual(result[0], False)

    # HostSet Tests
    def test_create_hostset_success(self):
        """Test successful hostset creation."""
        self.client.hostset_workflow.create_hostset = Mock(return_value={'id': 'hs1'})
        result = self.client.create_hostset('test_hs')
        self.assertEqual(result, (True, True, 'Host set test_hs created successfully', {}))

    def test_create_hostset_already_exists(self):
        """Test hostset creation when already exists."""
        self.client.hostset_workflow.create_hostset = Mock(
            side_effect=self.mock_exceptions_v3.HostSetAlreadyExists('Already exists'))
        result = self.client.create_hostset('test_hs')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_create_hostset_failure(self):
        """Test hostset creation failure."""
        self.client.hostset_workflow.create_hostset = Mock(side_effect=Exception('Error'))
        result = self.client.create_hostset('test_hs')
        self.assertEqual(result[0], False)

    def test_delete_hostset_success(self):
        """Test successful hostset deletion."""
        self.client.hostset_workflow.delete_hostset = Mock(return_value={'status': 'ok'})
        result = self.client.delete_hostset('test_hs')
        self.assertEqual(result, (True, True, 'Host set test_hs deleted successfully', {}))

    def test_delete_hostset_not_exists(self):
        """Test hostset deletion when not exists."""
        self.client.hostset_workflow.delete_hostset = Mock(
            side_effect=self.mock_exceptions_v3.HostSetDoesNotExist('Not found'))
        result = self.client.delete_hostset('test_hs')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_delete_hostset_failure(self):
        """Test hostset deletion failure."""
        self.client.hostset_workflow.delete_hostset = Mock(side_effect=Exception('Error'))
        result = self.client.delete_hostset('test_hs')
        self.assertEqual(result[0], False)

    def test_add_hosts_to_hostset_success(self):
        """Test successful adding hosts to hostset."""
        self.client.hostset_workflow.add_hosts_to_hostset = Mock(return_value={'status': 'ok'})
        result = self.client.add_hosts_to_hostset('test_hs', ['host1'])
        self.assertEqual(result, (True, True, 'Hosts added to host set test_hs successfully', {}))

    def test_add_hosts_to_hostset_already_present(self):
        """Test adding hosts when already present."""
        self.client.hostset_workflow.add_hosts_to_hostset = Mock(
            side_effect=self.mock_exceptions_v3.HostSetMembersAlreadyPresent('Already present'))
        result = self.client.add_hosts_to_hostset('test_hs', ['host1'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_add_hosts_to_hostset_not_exists(self):
        """Test adding hosts when hostset doesn't exist."""
        self.client.hostset_workflow.add_hosts_to_hostset = Mock(
            side_effect=self.mock_exceptions_v3.HostSetDoesNotExist('Not found'))
        result = self.client.add_hosts_to_hostset('test_hs', ['host1'])
        self.assertEqual(result[0], False)

    def test_add_hosts_to_hostset_failure(self):
        """Test adding hosts failure."""
        self.client.hostset_workflow.add_hosts_to_hostset = Mock(side_effect=Exception('Error'))
        result = self.client.add_hosts_to_hostset('test_hs', ['host1'])
        self.assertEqual(result[0], False)

    def test_remove_hosts_from_hostset_success(self):
        """Test successful removing hosts from hostset."""
        self.client.hostset_workflow.remove_hosts_from_hostset = Mock(return_value={'status': 'ok'})
        result = self.client.remove_hosts_from_hostset('test_hs', ['host1'])
        self.assertEqual(result, (True, True, 'Hosts removed from host set test_hs successfully', {}))

    def test_remove_hosts_from_hostset_already_removed(self):
        """Test removing hosts when already removed."""
        self.client.hostset_workflow.remove_hosts_from_hostset = Mock(
            side_effect=self.mock_exceptions_v3.HostSetMembersAlreadyRemoved('Already removed'))
        result = self.client.remove_hosts_from_hostset('test_hs', ['host1'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_remove_hosts_from_hostset_not_exists(self):
        """Test removing hosts when hostset doesn't exist."""
        self.client.hostset_workflow.remove_hosts_from_hostset = Mock(
            side_effect=self.mock_exceptions_v3.HostSetDoesNotExist('Not found'))
        result = self.client.remove_hosts_from_hostset('test_hs', ['host1'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_remove_hosts_from_hostset_failure(self):
        """Test removing hosts failure."""
        self.client.hostset_workflow.remove_hosts_from_hostset = Mock(side_effect=Exception('Error'))
        result = self.client.remove_hosts_from_hostset('test_hs', ['host1'])
        self.assertEqual(result[0], False)

    # NTP/DateTime Tests
    def test_configure_datetime_success(self):
        """Test successful datetime configuration."""
        self.client.ntp_workflow.configure_datetime = Mock(return_value={'status': 'ok'})
        result = self.client.configure_datetime(timezone='UTC')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], True)

    def test_configure_datetime_system_not_exists(self):
        """Test datetime configuration when system doesn't exist."""
        self.client.ntp_workflow.configure_datetime = Mock(
            side_effect=self.mock_exceptions_v3.SystemDoesNotExist('Not found'))
        result = self.client.configure_datetime(timezone='UTC')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_configure_datetime_failure(self):
        """Test datetime configuration failure."""
        self.client.ntp_workflow.configure_datetime = Mock(side_effect=Exception('Error'))
        result = self.client.configure_datetime(timezone='UTC')
        self.assertEqual(result[0], False)

    def test_get_system_info_success(self):
        """Test successful system info retrieval."""
        self.client.ntp_workflow.get_system_info = Mock(return_value={'name': 'system1'})
        result = self.client.get_system_info()
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_get_system_info_not_exists(self):
        """Test system info retrieval when not exists."""
        self.client.ntp_workflow.get_system_info = Mock(
            side_effect=self.mock_exceptions_v3.SystemDoesNotExist('Not found'))
        result = self.client.get_system_info()
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_get_system_info_failure(self):
        """Test system info retrieval failure."""
        self.client.ntp_workflow.get_system_info = Mock(side_effect=Exception('Error'))
        result = self.client.get_system_info()
        self.assertEqual(result[0], False)

    # DNS/Network Tests
    def test_configure_network_success(self):
        """Test successful network configuration."""
        self.client.dns_workflow.configure_network = Mock(return_value={'status': 'ok'})
        result = self.client.configure_network(['8.8.8.8'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], True)

    def test_configure_network_commit_false(self):
        """Test network configuration with commit_change=False."""
        self.client.dns_workflow.configure_network = Mock(return_value={'status': 'ok'})
        result = self.client.configure_network(['8.8.8.8'], commit_change=False)
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_configure_network_system_not_exists(self):
        """Test network configuration when system doesn't exist."""
        self.client.dns_workflow.configure_network = Mock(
            side_effect=self.mock_exceptions_v3.SystemDoesNotExist('Not found'))
        result = self.client.configure_network(['8.8.8.8'])
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_configure_network_failure(self):
        """Test network configuration failure."""
        self.client.dns_workflow.configure_network = Mock(side_effect=Exception('Error'))
        result = self.client.configure_network(['8.8.8.8'])
        self.assertEqual(result[0], False)

    def test_get_dns_system_info_success(self):
        """Test successful DNS system info retrieval."""
        self.client.dns_workflow.get_system_info = Mock(return_value={'name': 'system1'})
        result = self.client.get_dns_system_info()
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_get_dns_system_info_not_exists(self):
        """Test DNS system info retrieval when not exists."""
        self.client.dns_workflow.get_system_info = Mock(
            side_effect=self.mock_exceptions_v3.SystemDoesNotExist('Not found'))
        result = self.client.get_dns_system_info()
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_get_dns_system_info_failure(self):
        """Test DNS system info retrieval failure."""
        self.client.dns_workflow.get_system_info = Mock(side_effect=Exception('Error'))
        result = self.client.get_dns_system_info()
        self.assertEqual(result[0], False)

    # Schedule Tests
    def test_create_schedule_success(self):
        """Test successful schedule creation."""
        self.client.schedule_workflow.create_schedule = Mock(return_value={'id': 'sched1'})
        result = self.client.create_schedule('test_sched')
        self.assertEqual(result, (True, True, 'Schedule test_sched created successfully', {}))

    def test_create_schedule_already_exists(self):
        """Test schedule creation when already exists."""
        self.client.schedule_workflow.create_schedule = Mock(
            side_effect=self.mock_exceptions_v3.ScheduleAlreadyExists('Already exists'))
        result = self.client.create_schedule('test_sched')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_create_schedule_failure(self):
        """Test schedule creation failure."""
        self.client.schedule_workflow.create_schedule = Mock(side_effect=Exception('Error'))
        result = self.client.create_schedule('test_sched')
        self.assertEqual(result[0], False)

    def test_modify_schedule_success(self):
        """Test successful schedule modification."""
        self.client.schedule_workflow.modify_schedule = Mock(return_value={'status': 'ok'})
        result = self.client.modify_schedule('test_sched')
        self.assertEqual(result, (True, True, 'Schedule test_sched modified successfully', {}))

    def test_modify_schedule_not_exists(self):
        """Test schedule modification when not exists."""
        self.client.schedule_workflow.modify_schedule = Mock(
            side_effect=self.mock_exceptions_v3.ScheduleDoesNotExist('Not found'))
        result = self.client.modify_schedule('test_sched')
        self.assertEqual(result[0], False)

    def test_modify_schedule_failure(self):
        """Test schedule modification failure."""
        self.client.schedule_workflow.modify_schedule = Mock(side_effect=Exception('Error'))
        result = self.client.modify_schedule('test_sched')
        self.assertEqual(result[0], False)

    def test_delete_schedule_success(self):
        """Test successful schedule deletion."""
        self.client.schedule_workflow.delete_schedule = Mock(return_value={'status': 'ok'})
        result = self.client.delete_schedule('test_sched')
        self.assertEqual(result, (True, True, 'Schedule test_sched deleted successfully', {}))

    def test_delete_schedule_not_exists(self):
        """Test schedule deletion when not exists."""
        self.client.schedule_workflow.delete_schedule = Mock(
            side_effect=self.mock_exceptions_v3.ScheduleDoesNotExist('Not found'))
        result = self.client.delete_schedule('test_sched')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_delete_schedule_failure(self):
        """Test schedule deletion failure."""
        self.client.schedule_workflow.delete_schedule = Mock(side_effect=Exception('Error'))
        result = self.client.delete_schedule('test_sched')
        self.assertEqual(result[0], False)

    def test_suspend_schedule_success(self):
        """Test successful schedule suspension."""
        self.client.schedule_workflow.suspend_schedule = Mock(return_value={'status': 'ok'})
        result = self.client.suspend_schedule('test_sched')
        self.assertEqual(result, (True, True, 'Schedule test_sched suspended successfully', {}))

    def test_suspend_schedule_not_exists(self):
        """Test schedule suspension when not exists."""
        self.client.schedule_workflow.suspend_schedule = Mock(
            side_effect=self.mock_exceptions_v3.ScheduleDoesNotExist('Not found'))
        result = self.client.suspend_schedule('test_sched')
        self.assertEqual(result[0], False)

    def test_suspend_schedule_failure(self):
        """Test schedule suspension failure."""
        self.client.schedule_workflow.suspend_schedule = Mock(side_effect=Exception('Error'))
        result = self.client.suspend_schedule('test_sched')
        self.assertEqual(result[0], False)

    def test_resume_schedule_success(self):
        """Test successful schedule resumption."""
        self.client.schedule_workflow.resume_schedule = Mock(return_value={'status': 'ok'})
        result = self.client.resume_schedule('test_sched')
        self.assertEqual(result, (True, True, 'Schedule test_sched resumed successfully', {}))

    def test_resume_schedule_not_exists(self):
        """Test schedule resumption when not exists."""
        self.client.schedule_workflow.resume_schedule = Mock(
            side_effect=self.mock_exceptions_v3.ScheduleDoesNotExist('Not found'))
        result = self.client.resume_schedule('test_sched')
        self.assertEqual(result[0], False)

    def test_resume_schedule_failure(self):
        """Test schedule resumption failure."""
        self.client.schedule_workflow.resume_schedule = Mock(side_effect=Exception('Error'))
        result = self.client.resume_schedule('test_sched')
        self.assertEqual(result[0], False)

    # User Tests
    def test_get_all_users_success(self):
        """Test successful get all users."""
        self.client.user_workflow.get_all_users = Mock(return_value=[{'name': 'user1'}])
        result = self.client.get_all_users()
        self.assertEqual(result[0], True)
        self.assertIn('response', result[3])

    def test_get_all_users_failure(self):
        """Test get all users failure."""
        self.client.user_workflow.get_all_users = Mock(side_effect=Exception('Error'))
        result = self.client.get_all_users()
        self.assertEqual(result[0], False)

    def test_get_user_by_name_success(self):
        """Test successful get user by name."""
        self.client.user_workflow.get_user_by_name = Mock(return_value={'name': 'user1'})
        result = self.client.get_user_by_name('user1')
        self.assertEqual(result[0], True)
        self.assertIn('response', result[3])

    def test_get_user_by_name_not_exists(self):
        """Test get user by name when not exists."""
        self.client.user_workflow.get_user_by_name = Mock(
            side_effect=self.mock_exceptions_v3.UserDoesNotExist('Not found'))
        result = self.client.get_user_by_name('user1')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_get_user_by_name_failure(self):
        """Test get user by name failure."""
        self.client.user_workflow.get_user_by_name = Mock(side_effect=Exception('Error'))
        result = self.client.get_user_by_name('user1')
        self.assertEqual(result[0], False)

    def test_create_user_success(self):
        """Test successful user creation."""
        self.client.user_workflow.create_user = Mock(return_value={'id': 'user1'})
        result = self.client.create_user('user1', 'pass123', 'admin')
        self.assertEqual(result, (True, True, 'User user1 created successfully', {}))

    def test_create_user_already_exists(self):
        """Test user creation when already exists."""
        self.client.user_workflow.create_user = Mock(
            side_effect=self.mock_exceptions_v3.UserAlreadyExists('Already exists'))
        result = self.client.create_user('user1', 'pass123', 'admin')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_create_user_failure(self):
        """Test user creation failure."""
        self.client.user_workflow.create_user = Mock(side_effect=Exception('Error'))
        result = self.client.create_user('user1', 'pass123', 'admin')
        self.assertEqual(result[0], False)

    def test_modify_user_by_name_success(self):
        """Test successful user modification."""
        self.client.user_workflow.modify_user_by_name = Mock(return_value={'status': 'ok'})
        result = self.client.modify_user_by_name('user1', new_password='newpass')
        self.assertEqual(result, (True, True, 'User user1 modified successfully', {}))

    def test_modify_user_by_name_not_exists(self):
        """Test user modification when not exists."""
        self.client.user_workflow.modify_user_by_name = Mock(
            side_effect=self.mock_exceptions_v3.UserDoesNotExist('Not found'))
        result = self.client.modify_user_by_name('user1')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_modify_user_by_name_failure(self):
        """Test user modification failure."""
        self.client.user_workflow.modify_user_by_name = Mock(side_effect=Exception('Error'))
        result = self.client.modify_user_by_name('user1')
        self.assertEqual(result[0], False)

    def test_delete_user_by_name_success(self):
        """Test successful user deletion."""
        self.client.user_workflow.delete_user_by_name = Mock(return_value={'status': 'ok'})
        result = self.client.delete_user_by_name('user1')
        self.assertEqual(result, (True, True, 'User user1 deleted successfully', {}))

    def test_delete_user_by_name_not_exists(self):
        """Test user deletion when not exists."""
        self.client.user_workflow.delete_user_by_name = Mock(
            side_effect=self.mock_exceptions_v3.UserDoesNotExist('Not found'))
        result = self.client.delete_user_by_name('user1')
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_delete_user_by_name_failure(self):
        """Test user deletion failure."""
        self.client.user_workflow.delete_user_by_name = Mock(side_effect=Exception('Error'))
        result = self.client.delete_user_by_name('user1')
        self.assertEqual(result[0], False)

    # Logout Tests
    def test_logout_success(self):
        """Test successful logout."""
        self.client.session_manager_v3.token = 'token_v3'
        self.client.session_manager_v1.token = 'token_v1'
        self.client.session_manager_v3.delete_session = Mock()
        self.client.session_manager_v1.delete_session = Mock()
        result = self.client.logout()
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], True)

    def test_logout_no_sessions(self):
        """Test logout with no active sessions."""
        self.client.session_manager_v3.token = None
        self.client.session_manager_v1.token = None
        result = self.client.logout()
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_logout_v3_failure(self):
        """Test logout with v3 session failure."""
        self.client.session_manager_v3.token = 'token_v3'
        self.client.session_manager_v1.token = 'token_v1'
        self.client.session_manager_v3.delete_session = Mock(side_effect=Exception('V3 Error'))
        self.client.session_manager_v1.delete_session = Mock()
        result = self.client.logout()
        self.assertEqual(result[0], False)

    def test_logout_v1_failure(self):
        """Test logout with v1 session failure."""
        self.client.session_manager_v3.token = 'token_v3'
        self.client.session_manager_v1.token = 'token_v1'
        self.client.session_manager_v3.delete_session = Mock()
        self.client.session_manager_v1.delete_session = Mock(side_effect=Exception('V1 Error'))
        result = self.client.logout()
        self.assertEqual(result[0], False)

    def test_logout_both_failure(self):
        """Test logout with both sessions failure."""
        self.client.session_manager_v3.token = 'token_v3'
        self.client.session_manager_v1.token = 'token_v1'
        self.client.session_manager_v3.delete_session = Mock(side_effect=Exception('V3 Error'))
        self.client.session_manager_v1.delete_session = Mock(side_effect=Exception('V1 Error'))
        result = self.client.logout()
        self.assertEqual(result[0], False)

    # =========================================================================
    # HOST OPERATIONS TESTS
    # =========================================================================

    def test_create_host_success(self):
        """Test successful host creation."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_create_host = Mock(return_value={'name': 'host1'})
            self.client.host_workflow.host_exists = Mock(return_value=False)
            self.client.host_workflow.create_host = Mock(return_value={'status': 'ok'})
            result = self.client.create_host('host1', iscsiNames=['iqn1'])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], True)

    def test_create_host_already_exists(self):
        """Test host creation when already exists."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_create_host = Mock(return_value={'name': 'host1'})
            self.client.host_workflow.host_exists = Mock(return_value=True)
            result = self.client.create_host('host1')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_create_host_failure(self):
        """Test host creation failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_create_host = Mock(side_effect=Exception('Error'))
            result = self.client.create_host('host1')
            self.assertEqual(result[0], False)

    def test_delete_host_success(self):
        """Test successful host deletion."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.host_workflow.delete_host = Mock(return_value={'status': 'ok'})
            result = self.client.delete_host('host1')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], True)

    def test_delete_host_not_present(self):
        """Test host deletion when not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.delete_host('host1')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_delete_host_failure(self):
        """Test host deletion failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.delete_host('host1')
            self.assertEqual(result[0], False)

    def test_modify_host_success(self):
        """Test successful host modification."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_modify_host = Mock(return_value={'newName': 'host2'})
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
            result = self.client.modify_host('host1', 'host2')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], True)

    def test_modify_host_not_present(self):
        """Test host modification when not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_modify_host = Mock(return_value={'newName': 'host2'})
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.modify_host('host1', 'host2')
            self.assertEqual(result[0], False)

    def test_modify_host_failure(self):
        """Test host modification failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_modify_host = Mock(side_effect=Exception('Error'))
            result = self.client.modify_host('host1', 'host2')
            self.assertEqual(result[0], False)

    def test_add_initiator_chap_success(self):
        """Test successful initiator CHAP addition."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_initiator_chap = Mock(return_value={'chapName': 'chap1'})
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
            result = self.client.add_initiator_chap('host1', 'chap1', 'secret123')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], True)

    def test_add_initiator_chap_host_not_present(self):
        """Test initiator CHAP addition when host not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_initiator_chap = Mock(return_value={'chapName': 'chap1'})
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.add_initiator_chap('host1', 'chap1', 'secret123')
            self.assertEqual(result[0], False)

    def test_add_initiator_chap_failure(self):
        """Test initiator CHAP addition failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_initiator_chap = Mock(side_effect=Exception('Error'))
            result = self.client.add_initiator_chap('host1', 'chap1', 'secret123')
            self.assertEqual(result[0], False)

    def test_remove_initiator_chap_success(self):
        """Test successful initiator CHAP removal."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
                mock_utils.HOST_EDIT_REMOVE = 1
                self.client.host_workflow.host_exists = Mock(return_value=True)
                self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
                result = self.client.remove_initiator_chap('host1')
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_remove_initiator_chap_not_present(self):
        """Test initiator CHAP removal when host not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.remove_initiator_chap('host1')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_remove_initiator_chap_failure(self):
        """Test initiator CHAP removal failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.remove_initiator_chap('host1')
            self.assertEqual(result[0], False)

    def test_initiator_chap_exists_true(self):
        """Test initiator CHAP existence check returns True."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.initiator_chap_exists = Mock(return_value=True)
            result = self.client.initiator_chap_exists('host1')
            self.assertTrue(result)

    def test_initiator_chap_exists_false(self):
        """Test initiator CHAP existence check returns False."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.initiator_chap_exists = Mock(return_value=False)
            result = self.client.initiator_chap_exists('host1')
            self.assertFalse(result)

    def test_initiator_chap_exists_exception(self):
        """Test initiator CHAP existence check exception."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params') as mock_validate:
            error = Exception('Error')
            mock_validate.side_effect = error
            result = self.client.initiator_chap_exists('host1')
            self.assertEqual(result, error)

    def test_add_target_chap_success(self):
        """Test successful target CHAP addition."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_target_chap = Mock(return_value={'chapName': 'chap1'})
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.host_workflow.initiator_chap_exists = Mock(return_value=True)
            self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
            result = self.client.add_target_chap('host1', 'chap1', 'secret123')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], True)

    def test_add_target_chap_host_not_present(self):
        """Test target CHAP addition when host not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_target_chap = Mock(return_value={'chapName': 'chap1'})
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.add_target_chap('host1', 'chap1', 'secret123')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_add_target_chap_no_initiator(self):
        """Test target CHAP addition when initiator CHAP doesn't exist."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_target_chap = Mock(return_value={'chapName': 'chap1'})
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.host_workflow.initiator_chap_exists = Mock(return_value=False)
            result = self.client.add_target_chap('host1', 'chap1', 'secret123')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_add_target_chap_failure(self):
        """Test target CHAP addition failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.preprocess_target_chap = Mock(side_effect=Exception('Error'))
            result = self.client.add_target_chap('host1', 'chap1', 'secret123')
            self.assertEqual(result[0], False)

    def test_remove_target_chap_success(self):
        """Test successful target CHAP removal."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
                mock_utils.HOST_EDIT_REMOVE = 1
                self.client.host_workflow.host_exists = Mock(return_value=True)
                self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
                result = self.client.remove_target_chap('host1')
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_remove_target_chap_not_present(self):
        """Test target CHAP removal when host not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.remove_target_chap('host1')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_remove_target_chap_failure(self):
        """Test target CHAP removal failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.remove_target_chap('host1')
            self.assertEqual(result[0], False)

    def test_queryHost(self):
        """Test host query."""
        self.client.host_workflow.query_hosts = Mock(return_value={'members': [{'name': 'host1'}]})
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.prepare_iqn_wwn_queryurl = Mock(return_value='query')
            result = self.client.queryHost(iqns=['iqn1'])
            self.assertEqual(result, [{'name': 'host1'}])

    def test_normalize_wwn(self):
        """Test WWN normalization."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
            mock_utils.normalize_wwn = Mock(return_value='50:01:02:03:04:05:06:07')
            result = self.client._normalize_wwn('5001020304050607')
            self.assertEqual(result, '50:01:02:03:04:05:06:07')

    def test_add_fc_path_to_host_success(self):
        """Test successful FC path addition."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
                mock_utils.PATH_OPERATION_ADD = 1
                self.client.host_workflow.host_exists = Mock(return_value=True)
                self.client.queryHost = Mock(return_value=[])
                self.client._normalize_wwn = Mock(return_value='50:01:02:03:04:05:06:07')
                self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
                result = self.client.add_fc_path_to_host('host1', ['5001020304050607'])
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_add_fc_path_to_host_empty_wwns(self):
        """Test FC path addition with empty WWN list."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            result = self.client.add_fc_path_to_host('host1', [])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_add_fc_path_to_host_not_present(self):
        """Test FC path addition when host not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.add_fc_path_to_host('host1', ['wwn1'])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_add_fc_path_to_host_already_assigned(self):
        """Test FC path addition when already assigned to same host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.queryHost = Mock(return_value=[{'name': 'host1'}])
            self.client._normalize_wwn = Mock(return_value='50:01:02:03:04:05:06:07')
            result = self.client.add_fc_path_to_host('host1', ['5001020304050607'])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_add_fc_path_to_host_assigned_to_other(self):
        """Test FC path addition when assigned to other host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.queryHost = Mock(return_value=[{'name': 'host2'}])
            self.client._normalize_wwn = Mock(return_value='50:01:02:03:04:05:06:07')
            result = self.client.add_fc_path_to_host('host1', ['5001020304050607'])
            self.assertEqual(result[0], False)

    def test_add_fc_path_to_host_failure(self):
        """Test FC path addition failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.add_fc_path_to_host('host1', ['wwn1'])
            self.assertEqual(result[0], False)

    def test_remove_fc_path_from_host_success(self):
        """Test successful FC path removal."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
                mock_utils.PATH_OPERATION_REMOVE = 2
                self.client.host_workflow.host_exists = Mock(return_value=True)
                self.client.queryHost = Mock(return_value=[{'name': 'host1'}])
                self.client._normalize_wwn = Mock(return_value='50:01:02:03:04:05:06:07')
                self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
                result = self.client.remove_fc_path_from_host('host1', ['5001020304050607'])
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_remove_fc_path_from_host_empty_wwns(self):
        """Test FC path removal with empty WWN list."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            result = self.client.remove_fc_path_from_host('host1', [])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_remove_fc_path_from_host_not_present(self):
        """Test FC path removal when host not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.remove_fc_path_from_host('host1', ['wwn1'])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_remove_fc_path_from_host_already_removed(self):
        """Test FC path removal when already removed."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.queryHost = Mock(return_value=[])
            self.client._normalize_wwn = Mock(return_value='50:01:02:03:04:05:06:07')
            result = self.client.remove_fc_path_from_host('host1', ['5001020304050607'])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_remove_fc_path_from_host_assigned_to_other(self):
        """Test FC path removal when assigned to other host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.queryHost = Mock(return_value=[{'name': 'host2'}])
            self.client._normalize_wwn = Mock(return_value='50:01:02:03:04:05:06:07')
            result = self.client.remove_fc_path_from_host('host1', ['5001020304050607'])
            self.assertEqual(result[0], False)

    def test_remove_fc_path_from_host_failure(self):
        """Test FC path removal failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.remove_fc_path_from_host('host1', ['wwn1'])
            self.assertEqual(result[0], False)

    def test_add_iscsi_path_to_host_success(self):
        """Test successful iSCSI path addition."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
                mock_utils.PATH_OPERATION_ADD = 1
                self.client.host_workflow.host_exists = Mock(return_value=True)
                self.client.queryHost = Mock(return_value=[])
                self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
                result = self.client.add_iscsi_path_to_host('host1', ['iqn.test'])
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_add_iscsi_path_to_host_empty_iqns(self):
        """Test iSCSI path addition with empty IQN list."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            result = self.client.add_iscsi_path_to_host('host1', [])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_add_iscsi_path_to_host_not_present(self):
        """Test iSCSI path addition when host not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.add_iscsi_path_to_host('host1', ['iqn1'])
            self.assertEqual(result[0], False)

    def test_add_iscsi_path_to_host_already_assigned(self):
        """Test iSCSI path addition when already assigned to same host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.queryHost = Mock(return_value=[{'name': 'host1'}])
            result = self.client.add_iscsi_path_to_host('host1', ['iqn.test'])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_add_iscsi_path_to_host_assigned_to_other(self):
        """Test iSCSI path addition when assigned to other host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.queryHost = Mock(return_value=[{'name': 'host2'}])
            result = self.client.add_iscsi_path_to_host('host1', ['iqn.test'])
            self.assertEqual(result[0], False)

    def test_add_iscsi_path_to_host_failure(self):
        """Test iSCSI path addition failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.add_iscsi_path_to_host('host1', ['iqn1'])
            self.assertEqual(result[0], False)

    def test_remove_iscsi_path_from_host_success(self):
        """Test successful iSCSI path removal."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.host_utils') as mock_utils:
                mock_utils.PATH_OPERATION_REMOVE = 2
                self.client.host_workflow.host_exists = Mock(return_value=True)
                self.client.queryHost = Mock(return_value=[{'name': 'host1'}])
                self.client.host_workflow.modify_host = Mock(return_value={'status': 'ok'})
                result = self.client.remove_iscsi_path_from_host('host1', ['iqn.test'])
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_remove_iscsi_path_from_host_empty_iqns(self):
        """Test iSCSI path removal with empty IQN list."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            result = self.client.remove_iscsi_path_from_host('host1', [])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_remove_iscsi_path_from_host_not_present(self):
        """Test iSCSI path removal when host not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=False)
            result = self.client.remove_iscsi_path_from_host('host1', ['iqn1'])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_remove_iscsi_path_from_host_already_removed(self):
        """Test iSCSI path removal when already removed."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.queryHost = Mock(return_value=[])
            result = self.client.remove_iscsi_path_from_host('host1', ['iqn.test'])
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_remove_iscsi_path_from_host_assigned_to_other(self):
        """Test iSCSI path removal when assigned to other host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params'):
            self.client.host_workflow.host_exists = Mock(return_value=True)
            self.client.queryHost = Mock(return_value=[{'name': 'host2'}])
            result = self.client.remove_iscsi_path_from_host('host1', ['iqn.test'])
            self.assertEqual(result[0], False)

    def test_remove_iscsi_path_from_host_failure(self):
        """Test iSCSI path removal failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_host_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.remove_iscsi_path_from_host('host1', ['iqn1'])
            self.assertEqual(result[0], False)

    # =========================================================================
    # VLUN OPERATIONS TESTS
    # =========================================================================

    def test_export_volume_to_host_success(self):
        """Test successful volume export to host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                mock_validate.return_value = True
                mock_payload.return_value = {'volumeName': 'vol1', 'hostname': 'host1'}
                self.client.vlun_workflow.vlun_exists = Mock(return_value=False)
                self.client.vlun_workflow.export_volume_to_host = Mock(return_value={'status': 'ok'})
                result = self.client.export_volume_to_host('vol1', 'host1', lun=1)
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_export_volume_to_host_invalid_params(self):
        """Test volume export with invalid params."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            mock_validate.return_value = False
            result = self.client.export_volume_to_host('vol1', 'host1')
            self.assertEqual(result[0], False)

    def test_export_volume_to_host_already_present(self):
        """Test volume export when VLUN already present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                mock_validate.return_value = True
                mock_payload.return_value = {'volumeName': 'vol1', 'hostname': 'host1'}
                self.client.vlun_workflow.vlun_exists = Mock(return_value=True)
                result = self.client.export_volume_to_host('vol1', 'host1', lun=1)
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], False)

    def test_export_volume_to_host_failure(self):
        """Test volume export failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.export_volume_to_host('vol1', 'host1')
            self.assertEqual(result[0], False)

    def test_unexport_volume_from_host_success(self):
        """Test successful volume unexport from host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                with patch('hpe_storage_flowkit_py.services.src.ansible_service.find_vlun') as mock_find:
                    mock_validate.return_value = True
                    mock_payload.return_value = {'volumeName': 'vol1', 'hostname': 'host1'}
                    mock_find.return_value = {'volumeName': 'vol1', 'lun': 1, 'hostname': 'host1'}
                    self.client.vlun_workflow.list_vluns = Mock(return_value=[])
                    self.client.vlun_workflow.unexport_volume_from_host = Mock(return_value={'status': 'ok'})
                    result = self.client.unexport_volume_from_host('vol1', 'host1', lun=1)
                    self.assertEqual(result[0], True)
                    self.assertEqual(result[1], True)

    def test_unexport_volume_from_host_not_exists(self):
        """Test volume unexport when VLUN doesn't exist."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                with patch('hpe_storage_flowkit_py.services.src.ansible_service.find_vlun') as mock_find:
                    mock_validate.return_value = True
                    mock_payload.return_value = {'volumeName': 'vol1'}
                    mock_find.return_value = None
                    self.client.vlun_workflow.list_vluns = Mock(return_value=[])
                    result = self.client.unexport_volume_from_host('vol1', 'host1', lun=1)
                    self.assertEqual(result[0], False)

    def test_unexport_volume_from_host_failure(self):
        """Test volume unexport failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            mock_validate.side_effect = Exception('Error')
            result = self.client.unexport_volume_from_host('vol1', 'host1', lun=1)
            self.assertEqual(result[0], False)

    def test_export_volume_to_hostset_success(self):
        """Test successful volume export to hostset."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                mock_validate.return_value = True
                mock_payload.return_value = {'volumeName': 'vol1', 'hostname': 'hostset1'}
                self.client.vlun_workflow.vlun_exists = Mock(return_value=False)
                self.client.vlun_workflow.export_volume_to_hostset = Mock(return_value={'status': 'ok'})
                result = self.client.export_volume_to_hostset('vol1', 'hostset1', lun=1)
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_unexport_volume_from_hostset_success(self):
        """Test successful volume unexport from hostset."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                with patch('hpe_storage_flowkit_py.services.src.ansible_service.find_vlun') as mock_find:
                    mock_validate.return_value = True
                    mock_payload.return_value = {'volumeName': 'vol1', 'hostname': 'hostset1'}
                    mock_find.return_value = {'volumeName': 'vol1', 'lun': 1, 'hostname': 'hostset1'}
                    self.client.vlun_workflow.list_vluns = Mock(return_value=[])
                    self.client.vlun_workflow.unexport_volume_from_hostset = Mock(return_value={'status': 'ok'})
                    result = self.client.unexport_volume_from_hostset('vol1', 'hostset1', lun=1)
                    self.assertEqual(result[0], True)
                    self.assertEqual(result[1], True)

    def test_export_volumeset_to_host_success(self):
        """Test successful volumeset export to host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                mock_validate.return_value = True
                mock_payload.return_value = {'volumeName': 'set:vs1', 'hostname': 'host1'}
                self.client.vlun_workflow.vlun_exists = Mock(return_value=False)
                self.client.vlun_workflow.export_volumeset_to_host = Mock(return_value={'status': 'ok'})
                result = self.client.export_volumeset_to_host('set:vs1', 'host1', lun=1)
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_unexport_volumeset_from_host_success(self):
        """Test successful volumeset unexport from host."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                with patch('hpe_storage_flowkit_py.services.src.ansible_service.find_vlun') as mock_find:
                    mock_validate.return_value = True
                    mock_payload.return_value = {'volumeName': 'set:vs1', 'hostname': 'host1'}
                    mock_find.return_value = {'volumeName': 'vol1', 'lun': 1, 'hostname': 'host1'}
                    self.client.vlun_workflow.list_vluns = Mock(return_value=[])
                    self.client.vlun_workflow.get_vvsets = Mock(return_value={'setmembers': ['vol1']})
                    self.client.vlun_workflow.unexport_volumeset_from_host = Mock(return_value={'status': 'ok'})
                    result = self.client.unexport_volumeset_from_host('set:vs1', 'host1', lun=1)
                    self.assertEqual(result[0], True)
                    self.assertEqual(result[1], True)

    def test_unexport_volumeset_from_host_no_vluns(self):
        """Test volumeset unexport when no VLUNs found."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                with patch('hpe_storage_flowkit_py.services.src.ansible_service.find_vlun') as mock_find:
                    mock_validate.return_value = True
                    mock_payload.return_value = {'volumeName': 'set:vs1'}
                    mock_find.return_value = None
                    self.client.vlun_workflow.list_vluns = Mock(return_value=[])
                    self.client.vlun_workflow.get_vvsets = Mock(return_value={'setmembers': ['vol1']})
                    result = self.client.unexport_volumeset_from_host('set:vs1', 'host1', lun=1)
                    self.assertEqual(result[0], False)

    def test_export_volumeset_to_hostset_success(self):
        """Test successful volumeset export to hostset."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                mock_validate.return_value = True
                mock_payload.return_value = {'volumeName': 'set:vs1', 'hostname': 'hostset1'}
                self.client.vlun_workflow.vlun_exists = Mock(return_value=False)
                self.client.vlun_workflow.export_volumeset_to_hostset = Mock(return_value={'status': 'ok'})
                result = self.client.export_volumeset_to_hostset('set:vs1', 'hostset1', lun=1)
                self.assertEqual(result[0], True)
                self.assertEqual(result[1], True)

    def test_unexport_volumeset_from_hostset_success(self):
        """Test successful volumeset unexport from hostset."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_params') as mock_validate:
            with patch('hpe_storage_flowkit_py.services.src.ansible_service.build_payload') as mock_payload:
                with patch('hpe_storage_flowkit_py.services.src.ansible_service.find_vlun') as mock_find:
                    mock_validate.return_value = True
                    mock_payload.return_value = {'volumeName': 'set:vs1', 'hostname': 'hostset1'}
                    mock_find.return_value = {'volumeName': 'vol1', 'lun': 1, 'hostname': 'hostset1'}
                    self.client.vlun_workflow.list_vluns = Mock(return_value=[])
                    self.client.vlun_workflow.get_vvsets = Mock(return_value={'setmembers': ['vol1']})
                    self.client.vlun_workflow.unexport_volumeset_from_hostset = Mock(return_value={'status': 'ok'})
                    result = self.client.unexport_volumeset_from_hostset('set:vs1', 'hostset1', lun=1)
                    self.assertEqual(result[0], True)
                    self.assertEqual(result[1], True)

    # =========================================================================
    # REMOTE COPY OPERATIONS TESTS
    # =========================================================================

    def test_create_remote_copy_group_success(self):
        """Test successful remote copy group creation."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.remote_copy_utils') as mock_utils:
            mock_utils.preprocess_create_remote_copy_group = Mock(
                return_value=([{'targetName': 'target1'}], ['target1'], {}))
            self.client.system_workflow.get_storage_system_info = Mock(return_value={'name': 'source1'})
            self.client.remote_copy_workflow.remote_copy_group_exists = Mock(return_value=False)
            self.client.remote_copy_workflow.create_remote_copy_group = Mock(return_value={'status': 'ok'})
            result = self.client.create_remote_copy_group('rcg1', 'domain1', [{'targetName': 'target1'}], 'cpg1', 'cpg2')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], True)

    def test_create_remote_copy_group_source_target_same(self):
        """Test remote copy group creation when source and target are same."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.remote_copy_utils') as mock_utils:
            mock_utils.preprocess_create_remote_copy_group = Mock(
                return_value=([{'targetName': 'source1'}], ['source1'], {}))
            self.client.system_workflow.get_storage_system_info = Mock(return_value={'name': 'source1'})
            result = self.client.create_remote_copy_group('rcg1', 'domain1', [{'targetName': 'source1'}], 'cpg1', 'cpg2')
            self.assertEqual(result[0], False)

    def test_create_remote_copy_group_already_exists(self):
        """Test remote copy group creation when already exists."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.remote_copy_utils') as mock_utils:
            mock_utils.preprocess_create_remote_copy_group = Mock(
                return_value=([{'targetName': 'target1'}], ['target1'], {}))
            self.client.system_workflow.get_storage_system_info = Mock(return_value={'name': 'source1'})
            self.client.remote_copy_workflow.remote_copy_group_exists = Mock(return_value=True)
            result = self.client.create_remote_copy_group('rcg1', 'domain1', [{'targetName': 'target1'}], 'cpg1', 'cpg2')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_create_remote_copy_group_failure(self):
        """Test remote copy group creation failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.remote_copy_utils') as mock_utils:
            mock_utils.preprocess_create_remote_copy_group = Mock(side_effect=Exception('Error'))
            result = self.client.create_remote_copy_group('rcg1', 'domain1', [], 'cpg1', 'cpg2')
            self.assertEqual(result[0], False)

    def test_delete_remote_copy_group_success(self):
        """Test successful remote copy group deletion."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.remote_copy_utils') as mock_utils:
            mock_utils.preprocess_delete_remote_copy_group = Mock()
            self.client.remote_copy_workflow.remote_copy_group_exists = Mock(return_value=True)
            self.client.remote_copy_workflow.delete_remote_copy_group = Mock(return_value={'status': 'ok'})
            result = self.client.delete_remote_copy_group('rcg1')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], True)

    def test_delete_remote_copy_group_not_present(self):
        """Test remote copy group deletion when not present."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.remote_copy_utils') as mock_utils:
            mock_utils.preprocess_delete_remote_copy_group = Mock()
            self.client.remote_copy_workflow.remote_copy_group_exists = Mock(return_value=False)
            result = self.client.delete_remote_copy_group('rcg1')
            self.assertEqual(result[0], True)
            self.assertEqual(result[1], False)

    def test_delete_remote_copy_group_failure(self):
        """Test remote copy group deletion failure."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.remote_copy_utils') as mock_utils:
            mock_utils.preprocess_delete_remote_copy_group = Mock(side_effect=Exception('Error'))
            result = self.client.delete_remote_copy_group('rcg1')
            self.assertEqual(result[0], False)

    def test_remote_copy_group_status_synced(self):
        """Test remote copy group status when all synced."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_remote_copy_group_params'):
            self.client.remote_copy_workflow.get_remote_copy_group = Mock(return_value={
                'targets': [{'state': 3}],
                'volumes': [{'remoteVolumes': [{'syncStatus': 3}]}]
            })
            result = self.client.remote_copy_group_status('rcg1')
            self.assertTrue(result)

    def test_remote_copy_group_status_not_synced_target(self):
        """Test remote copy group status when target not synced."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_remote_copy_group_params'):
            self.client.remote_copy_workflow.get_remote_copy_group = Mock(return_value={
                'targets': [{'state': 1}],
                'volumes': [{'remoteVolumes': [{'syncStatus': 3}]}]
            })
            result = self.client.remote_copy_group_status('rcg1')
            self.assertFalse(result)

    def test_remote_copy_group_status_not_synced_volume(self):
        """Test remote copy group status when volume not synced."""
        with patch('hpe_storage_flowkit_py.services.src.ansible_service.validate_remote_copy_group_params'):
            self.client.remote_copy_workflow.get_remote_copy_group = Mock(return_value={
                'targets': [{'state': 3}],
                'volumes': [{'remoteVolumes': [{'syncStatus': 1}]}]
            })
            result = self.client.remote_copy_group_status('rcg1')
            self.assertFalse(result)

    def test_start_remote_copy_service_success(self):
        """Test successful start remote copy service."""
        self.client.show_remote_copy_service = Mock(return_value=False)
        self.client.remote_copy_workflow.start_remote_copy_service = Mock(return_value=[])
        result = self.client.start_remote_copy_service()
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], True)

    def test_start_remote_copy_service_already_started(self):
        """Test start remote copy service when already started."""
        self.client.show_remote_copy_service = Mock(return_value=True)
        result = self.client.start_remote_copy_service()
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], False)

    def test_rcopy_link_exists_true(self):
        """Test remote copy link exists returns True."""
        self.client.remote_copy_workflow.get_rcopy_links = Mock(
            return_value=['target1 0:1:1 10.0.0.1'])
        result = self.client.rcopy_link_exists('target1', '0:1:1', '10.0.0.1')
        self.assertTrue(result)

    def test_rcopy_link_exists_false(self):
        """Test remote copy link exists returns False."""
        self.client.remote_copy_workflow.get_rcopy_links = Mock(
            return_value=['target2 0:2:2 10.0.0.2'])
        result = self.client.rcopy_link_exists('target1', '0:1:1', '10.0.0.1')
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
