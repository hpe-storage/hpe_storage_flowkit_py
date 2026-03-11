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
from unittest.mock import Mock
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hpe_storage_flowkit_py.v3.src.workflows.port import PortWorkflow
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException


class MockSessionManager:
    """Mock session manager for testing"""
    def __init__(self):
        self.rest_client = MockRestClient()


class MockRestClient:
    """Mock REST client for testing"""
    def __init__(self):
        self.get_response = None
    
    def get(self, endpoint):
        """Mock GET request"""
        if self.get_response is not None:
            return self.get_response
        
        # Default response - ports as dict of dicts
        return {
            'members': {
                'port-1': {
                    'portPos': {'node': 0, 'slot': 0, 'cardPort': 1},
                    'type': 'HOST',
                    'protocol': 'FC',
                    'mode': 'TARGET',
                    'linkState': 'READY'
                },
                'port-2': {
                    'portPos': {'node': 1, 'slot': 1, 'cardPort': 1},
                    'type': 'HOST',
                    'protocol': 'FC',
                    'mode': 'TARGET',
                    'linkState': 'READY'
                }
            }
        }


class TestPortWorkflow(unittest.TestCase):
    """Unit tests for PortWorkflow class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_mgr = MockSessionManager()
        self.workflow = PortWorkflow(self.session_mgr)
    
    def test_get_ports_success_dict_members(self):
        """Test getting ports when response has members as dict"""
        result = self.workflow.get_ports()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['type'], 'HOST')
        self.assertEqual(result[0]['protocol'], 'FC')
    
    def test_get_ports_success_list_members(self):
        """Test getting ports when response has members as list"""
        self.session_mgr.rest_client.get_response = {
            'members': [
                {'portPos': {'node': 0}, 'type': 'HOST'},
                {'portPos': {'node': 1}, 'type': 'HOST'}
            ]
        }
        
        result = self.workflow.get_ports()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
    
    def test_get_ports_direct_list_response(self):
        """Test getting ports when response is a direct list"""
        self.session_mgr.rest_client.get_response = [
            {'portPos': {'node': 0}, 'type': 'HOST'},
            {'portPos': {'node': 1}, 'type': 'DISK'}
        ]
        
        result = self.workflow.get_ports()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['type'], 'HOST')
        self.assertEqual(result[1]['type'], 'DISK')
    
    def test_get_ports_empty_members_dict(self):
        """Test getting ports when members dict is empty"""
        self.session_mgr.rest_client.get_response = {'members': {}}
        
        with self.assertRaises(ValueError) as context:
            self.workflow.get_ports()
        
        self.assertIn('Invalid ports response', str(context.exception))
    
    def test_get_ports_empty_members_list(self):
        """Test getting ports when members list is empty"""
        self.session_mgr.rest_client.get_response = {'members': []}
        
        with self.assertRaises(ValueError) as context:
            self.workflow.get_ports()
        
        self.assertIn('Invalid ports response', str(context.exception))
    
    def test_get_ports_no_members_key(self):
        """Test getting ports when response has no members key"""
        self.session_mgr.rest_client.get_response = {'data': 'some_data'}
        
        with self.assertRaises(ValueError) as context:
            self.workflow.get_ports()
        
        self.assertIn('Invalid ports response', str(context.exception))
    
    def test_get_ports_exception_handling(self):
        """Test exception handling in get_ports"""
        def raise_exception(endpoint):
            raise Exception("Network error")
        
        self.session_mgr.rest_client.get = raise_exception
        
        with self.assertRaises(Exception) as context:
            self.workflow.get_ports()
        
        self.assertIn('Network error', str(context.exception))
    
    def test_normalize_members_dict_of_dicts(self):
        """Test normalize_members with dict containing dict members"""
        response = {
            'members': {
                'port-1': {'name': 'port1'},
                'port-2': {'name': 'port2'}
            }
        }
        
        result = PortWorkflow.normalize_members(response)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
    
    def test_normalize_members_dict_of_list(self):
        """Test normalize_members with dict containing list members"""
        response = {
            'members': [
                {'name': 'port1'},
                {'name': 'port2'}
            ]
        }
        
        result = PortWorkflow.normalize_members(response)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'port1')
    
    def test_normalize_members_direct_list(self):
        """Test normalize_members with direct list"""
        response = [
            {'name': 'port1'},
            {'name': 'port2'}
        ]
        
        result = PortWorkflow.normalize_members(response)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
    
    def test_normalize_members_empty_dict(self):
        """Test normalize_members with empty dict"""
        result = PortWorkflow.normalize_members({})
        
        self.assertEqual(result, [])
    
    def test_normalize_members_dict_no_members(self):
        """Test normalize_members with dict but no members key"""
        result = PortWorkflow.normalize_members({'data': 'something'})
        
        self.assertEqual(result, [])
    
    def test_normalize_members_none(self):
        """Test normalize_members with None"""
        result = PortWorkflow.normalize_members(None)
        
        self.assertEqual(result, [])
    
    def test_normalize_members_string(self):
        """Test normalize_members with string"""
        result = PortWorkflow.normalize_members("not a dict or list")
        
        self.assertEqual(result, [])
    
    def test_normalize_members_empty_list(self):
        """Test normalize_members with empty list"""
        result = PortWorkflow.normalize_members([])
        
        self.assertEqual(result, [])
    
    def test_get_ports_multiple_port_types(self):
        """Test getting ports with multiple port types"""
        self.session_mgr.rest_client.get_response = {
            'members': {
                'port-1': {'type': 'HOST', 'protocol': 'FC'},
                'port-2': {'type': 'DISK', 'protocol': 'SAS'},
                'port-3': {'type': 'HOST', 'protocol': 'iSCSI'},
                'port-4': {'type': 'RCFC', 'protocol': 'FC'}
            }
        }
        
        result = self.workflow.get_ports()
        
        self.assertEqual(len(result), 4)
        types = [port['type'] for port in result]
        self.assertIn('HOST', types)
        self.assertIn('DISK', types)
        self.assertIn('RCFC', types)


if __name__ == '__main__':
    unittest.main()

