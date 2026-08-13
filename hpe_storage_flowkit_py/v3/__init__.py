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

import sys

# Alias hpe_storage_flowkit_py.v3.src -> hpe_storage_flowkit_py.v3
# This allows: from hpe_storage_flowkit_py.v3.src import module
current_module = sys.modules[__name__]
sys.modules[f'{__name__}.src'] = current_module

# Some tests reference bare "src.*" module paths in @patch(...) targets
# (e.g. @patch('src.workflows.task.time.sleep')). Alias the bare "src"
# namespace to this package so those targets resolve regardless of how the
# tests are launched (submodules resolve via this package's __path__).
sys.modules.setdefault('src', current_module)

# Optional: Add deprecation warning for .src usage
import warnings
warnings.warn(
    "Using '.src' is deprecated. Import directly from 'hpe_storage_flowkit_py.v3' instead.",
    DeprecationWarning,
    stacklevel=2
)
