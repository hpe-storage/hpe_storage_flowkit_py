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
from hpe_storage_flowkit_py.v1.src.validators.cpg_validator import validate_cpg_params
from hpe_storage_flowkit_py.v1.src.utils.volume_utils import convert_to_binary_multiple

# Disk types
disk_types={"FC":1,"NL":2,"SSD":3}
RAID_MAP = {'R0': {'raid_value': 1, 'set_sizes': [1]},
                'R1': {'raid_value': 2, 'set_sizes': [2, 3, 4]},
                'R5': {'raid_value': 3, 'set_sizes': [3, 4, 5, 6, 7, 8, 9]},
                'R6': {'raid_value': 4, 'set_sizes': [6, 8, 10, 12, 16]}
                }
# CPG High Availability
PORT = 1
CAGE = 2
MAG = 3
HA_MAP = {"PORT": PORT, "CAGE": CAGE, "MAG": MAG}

def cpg_ldlayout_map(ldlayout_dict):
		if ldlayout_dict['RAIDType'] is not None and ldlayout_dict['RAIDType']:
			ldlayout_dict['RAIDType'] =RAID_MAP[ldlayout_dict['RAIDType']]['raid_value']
		if ldlayout_dict['HA'] is not None and ldlayout_dict['HA']:
			ldlayout_dict['HA'] = HA_MAP.get(ldlayout_dict['HA'], ldlayout_dict['HA'])
		return ldlayout_dict

def preprocess_create_cpg(name, params):
        """Ansible wrapper with full validation and preprocessing"""

        
        # Ansible-specific validations and preprocessing
        validate_cpg_params(name, params)
        
        if params:
            disk_type = params.get("disk_type")
            raid_type = params.get("raid_type")
            high_availability = params.get("high_availability")
            growth_increment = params.get("growth_increment")
            growth_increment_unit = params.get("growth_increment_unit")
            growth_limit_unit = params.get("growth_limit_unit")
            growth_limit = params.get("growth_limit")
            growth_warning = params.get("growth_warning")
            growth_warning_unit = params.get("growth_warning_unit")
            sdgs = params.get("sdgs")
            sdgw_unit = params.get("sdgw_unit")
            sdgs_unit = params.get("sdgs_unit")
            sdgw = params.get("sdgw")
            domain = params.get("domain")
            
            # Process LD Layout
            ld_layout = dict()
            disk_patterns = []
            if disk_type is not None and disk_type:
                disk_patterns = [{'diskType': disk_types.get(disk_type, None)}]
                ld_layout = {
                    'RAIDType': raid_type,
                    'HA': high_availability,
                    'diskPatterns': disk_patterns
                }
                ld_layout = cpg_ldlayout_map(ld_layout)
            
            # Convert sizes to binary multiples
            if growth_increment is not None:
                growth_increment = convert_to_binary_multiple(growth_increment, growth_increment_unit)
            if growth_limit is not None:
                growth_limit = convert_to_binary_multiple(growth_limit, growth_limit_unit)
            if growth_warning is not None:
                growth_warning = convert_to_binary_multiple(growth_warning, growth_warning_unit)
            if sdgs is not None:
                sdgs = convert_to_binary_multiple(sdgs, sdgs_unit)
            if sdgw is not None:
                sdgw = convert_to_binary_multiple(sdgw, sdgw_unit)
            
            # Build processed parameters for parent class
            processed_params = {
                'domain': domain,
                'growthIncrementMiB': growth_increment if growth_increment != -1.0 else sdgs,
                'growthLimitMiB': growth_limit,
                'usedLDWarningAlertMiB': growth_warning if growth_warning != -1.0 else sdgw,
                'LDLayout': ld_layout
            }
            
            # Remove None values
            processed_params = {k: v for k, v in processed_params.items() if v is not None}
        else:
            processed_params = None
        
     
        return processed_params
            
           
def preprocess_delete_cpg(name):
        """Ansible wrapper with validation"""
        print("Ansible: Deleting CPG...")
        
        # Ansible-specific validations
        validate_cpg_params(name)
        
        return name
