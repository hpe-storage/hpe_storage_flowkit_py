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
from unittest.mock import Mock, patch
import sys
import os

# Ensure src is on sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hpe_storage_flowkit_py.v3.src.workflows.remote_copy import RemoteCopyGroupWorkflow
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.rest_client import RESTClient
from hpe_storage_flowkit_py.v3.src.validators.remote_copy_validator import (
    validate_admit_rcopy_host_params,
)


# ===================================================================
# VALIDATOR TESTS
# ===================================================================

class TestRemoteCopyValidator(unittest.TestCase):
    """Unit tests for validate_admit_rcopy_host_params."""

    # ---------- rcg_name ----------

    def test_rcg_name_none(self):
        """Null rcg_name raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            validate_admit_rcopy_host_params(None, "primary", host_names=["h1"])
        self.assertIn("null", str(ctx.exception).lower())

    def test_rcg_name_empty_string(self):
        """Empty string rcg_name raises ValueError."""
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("", "primary", host_names=["h1"])

    def test_rcg_name_blank_spaces(self):
        """Whitespace-only rcg_name raises ValueError."""
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("   ", "primary", host_names=["h1"])

    def test_rcg_name_not_string(self):
        """Non-string rcg_name raises ValueError."""
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params(123, "primary", host_names=["h1"])

    # ---------- proximity ----------

    def test_proximity_none(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", None, host_names=["h1"])

    def test_proximity_invalid_value(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "invalid", host_names=["h1"])

    def test_proximity_not_string(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", 42, host_names=["h1"])

    def test_proximity_primary(self):
        self.assertTrue(
            validate_admit_rcopy_host_params("rcg1", "primary", host_names=["h1"]))

    def test_proximity_secondary(self):
        self.assertTrue(
            validate_admit_rcopy_host_params("rcg1", "secondary", host_names=["h1"]))

    def test_proximity_all(self):
        self.assertTrue(
            validate_admit_rcopy_host_params("rcg1", "all", host_names=["h1"]))

    def test_proximity_case_insensitive(self):
        """Proximity comparison is case-insensitive."""
        self.assertTrue(
            validate_admit_rcopy_host_params("rcg1", "PRIMARY", host_names=["h1"]))

    # ---------- host_names ----------

    def test_host_names_not_list(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary", host_names="h1")

    def test_host_names_contains_non_string(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary", host_names=[123])

    def test_host_names_contains_empty_string(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary", host_names=[""])

    def test_host_names_contains_blank_string(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary", host_names=["  "])

    def test_host_names_mixed_valid_and_blank(self):
        """One blank among valid names still raises."""
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary",
                                             host_names=["h1", "  ", "h2"])

    def test_host_names_valid(self):
        self.assertTrue(
            validate_admit_rcopy_host_params("rcg1", "primary",
                                             host_names=["host1", "host2"]))

    # ---------- hostset_names ----------

    def test_hostset_names_not_list(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary", hostset_names="hs1")

    def test_hostset_names_contains_non_string(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary", hostset_names=[99])

    def test_hostset_names_contains_empty_string(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary", hostset_names=[""])

    def test_hostset_names_contains_blank_string(self):
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary", hostset_names=["  "])

    def test_hostset_names_valid(self):
        self.assertTrue(
            validate_admit_rcopy_host_params("rcg1", "primary",
                                             hostset_names=["hs1"]))

    # ---------- mutual exclusion ----------

    def test_neither_host_nor_hostset(self):
        """Must provide at least one of host_names / hostset_names."""
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary")

    def test_both_host_and_hostset(self):
        """Cannot mix host_names and hostset_names."""
        with self.assertRaises(ValueError):
            validate_admit_rcopy_host_params("rcg1", "primary",
                                             host_names=["h1"],
                                             hostset_names=["hs1"])

    # ---------- positive / edge ----------

    def test_single_host_name(self):
        self.assertTrue(
            validate_admit_rcopy_host_params("rcg1", "primary",
                                             host_names=["h1"]))

    def test_single_hostset_name(self):
        self.assertTrue(
            validate_admit_rcopy_host_params("rcg1", "all",
                                             hostset_names=["hs1"]))


# ===================================================================
# WORKFLOW TESTS
# ===================================================================

class TestRemoteCopyGroupWorkflow(unittest.TestCase):
    """Unit tests for RemoteCopyGroupWorkflow class.

    Tests cover all methods with positive, negative, and edge-case scenarios.
    """

    def setUp(self):
        self.session_mgr = Mock()
        self.session_mgr.rest_client = Mock(spec=RESTClient)
        self.task_manager = Mock()
        self.task_manager.wait_for_task_to_end.return_value = {"status": "completed"}
        self.workflow = RemoteCopyGroupWorkflow(self.session_mgr, self.task_manager)

    # ---- helper ----

    def _simulate_rcg_exists(self, name, uid="rcg-uid-1"):
        """Configure the mock so that _get_rcg_info returns a hit."""
        self.session_mgr.rest_client.get.return_value = [
            {"uid": uid, "name": name}
        ]

    def _simulate_rcg_not_found(self):
        self.session_mgr.rest_client.get.return_value = []

    # ===================================================================
    # GET_RCG_INFO TESTS
    # ===================================================================

    def test_get_rcg_info_found(self):
        """Return RCG data when the group exists."""
        self._simulate_rcg_exists("rcg1", uid="uid-abc")
        result = self.workflow.get_rcg_info("rcg1")
        self.assertEqual(result["uid"], "uid-abc")
        self.assertEqual(result["name"], "rcg1")
        self.session_mgr.rest_client.get.assert_called_once()
        call_uri = self.session_mgr.rest_client.get.call_args[0][0]
        self.assertIn("/remotecopygroups?name=rcg1", call_uri)

    def test_get_rcg_info_passes_experimental_header(self):
        """Verify experimentalfilter header is sent."""
        self._simulate_rcg_exists("rcg1")
        self.workflow.get_rcg_info("rcg1")
        _, kwargs = self.session_mgr.rest_client.get.call_args
        self.assertEqual(kwargs.get("headers", {}).get("experimentalfilter"), "true")

    def test_get_rcg_info_not_found(self):
        """Return None when the group does not exist."""
        self._simulate_rcg_not_found()
        result = self.workflow.get_rcg_info("no_such_rcg")
        self.assertIsNone(result)

    def test_get_rcg_info_api_exception_propagates(self):
        """API errors propagate out of get_rcg_info."""
        self.session_mgr.rest_client.get.side_effect = Exception("connection lost")
        with self.assertRaises(Exception) as ctx:
            self.workflow.get_rcg_info("rcg1")
        self.assertIn("connection lost", str(ctx.exception))

    # ===================================================================
    # _GET_RCG_UID TESTS (internal, but critical path)
    # ===================================================================

    def test_get_rcg_uid_success(self):
        self._simulate_rcg_exists("rcg1", uid="uid-123")
        uid = self.workflow._get_rcg_uid("rcg1")
        self.assertEqual(uid, "uid-123")

    def test_get_rcg_uid_not_found_raises(self):
        self._simulate_rcg_not_found()
        with self.assertRaises(exceptions.RemoteCopyGroupDoesNotExist):
            self.workflow._get_rcg_uid("missing_rcg")

    # ===================================================================
    # ADMIT_RCOPY_HOST – POSITIVE TESTS
    # ===================================================================

    def test_admit_host_with_host_names(self):
        """Basic happy path: admit a list of hosts with proximity=primary."""
        self._simulate_rcg_exists("rcg1", uid="uid-1")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        result = self.workflow.admit_rcopy_host(
            "rcg1", "primary", host_names=["host1", "host2"])

        self.assertEqual(result, {"status": "ok"})
        post_args = self.session_mgr.rest_client.post.call_args
        self.assertEqual(post_args[0][0], "/remotecopygroups/uid-1")
        payload = post_args[0][1]
        self.assertEqual(payload["action"], "RC_GROUP_ADMIT_HOST")
        self.assertEqual(payload["parameters"]["proximity"], "primary")
        self.assertEqual(payload["parameters"]["hostNames"], ["host1", "host2"])
        self.assertNotIn("hostSetNames", payload["parameters"])

    def test_admit_host_with_hostset_names(self):
        """Admit host sets instead of individual hosts."""
        self._simulate_rcg_exists("rcg1", uid="uid-2")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        result = self.workflow.admit_rcopy_host(
            "rcg1", "secondary", hostset_names=["hset1"])

        payload = self.session_mgr.rest_client.post.call_args[0][1]
        self.assertEqual(payload["parameters"]["proximity"], "secondary")
        self.assertEqual(payload["parameters"]["hostSetNames"], ["hset1"])
        self.assertNotIn("hostNames", payload["parameters"])

    def test_admit_host_proximity_all(self):
        """Proximity='all' is accepted and lowered in the payload."""
        self._simulate_rcg_exists("rcg1", uid="uid-3")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        self.workflow.admit_rcopy_host(
            "rcg1", "ALL", host_names=["h1"])

        payload = self.session_mgr.rest_client.post.call_args[0][1]
        self.assertEqual(payload["parameters"]["proximity"], "all")

    def test_admit_host_proximity_mixed_case(self):
        """Proximity is case-insensitive for validation but stored lower."""
        self._simulate_rcg_exists("rcg1", uid="uid-4")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        self.workflow.admit_rcopy_host("rcg1", "Primary", host_names=["h1"])

        payload = self.session_mgr.rest_client.post.call_args[0][1]
        self.assertEqual(payload["parameters"]["proximity"], "primary")

    def test_admit_host_single_host(self):
        """Single-item host list works."""
        self._simulate_rcg_exists("rcg1", uid="uid-5")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        self.workflow.admit_rcopy_host("rcg1", "primary", host_names=["h1"])

        payload = self.session_mgr.rest_client.post.call_args[0][1]
        self.assertEqual(payload["parameters"]["hostNames"], ["h1"])

    # ===================================================================
    # ADMIT_RCOPY_HOST – ASYNC / TASK HANDLING
    # ===================================================================

    def test_admit_host_with_task_uri(self):
        """When API returns taskUri, workflow waits for the task."""
        self._simulate_rcg_exists("rcg1", uid="uid-6")
        self.session_mgr.rest_client.post.return_value = {
            "taskUri": "/api/v3/tasks/task-99"
        }
        self.task_manager.wait_for_task_to_end.return_value = {
            "status": "STATE_FINISHED"
        }

        result = self.workflow.admit_rcopy_host(
            "rcg1", "primary", host_names=["h1"])

        self.task_manager.wait_for_task_to_end.assert_called_once_with(
            "/api/v3/tasks/task-99")
        self.assertEqual(result["status"], "STATE_FINISHED")

    def test_admit_host_with_resource_uri(self):
        """When API returns resourceUri, workflow waits for the resource."""
        self._simulate_rcg_exists("rcg1", uid="uid-7")
        self.session_mgr.rest_client.post.return_value = {
            "resourceUri": "/api/v3/remotecopygroups/uid-7"
        }
        self.task_manager.wait_for_task_to_end.return_value = {
            "status": "STATE_FINISHED"
        }

        result = self.workflow.admit_rcopy_host(
            "rcg1", "primary", host_names=["h1"])

        self.task_manager.wait_for_task_to_end.assert_called_once_with(
            "/api/v3/remotecopygroups/uid-7")
        self.assertEqual(result["status"], "STATE_FINISHED")

    def test_admit_host_no_task_uri_returns_immediate_response(self):
        """When response has neither taskUri nor resourceUri, return as-is."""
        self._simulate_rcg_exists("rcg1", uid="uid-8")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        result = self.workflow.admit_rcopy_host(
            "rcg1", "primary", host_names=["h1"])

        self.task_manager.wait_for_task_to_end.assert_not_called()
        self.assertEqual(result, {"status": "ok"})

    # ===================================================================
    # ADMIT_RCOPY_HOST – NEGATIVE / VALIDATION TESTS
    # ===================================================================

    def test_admit_host_rcg_name_none(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host(None, "primary", host_names=["h1"])

    def test_admit_host_rcg_name_empty(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("", "primary", host_names=["h1"])

    def test_admit_host_rcg_name_blank(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("   ", "primary", host_names=["h1"])

    def test_admit_host_rcg_name_non_string(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host(123, "primary", host_names=["h1"])

    def test_admit_host_proximity_none(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", None, host_names=["h1"])

    def test_admit_host_proximity_invalid(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "nearby", host_names=["h1"])

    def test_admit_host_no_hosts_or_hostsets(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary")

    def test_admit_host_both_hosts_and_hostsets(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host(
                "rcg1", "primary",
                host_names=["h1"], hostset_names=["hs1"])

    def test_admit_host_host_names_not_list(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", host_names="h1")

    def test_admit_host_host_names_contains_non_string(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", host_names=[42])

    def test_admit_host_host_names_contains_empty(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", host_names=[""])

    def test_admit_host_host_names_contains_blank(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", host_names=["  "])

    def test_admit_host_hostset_names_not_list(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", hostset_names="hs1")

    def test_admit_host_hostset_names_contains_non_string(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", hostset_names=[True])

    def test_admit_host_hostset_names_contains_empty(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", hostset_names=[""])

    def test_admit_host_hostset_names_contains_blank(self):
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", hostset_names=["  "])

    # ===================================================================
    # ADMIT_RCOPY_HOST – RCG NOT FOUND
    # ===================================================================

    def test_admit_host_rcg_does_not_exist(self):
        """After validation passes, _get_rcg_uid raises if RCG missing."""
        self._simulate_rcg_not_found()
        with self.assertRaises(exceptions.RemoteCopyGroupDoesNotExist):
            self.workflow.admit_rcopy_host(
                "no_such_rcg", "primary", host_names=["h1"])

    # ===================================================================
    # ADMIT_RCOPY_HOST – API / POST ERRORS
    # ===================================================================

    def test_admit_host_post_raises_propagates(self):
        """REST client POST exception propagates through the workflow."""
        self._simulate_rcg_exists("rcg1", uid="uid-9")
        self.session_mgr.rest_client.post.side_effect = Exception("server error")
        with self.assertRaises(Exception) as ctx:
            self.workflow.admit_rcopy_host("rcg1", "primary", host_names=["h1"])
        self.assertIn("server error", str(ctx.exception))

    def test_admit_host_get_raises_propagates(self):
        """REST client GET exception (during UID lookup) propagates."""
        self.session_mgr.rest_client.get.side_effect = Exception("timeout")
        with self.assertRaises(Exception) as ctx:
            self.workflow.admit_rcopy_host("rcg1", "primary", host_names=["h1"])
        self.assertIn("timeout", str(ctx.exception))

    def test_admit_host_task_wait_raises_propagates(self):
        """Task manager exception propagates."""
        self._simulate_rcg_exists("rcg1", uid="uid-10")
        self.session_mgr.rest_client.post.return_value = {
            "taskUri": "/api/v3/tasks/task-fail"
        }
        self.task_manager.wait_for_task_to_end.side_effect = (
            exceptions.HPEStorageException("task failed")
        )
        with self.assertRaises(exceptions.HPEStorageException):
            self.workflow.admit_rcopy_host("rcg1", "primary", host_names=["h1"])

    # ===================================================================
    # EDGE CASES
    # ===================================================================

    def test_admit_host_multiple_hosts(self):
        """Verify payload carries all supplied hosts."""
        self._simulate_rcg_exists("rcg1", uid="uid-11")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        hosts = [f"host{i}" for i in range(10)]
        self.workflow.admit_rcopy_host("rcg1", "primary", host_names=hosts)

        payload = self.session_mgr.rest_client.post.call_args[0][1]
        self.assertEqual(payload["parameters"]["hostNames"], hosts)

    def test_admit_host_multiple_hostsets(self):
        """Verify payload carries all supplied host sets."""
        self._simulate_rcg_exists("rcg1", uid="uid-12")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        hsets = ["hset1", "hset2", "hset3"]
        self.workflow.admit_rcopy_host("rcg1", "secondary", hostset_names=hsets)

        payload = self.session_mgr.rest_client.post.call_args[0][1]
        self.assertEqual(payload["parameters"]["hostSetNames"], hsets)

    def test_admit_host_rcg_name_with_leading_trailing_spaces(self):
        """rcg_name with inner content but surrounding spaces passes validation
        and is sent as-is (server handles trimming)."""
        self._simulate_rcg_exists(" rcg1 ", uid="uid-13")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        self.workflow.admit_rcopy_host(" rcg1 ", "primary", host_names=["h1"])

        call_uri = self.session_mgr.rest_client.get.call_args[0][0]
        self.assertIn("name= rcg1 ", call_uri)

    def test_admit_host_post_endpoint_uses_rcg_uid(self):
        """POST hits /remotecopygroups/<uid>, not the name."""
        self._simulate_rcg_exists("rcg1", uid="special-uid")
        self.session_mgr.rest_client.post.return_value = {"status": "ok"}

        self.workflow.admit_rcopy_host("rcg1", "primary", host_names=["h1"])

        endpoint = self.session_mgr.rest_client.post.call_args[0][0]
        self.assertEqual(endpoint, "/remotecopygroups/special-uid")

    def test_admit_host_host_names_empty_list_raises(self):
        """Empty host_names list (falsy) with no hostset_names raises."""
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", host_names=[])

    def test_admit_host_hostset_names_empty_list_raises(self):
        """Empty hostset_names list (falsy) with no host_names raises."""
        with self.assertRaises(ValueError):
            self.workflow.admit_rcopy_host("rcg1", "primary", hostset_names=[])


if __name__ == '__main__':
    unittest.main()