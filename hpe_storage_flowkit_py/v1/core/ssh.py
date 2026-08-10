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

import logging
import os
import re

import paramiko
from hpe_storage_flowkit_py.v1.src.core.exceptions import HPEStorageException
from urllib.parse import urlparse

# Python 3 detection (mirrors legacy pattern but simplified)
try:  # pragma: no cover - compatibility shim
	basestring  # type: ignore
	PY3 = False
except NameError:  # pragma: no cover
	basestring = str  # type: ignore
	PY3 = True


class SSHClient(object):
	"""Light‑weight SSH client tailored for 3PAR CLI gaps (non‑REST ops)."""

	log_debug = False
	_logger = logging.getLogger(__name__)
	_logger.setLevel(logging.INFO)

	def __init__(self, api_url, login, password, port=22, conn_timeout=None, privatekey=None, **kwargs):
		parsed = urlparse(api_url)
		ip = parsed.hostname
		self.san_ip = ip
		self.san_ssh_port = port
		self.ssh_conn_timeout = conn_timeout
		self.san_login = login
		self.san_password = password
		self.san_privatekey = privatekey
		self.ssh = None
		self._create_ssh(**kwargs)

	# ------------------------------------------------------------------
	# Connection lifecycle
	# ------------------------------------------------------------------
	def _create_ssh(self, **kwargs):
		if paramiko is None:
			raise HPEStorageException("paramiko not installed. Install with 'pip install paramiko'")
		try:
			ssh = paramiko.SSHClient()
			known_hosts_file = kwargs.get('known_hosts_file')
			if known_hosts_file is None:
				ssh.load_system_host_keys()
			else:
				open(known_hosts_file, 'a').close()
				ssh.load_host_keys(known_hosts_file)
			missing_key_policy = kwargs.get('missing_key_policy')
			if missing_key_policy is None:
				missing_key_policy = paramiko.AutoAddPolicy()
			elif isinstance(missing_key_policy, basestring):
				policy_map = {
					paramiko.AutoAddPolicy().__class__.__name__: paramiko.AutoAddPolicy(),
					paramiko.RejectPolicy().__class__.__name__: paramiko.RejectPolicy(),
					paramiko.WarningPolicy().__class__.__name__: paramiko.WarningPolicy(),
				}
				if missing_key_policy in policy_map:
					missing_key_policy = policy_map[missing_key_policy]
				else:
					raise HPEStorageException(f"Invalid missing_key_policy: {missing_key_policy}")
			ssh.set_missing_host_key_policy(missing_key_policy)
			self.ssh = ssh
		except Exception as e:
			msg = f"Error preparing ssh client: {e}"
			self._logger.error(msg)
			raise HPEStorageException(msg)

	def _connect(self):
		if not self.ssh:
			self._create_ssh()
		try:
			if self.san_password:
				self.ssh.connect(
					self.san_ip,
					port=self.san_ssh_port,
					username=self.san_login,
					password=self.san_password,
					timeout=self.ssh_conn_timeout,
				)
			elif self.san_privatekey:
				pkfile = os.path.expanduser(self.san_privatekey)
				pkey = paramiko.RSAKey.from_private_key_file(pkfile)
				self.ssh.connect(
					self.san_ip,
					port=self.san_ssh_port,
					username=self.san_login,
					pkey=pkey,
					timeout=self.ssh_conn_timeout,
				)
			else:
				raise HPEStorageException("Specify a password or private_key")
		except Exception as e:  # pragma: no cover
			msg = f"Error connecting via ssh: {e}"
			self._logger.error(msg)
			raise HPEStorageException(msg)

	def open(self):
		"""Ensure transport is active."""
		if not self.ssh:
			self._create_ssh()
		if not self.ssh.get_transport() or not self.ssh.get_transport().is_active():
			self._connect()
		return self

	def close(self):
		if self.ssh:
			try:
				self.ssh.close()
			finally:
				self.ssh = None

	# ------------------------------------------------------------------
	# Command execution helpers
	# ------------------------------------------------------------------
	@staticmethod
	def _sanitize_cert(output_text):
		# Redact certificate bodies to avoid log noise
		try:
			return re.sub(r'-BEGIN CERTIFICATE-[\s\S]*?-END CERTIFICATE-', '-BEGIN CERTIFICATE- sanitized -END CERTIFICATE-', output_text)
		except Exception:
			return output_text

	@staticmethod
	def _check_injection(command):
		forbidden = ['`', '$(', '|', ';', '&&', '||']
		for token in forbidden:
			if token in command:
				raise HPEStorageException(f"Potential shell injection token '{token}' detected in command")

	def run(self, cmd, split_lines=True, multi_line_stripper=False):  # multi_line_stripper kept for API parity
		"""Execute a command (string or list) over SSH and return output.

		Parameters:
		  cmd: list[str] or str - command and args
		  split_lines: bool - return list of lines (default) else raw string
		"""
		self.open()
		if isinstance(cmd, (list, tuple)):
			command_str = ' '.join(str(c) for c in cmd)
		else:
			command_str = str(cmd)
		self._check_injection(command_str)
		self._logger.debug("SSH CMD = %s", command_str)
		try:
			stdin, stdout, stderr = self.ssh.exec_command(command_str)
			out = stdout.read().decode(errors='replace')
			err = stderr.read().decode(errors='replace')
			if err.strip():
				raise HPEStorageException(f"SSH command error: {err.strip()}")
			cleaned = self._sanitize_cert(out)
			return cleaned.splitlines() if split_lines else cleaned
		except Exception as e:  # pragma: no cover
			raise HPEStorageException(f"SSH execution failed: {e}")


