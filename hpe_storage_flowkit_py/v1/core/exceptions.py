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

class HPEStorageException(Exception):
	def __init__(self, message=None):
		self.message = message or "An unknown HPE Storage exception occurred."
		super().__init__(self.message)

class HTTPForbidden(HPEStorageException):
	def __init__(self, error=None):
		self.error = error
		super().__init__(str(error) if error is not None else None)

class HTTPNotFound(HPEStorageException):
	"""Raised when a requested resource was not found after creation.

	This mirrors the HTTPNotFound used by some upstream SDKs. Accepts an
	optional `error` dict or message string.
	"""
	def __init__(self, error=None):
		self.error = error
		super().__init__(str(error) if error is not None else None)

class HostAlreadyExists(HPEStorageException):
	"""Raised when attempting to create a host that already exists."""
	def __init__(self, name=None, message=None):
		self.name = name
		self.message = message or f"Host Name '{name}' already exists."
		super().__init__(self.message)

class HostDoesNotExist(HPEStorageException):
	def __init__(self, name=None, message=None):
		self.name = name
		self.message = message or f"Host '{name}' does not exist."
		super().__init__(self.message)

class HTTPForbidden(HPEStorageException):
	def __init__(self, error=None):
		self.error = error
		super().__init__(str(error) if error is not None else None)

class HTTPBadRequest(HPEStorageException):
	def __init__(self, error=None):
		self.error = error
		super().__init__(str(error) if error is not None else None)

class HTTPConflict(HPEStorageException):
	def __init__(self, error=None):
		self.error = error
		super().__init__(str(error) if error is not None else None)

class InvalidParameterValue(HPEStorageException):
	"""Raised when provided parameters are invalid."""
	def __init__(self, param=None, message=None):
		self.param = param
		# Allow callers to pass either a full message or a short reason
		if message:
			self.message = f"Invalid parameter value provided for '{param}'. {message}"
		else:
			self.message = f"Invalid parameter value(s) provided for '{param}'"
		super().__init__(self.message)

	def __str__(self):
		return self.message


class HostSetAlreadyExists(HPEStorageException):
	def __init__(self, name=None, message=None):
		self.name = name
		self.message = message or f"Hostset '{name}' already exists."
		super().__init__(self.message)


class HostSetDoesNotExist(HPEStorageException):
	def __init__(self, name=None, message=None):
		self.name = name
		self.message = message or f"Hostset '{name}' does not exist."
		super().__init__(self.message)


class NoNewMembersToAdd(HPEStorageException):
	def __init__(self, name=None, message=None):
		self.name = name
		self.message = message or f"No new members to add to hostset '{name}'."
		super().__init__(self.message)


class NoMembersToRemove(HPEStorageException):
	def __init__(self, name=None, message=None):
		self.name = name
		self.message = message or f"No members to remove from hostset '{name}'."
		super().__init__(self.message)


class ResourceAlreadyExists(HPEStorageException):
	"""Generic exception for idempotent create operations for arbitrary resources."""
	def __init__(self, message=None):
		self.message = message or "Resource already exists."
		super().__init__(self.message)


class ResourceDoesNotExist(HPEStorageException):
	"""Generic exception indicating a resource was not found (idempotent delete/resync)."""
	def __init__(self, message=None):
		self.message = message or "Resource does not exist."
		super().__init__(self.message)


class SSHException(Exception):
    """This is the basis for the SSH Exceptions."""

    code = 500
    message = "An unknown exception occurred."

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        if not message:
            try:
                message = self.message % kwargs

            except Exception:
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception('Exception in string format operation')
                for name, value in list(kwargs.items()):
                    LOG.error("%s: %s" % (name, value))
                # at least get the core message out if something happened
                message = self.message

        self.msg = message
        super(SSHException, self).__init__(message)