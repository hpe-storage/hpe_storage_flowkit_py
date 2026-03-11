# Copyright (c) 2025 HPE. All rights reserved.

import unittest
from unittest.mock import Mock, patch, MagicMock
import hashlib
import time
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager


class TestSessionManager(unittest.TestCase):
    """Test cases for SessionManager class"""

    def setUp(self):
        """Set up test fixtures"""
        self.api_url = "https://test-api.example.com"
        self.username = "testuser"
        self.password = "testpass"
        # Clear session cache before each test
        SessionManager._session_cache.clear()

    def tearDown(self):
        """Clean up after tests"""
        SessionManager._session_cache.clear()

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_init_creates_session_manager(self, mock_logger, mock_rest_client):
        """Test SessionManager initialization"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "test_token_123"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)

        self.assertEqual(session_mgr.api_url, self.api_url)
        self.assertEqual(session_mgr.username, self.username)
        self.assertEqual(session_mgr.password, self.password)
        self.assertIsNotNone(session_mgr.token)
        mock_rest_client.assert_called_once_with(self.api_url)

    def test_make_session_key(self):
        """Test session key generation"""
        key1 = SessionManager._make_session_key("https://api1.com", "user1")
        key2 = SessionManager._make_session_key("https://api1.com", "user1")
        key3 = SessionManager._make_session_key("https://api2.com", "user1")

        # Same inputs should produce same key
        self.assertEqual(key1, key2)
        # Different inputs should produce different keys
        self.assertNotEqual(key1, key3)
        # Should be a valid sha256 hash (64 hex chars)
        self.assertEqual(len(key1), 64)

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_login_success(self, mock_logger, mock_rest_client):
        """Test successful login"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "test_token_abc123"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)

        self.assertEqual(session_mgr.token, "test_token_abc123")
        self.assertIn('Authorization', session_mgr.session.headers)
        self.assertEqual(session_mgr.session.headers['Authorization'], 'Bearer test_token_abc123')

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_login_empty_response(self, mock_logger, mock_rest_client):
        """Test login with empty response"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value=None)
        mock_rest_client.return_value = mock_rest_instance

        with self.assertRaises(Exception) as context:
            SessionManager(self.api_url, self.username, self.password)
        
        self.assertIn("Empty response from login API", str(context.exception))

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_login_no_token_in_response(self, mock_logger, mock_rest_client):
        """Test login with response missing token"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"status": "ok"})
        mock_rest_client.return_value = mock_rest_instance

        with self.assertRaises(Exception) as context:
            SessionManager(self.api_url, self.username, self.password)
        
        self.assertIn("Failed to obtain session token", str(context.exception))

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_login_api_exception(self, mock_logger, mock_rest_client):
        """Test login when API raises exception"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(side_effect=Exception("Connection error"))
        mock_rest_client.return_value = mock_rest_instance

        with self.assertRaises(Exception) as context:
            SessionManager(self.api_url, self.username, self.password)
        
        self.assertIn("Login failed", str(context.exception))

    @patch('src.core.session.time.time')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_cached_session_reuse(self, mock_logger, mock_rest_client, mock_time):
        """Test that cached session is reused when not expired"""
        mock_time.return_value = 1000.0
        
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "cached_token_123"})
        mock_rest_client.return_value = mock_rest_instance

        # Create first session
        session1 = SessionManager(self.api_url, self.username, self.password)
        token1 = session1.token
        
        # Mock time moves forward but still within timeout (14 minutes)
        mock_time.return_value = 1000.0 + (10 * 60)  # 10 minutes later
        
        # Create second session with same credentials
        session2 = SessionManager(self.api_url, self.username, self.password)
        token2 = session2.token

        # Should reuse cached token
        self.assertEqual(token1, token2)
        # Login should only be called once
        self.assertEqual(mock_rest_instance.post.call_count, 1)

    @patch('src.core.session.time.time')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_cached_session_expiry(self, mock_logger, mock_rest_client, mock_time):
        """Test that expired cached session is recreated"""
        mock_time.return_value = 1000.0
        
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(side_effect=[
            {"key": "token1"},
            {"key": "token2"}
        ])
        mock_rest_instance.delete = Mock()
        mock_rest_client.return_value = mock_rest_instance

        # Create first session
        session1 = SessionManager(self.api_url, self.username, self.password)
        token1 = session1.token
        
        # Mock time moves beyond timeout (15 minutes)
        mock_time.return_value = 1000.0 + (15 * 60)
        
        # Create second session with same credentials
        session2 = SessionManager(self.api_url, self.username, self.password)
        token2 = session2.token

        # Should have new token
        self.assertNotEqual(token1, token2)
        # Login should be called twice
        self.assertEqual(mock_rest_instance.post.call_count, 2)
        # Old token should be deleted
        mock_rest_instance.delete.assert_called_with(f"/credentials/{token1}")

    @patch('src.core.session.time.time')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_get_token_returns_current_token(self, mock_logger, mock_rest_client, mock_time):
        """Test get_token returns current valid token"""
        mock_time.return_value = 1000.0
        
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "current_token"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        # Get token within valid period
        token = session_mgr.get_token()
        
        self.assertEqual(token, "current_token")
        # Should not call login again
        self.assertEqual(mock_rest_instance.post.call_count, 1)

    @patch('src.core.session.time.time')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_get_token_refreshes_expired_token(self, mock_logger, mock_rest_client, mock_time):
        """Test get_token refreshes expired token"""
        mock_time.return_value = 1000.0
        
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(side_effect=[
            {"key": "old_token"},
            {"key": "new_token"}
        ])
        mock_rest_instance.delete = Mock()
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        old_token = session_mgr.token
        
        # Move time beyond expiry
        mock_time.return_value = 1000.0 + (15 * 60)
        
        # Get token should refresh
        new_token = session_mgr.get_token()
        
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(new_token, "new_token")
        # Should delete old token
        mock_rest_instance.delete.assert_called()

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_validate_token_success(self, mock_logger, mock_rest_client):
        """Test validate_token with valid token"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "valid_token"})
        mock_rest_instance.get = Mock(return_value={"status": "ok"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        is_valid = session_mgr.validate_token()
        
        self.assertTrue(is_valid)
        mock_rest_instance.get.assert_called_once_with("/credentials")

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_validate_token_no_token(self, mock_logger, mock_rest_client):
        """Test validate_token with no token"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "test_token"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        session_mgr.token = None
        
        is_valid = session_mgr.validate_token()
        
        self.assertFalse(is_valid)

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_validate_token_api_error(self, mock_logger, mock_rest_client):
        """Test validate_token when API call fails"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "test_token"})
        mock_rest_instance.get = Mock(side_effect=Exception("Unauthorized"))
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        is_valid = session_mgr.validate_token()
        
        self.assertFalse(is_valid)

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_ensure_session_with_valid_token(self, mock_logger, mock_rest_client):
        """Test ensure_session when token is already valid"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "valid_token"})
        mock_rest_instance.get = Mock(return_value={"status": "ok"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        token = session_mgr.ensure_session()
        
        self.assertEqual(token, "valid_token")
        # Should only login once during init
        self.assertEqual(mock_rest_instance.post.call_count, 1)

    @patch('src.core.session.time.time')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_ensure_session_refreshes_invalid_token(self, mock_logger, mock_rest_client, mock_time):
        """Test ensure_session refreshes invalid token"""
        mock_time.return_value = 1000.0
        
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(side_effect=[
            {"key": "initial_token"},
            {"key": "refreshed_token"}
        ])
        mock_rest_instance.get = Mock(side_effect=Exception("Invalid token"))
        mock_rest_instance.delete = Mock()
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        # Move time to trigger expiry
        mock_time.return_value = 1000.0 + (15 * 60)
        
        token = session_mgr.ensure_session()
        
        self.assertEqual(token, "refreshed_token")
        # Should login twice (init + refresh)
        self.assertEqual(mock_rest_instance.post.call_count, 2)

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_get_session_returns_session_object(self, mock_logger, mock_rest_client):
        """Test get_session returns session object"""
        mock_rest_instance = Mock()
        mock_session = Mock()
        mock_session.headers = {}
        mock_rest_instance.session = mock_session
        mock_rest_instance.post = Mock(return_value={"key": "test_token"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        session = session_mgr.get_session()
        
        self.assertEqual(session, mock_session)

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_delete_session(self, mock_logger, mock_rest_client):
        """Test delete_session removes token and cache"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "test_token_delete"})
        mock_rest_instance.delete = Mock()
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        session_key = session_mgr._session_key
        
        # Verify session is cached
        self.assertIn(session_key, SessionManager._session_cache)
        
        session_mgr.delete_session()
        
        # Token should be None
        self.assertIsNone(session_mgr.token)
        # Cache should be cleared
        self.assertNotIn(session_key, SessionManager._session_cache)
        # API should be called to delete token
        mock_rest_instance.delete.assert_called_once_with("/credentials/test_token_delete")

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_set_and_get_session_data(self, mock_logger, mock_rest_client):
        """Test set and get session data methods"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "test_token"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        # Set data
        session_mgr.set("test_key", "test_value")
        session_mgr.set("number", 42)
        
        # Get data
        self.assertEqual(session_mgr.get("test_key"), "test_value")
        self.assertEqual(session_mgr.get("number"), 42)
        self.assertIsNone(session_mgr.get("non_existent"))
        self.assertEqual(session_mgr.get("non_existent", "default"), "default")

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_clear_session_data(self, mock_logger, mock_rest_client):
        """Test clear session data method"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "test_token"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        # Set some data
        session_mgr.set("key1", "value1")
        session_mgr.set("key2", "value2")
        
        # Clear data
        session_mgr.clear()
        
        # Data should be cleared
        self.assertIsNone(session_mgr.get("key1"))
        self.assertIsNone(session_mgr.get("key2"))

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_session_data_methods_without_session_data_attr(self, mock_logger, mock_rest_client):
        """Test session data methods create session_data if it doesn't exist"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(return_value={"key": "test_token"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        # Delete session_data if it exists
        if hasattr(session_mgr, 'session_data'):
            delattr(session_mgr, 'session_data')
        
        # get should create session_data
        result = session_mgr.get("key")
        self.assertIsNone(result)
        self.assertTrue(hasattr(session_mgr, 'session_data'))

    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_login_clears_authorization_header(self, mock_logger, mock_rest_client):
        """Test that login clears any existing Authorization header before logging in"""
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {'Authorization': 'Bearer old_token'}
        mock_rest_instance.post = Mock(return_value={"key": "new_token"})
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        # Verify the authorization header was set with new token
        self.assertEqual(session_mgr.session.headers['Authorization'], 'Bearer new_token')

    @patch('src.core.session.time.time')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_get_token_with_no_token(self, mock_logger, mock_rest_client, mock_time):
        """Test get_token when token is None"""
        mock_time.return_value = 1000.0
        
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(side_effect=[
            {"key": "initial_token"},
            {"key": "new_token"}
        ])
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        
        # Set token to None
        session_mgr.token = None
        
        # Get token should create new one
        token = session_mgr.get_token()
        
        self.assertEqual(token, "new_token")
        self.assertEqual(mock_rest_instance.post.call_count, 2)

    @patch('src.core.session.time.time')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_cached_session_expiry_with_delete_failure(self, mock_logger, mock_rest_client, mock_time):
        """Test that expired cached session is recreated even when delete fails"""
        mock_time.return_value = 1000.0
        
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(side_effect=[
            {"key": "token1"},
            {"key": "token2"}
        ])
        # Delete raises exception
        mock_rest_instance.delete = Mock(side_effect=Exception("Delete failed"))
        mock_rest_client.return_value = mock_rest_instance

        # Create first session
        session1 = SessionManager(self.api_url, self.username, self.password)
        token1 = session1.token
        
        # Mock time moves beyond timeout (15 minutes)
        mock_time.return_value = 1000.0 + (15 * 60)
        
        # Create second session with same credentials - should succeed despite delete failure
        session2 = SessionManager(self.api_url, self.username, self.password)
        token2 = session2.token

        # Should have new token
        self.assertNotEqual(token1, token2)
        self.assertEqual(token2, "token2")
        # Login should be called twice
        self.assertEqual(mock_rest_instance.post.call_count, 2)

    @patch('src.core.session.time.time')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.RESTClient')
    @patch('hpe_storage_flowkit_py.v3.src.core.session.Logger')
    def test_get_token_refresh_with_delete_failure(self, mock_logger, mock_rest_client, mock_time):
        """Test get_token refreshes token even when delete of old token fails"""
        mock_time.return_value = 1000.0
        
        mock_rest_instance = Mock()
        mock_rest_instance.session = Mock()
        mock_rest_instance.session.headers = {}
        mock_rest_instance.post = Mock(side_effect=[
            {"key": "old_token"},
            {"key": "new_token"}
        ])
        # Delete raises exception
        mock_rest_instance.delete = Mock(side_effect=Exception("Delete failed"))
        mock_rest_client.return_value = mock_rest_instance

        session_mgr = SessionManager(self.api_url, self.username, self.password)
        old_token = session_mgr.token
        
        # Move time beyond expiry
        mock_time.return_value = 1000.0 + (15 * 60)
        
        # Get token should refresh despite delete failure
        new_token = session_mgr.get_token()
        
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(new_token, "new_token")
        # Should attempt to delete old token
        mock_rest_instance.delete.assert_called()


if __name__ == '__main__':
    unittest.main()
