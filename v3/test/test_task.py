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
import time

# Ensure src is on sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException
from hpe_storage_flowkit_py.v3.src.core.rest_client import RESTClient


class TestTaskManager(unittest.TestCase):
	"""Unit tests for TaskManager class.
	
	Tests cover all methods with positive and negative scenarios including edge cases.
	"""

	def setUp(self):
		"""Set up test fixtures before each test method."""
		self.session_mgr = Mock()
		self.session_mgr.rest_client = Mock(spec=RESTClient)
		self.task_manager = TaskManager(self.session_mgr)

	# ===================================================================
	# WAIT_FOR_TASK_TO_END TESTS
	# ===================================================================

	def test_wait_for_task_success_simple_id(self):
		"""Test successful task completion with simple task ID."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_FINISHED',
			'percentComplete': 100,
			'state': {'overall': 'STATE_NORMAL'}
		}
		
		result = self.task_manager.wait_for_task_to_end('task_123')
		
		self.session_mgr.rest_client.get.assert_called_with('/tasks/task_123')
		self.assertEqual(result['status'], 'STATE_FINISHED')

	def test_wait_for_task_success_uri_format(self):
		"""Test successful task completion with full URI format."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_FINISHED',
			'percentComplete': 100,
			'state': {'overall': 'STATE_NORMAL'}
		}
		
		result = self.task_manager.wait_for_task_to_end('/api/v3/tasks/task_456')
		
		# Should extract task ID from URI
		self.session_mgr.rest_client.get.assert_called_with('/tasks/task_456')
		self.assertEqual(result['status'], 'STATE_FINISHED')

	def test_wait_for_task_extract_from_nested_uri(self):
		"""Test task ID extraction from complex nested URI."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_FINISHED',
			'percentComplete': 100,
			'state': {'overall': 'STATE_NORMAL'}
		}
		
		result = self.task_manager.wait_for_task_to_end('/something/tasks/extracted_id')
		
		self.session_mgr.rest_client.get.assert_called_with('/tasks/extracted_id')

	@patch('src.workflows.task.time.sleep', return_value=None)
	def test_wait_for_task_polling_multiple_times(self, mock_sleep):
		"""Test task polling through multiple status checks."""
		# Simulate task progressing from running to finished
		responses = [
			{'status': 'STATE_RUNNING', 'percentComplete': 25},
			{'status': 'STATE_RUNNING', 'percentComplete': 50},
			{'status': 'STATE_RUNNING', 'percentComplete': 75},
			{'status': 'STATE_FINISHED', 'percentComplete': 100, 'state': {'overall': 'STATE_NORMAL'}}
		]
		self.session_mgr.rest_client.get.side_effect = responses
		
		result = self.task_manager.wait_for_task_to_end('task_polling')
		
		self.assertEqual(self.session_mgr.rest_client.get.call_count, 4)
		self.assertEqual(result['status'], 'STATE_FINISHED')
		self.assertEqual(mock_sleep.call_count, 3)  # Slept 3 times before final check

	def test_wait_for_task_failed_state(self):
		"""Test task that ends in STATE_FAILED."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_FAILED',
			'percentComplete': 50,
			'detailsMap': {'error': 'Something went wrong'}
		}
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.wait_for_task_to_end('task_fail')
		
		self.assertIn('STATE_FAILED', str(context.exception))

	def test_wait_for_task_cancelled_state(self):
		"""Test task that ends in STATE_CANCELLED."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_CANCELLED',
			'percentComplete': 30,
			'detailsMap': {'reason': 'User cancelled'}
		}
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.wait_for_task_to_end('task_cancel')
		
		self.assertIn('STATE_CANCELLED', str(context.exception))

	def test_wait_for_task_finished_abnormal_overall_state(self):
		"""Test task that finishes but with abnormal overall state."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_FINISHED',
			'percentComplete': 100,
			'state': {'overall': 'STATE_ERROR'}
		}
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.wait_for_task_to_end('task_abnormal')
		
		self.assertIn('STATE_ERROR', str(context.exception))

	def test_wait_for_task_finished_missing_overall_state(self):
		"""Test task that finishes but state field is missing overall."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_FINISHED',
			'percentComplete': 100,
			'state': {}  # Missing 'overall' key
		}
		
		# Should default to STATE_NORMAL and succeed
		result = self.task_manager.wait_for_task_to_end('task_no_overall')
		self.assertEqual(result['status'], 'STATE_FINISHED')

	def test_wait_for_task_api_exception(self):
		"""Test handling of REST client exceptions during polling."""
		self.session_mgr.rest_client.get.side_effect = Exception('Network error')
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.wait_for_task_to_end('task_error')
		
		self.assertIn('Failed to poll task status', str(context.exception))

	@patch('src.workflows.task.time.time')
	@patch('src.workflows.task.time.sleep', return_value=None)
	def test_wait_for_task_timeout_elapsed_time(self, mock_sleep, mock_time):
		"""Test task timeout using elapsed time check."""
		# Mock time to simulate timeout
		mock_time.side_effect = [0, 1300, 1300]  # Start, then exceed 1200s timeout
		
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_RUNNING',
			'percentComplete': 50
		}
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.wait_for_task_to_end('task_timeout')
		
		self.assertIn('did not complete within timeout', str(context.exception))

	@patch('src.workflows.task.time.time')
	@patch('src.workflows.task.time.sleep', return_value=None)
	@patch('src.workflows.task.TASK_TIMEOUT_SECS', 10)
	@patch('src.workflows.task.TASK_POLL_RATE_SECS', 3)
	def test_wait_for_task_timeout_max_attempts(self, mock_sleep, mock_time):
		"""Test task timeout after max attempts."""
		# Simulate time not advancing but hitting max attempts
		mock_time.return_value = 5  # Always under timeout
		
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_RUNNING',
			'percentComplete': 10
		}
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.wait_for_task_to_end('task_max_attempts')
		
		self.assertIn('did not complete within timeout', str(context.exception))

	def test_wait_for_task_hpe_exception_propagated(self):
		"""Test that HPEStorageException is propagated directly."""
		error = HPEStorageException('Custom HPE error')
		self.session_mgr.rest_client.get.side_effect = error
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.wait_for_task_to_end('task_hpe_err')
		
		self.assertEqual(context.exception, error)

	def test_wait_for_task_percent_complete_zero(self):
		"""Test task with percentComplete = 0."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_FINISHED',
			'percentComplete': 0,
			'state': {'overall': 'STATE_NORMAL'}
		}
		
		result = self.task_manager.wait_for_task_to_end('task_zero_pct')
		self.assertEqual(result['percentComplete'], 0)

	def test_wait_for_task_percent_complete_missing(self):
		"""Test task with missing percentComplete field."""
		self.session_mgr.rest_client.get.return_value = {
			'status': 'STATE_FINISHED',
			'state': {'overall': 'STATE_NORMAL'}
		}
		
		result = self.task_manager.wait_for_task_to_end('task_no_pct')
		self.assertEqual(result['status'], 'STATE_FINISHED')

	# ===================================================================
	# GET_TASK TESTS
	# ===================================================================

	def test_get_task_with_simple_id(self):
		"""Test fetching task with simple ID."""
		self.session_mgr.rest_client.get.return_value = {
			'taskId': 'task_123',
			'status': 'STATE_RUNNING'
		}
		
		result = self.task_manager.get_task('task_123')
		
		self.session_mgr.rest_client.get.assert_called_with('/tasks/task_123')
		self.assertEqual(result['taskId'], 'task_123')

	def test_get_task_with_full_uri(self):
		"""Test fetching task with full API URI."""
		self.session_mgr.rest_client.get.return_value = {
			'taskId': 'task_456',
			'status': 'STATE_FINISHED'
		}
		
		result = self.task_manager.get_task('/api/v3/tasks/task_456')
		
		# Should use full URI as-is
		self.session_mgr.rest_client.get.assert_called_with('/api/v3/tasks/task_456')
		self.assertEqual(result['taskId'], 'task_456')

	def test_get_task_with_non_api_path(self):
		"""Test fetching task with non-/api/ path builds endpoint."""
		self.session_mgr.rest_client.get.return_value = {
			'taskId': 'task_789',
			'status': 'STATE_FINISHED'
		}
		
		result = self.task_manager.get_task('task_789')
		
		self.session_mgr.rest_client.get.assert_called_with('/tasks/task_789')

	def test_get_task_exception(self):
		"""Test get_task with REST client exception."""
		self.session_mgr.rest_client.get.side_effect = Exception('API error')
		
		with self.assertRaises(Exception) as context:
			self.task_manager.get_task('task_error')
		
		self.assertIn('API error', str(context.exception))

	# ===================================================================
	# GET_ALL_TASKS TESTS
	# ===================================================================

	def test_get_all_tasks_success(self):
		"""Test successful retrieval of all tasks."""
		tasks_response = {
			'members': {
				'task_1': {'taskId': 'task_1', 'status': 'STATE_RUNNING'},
				'task_2': {'taskId': 'task_2', 'status': 'STATE_FINISHED'}
			}
		}
		self.session_mgr.rest_client.get.return_value = tasks_response
		
		result = self.task_manager.get_all_tasks()
		
		self.session_mgr.rest_client.get.assert_called_with('/tasks')
		self.assertEqual(result, tasks_response)

	def test_get_all_tasks_empty(self):
		"""Test get_all_tasks when no tasks exist."""
		self.session_mgr.rest_client.get.return_value = {'members': {}}
		
		result = self.task_manager.get_all_tasks()
		
		self.assertEqual(result, {'members': {}})

	def test_get_all_tasks_exception(self):
		"""Test get_all_tasks with REST client exception."""
		self.session_mgr.rest_client.get.side_effect = Exception('Connection error')
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.get_all_tasks()
		
		self.assertIn('Failed to fetch all tasks', str(context.exception))

	def test_get_all_tasks_timeout_exception(self):
		"""Test get_all_tasks with timeout exception."""
		self.session_mgr.rest_client.get.side_effect = TimeoutError('Request timeout')
		
		with self.assertRaises(HPEStorageException) as context:
			self.task_manager.get_all_tasks()
		
		self.assertIn('Failed to fetch all tasks', str(context.exception))


if __name__ == '__main__':
	unittest.main()
