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
import threading

class Logger:
    _instance = None
    _initialized = False
    _lock = threading.Lock()
    
    def __new__(cls, name='flowkit', log_file='flowkit.log', level=logging.INFO):
        """Thread-safe singleton implementation using double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, name='flowkit', log_file='flowkit.log', level=logging.INFO):
        """Initialize logger only once (singleton pattern)."""
        # Only initialize once, even if __init__ is called multiple times
        if not Logger._initialized:
            with Logger._lock:
                # Double-check after acquiring lock
                if not Logger._initialized:
                    self.logger = logging.getLogger(name)
                    self.logger.setLevel(level)
                    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')

                    # Avoid duplicate handlers if Logger is instantiated multiple times
                    if not self.logger.handlers:
                        # Console handler
                        ch = logging.StreamHandler()
                        ch.setFormatter(formatter)
                        ch.setLevel(level)
                        self.logger.addHandler(ch)

                        # File handler
                        fh = logging.FileHandler(log_file, encoding='utf-8')
                        fh.setFormatter(formatter)
                        fh.setLevel(level)
                        self.logger.addHandler(fh)
                    
                    Logger._initialized = True
    
    def set_level(self, level):
        """Update the log level for the singleton logger and all its handlers."""
        with Logger._lock:
            self.logger.setLevel(level)
            for handler in self.logger.handlers:
                handler.setLevel(level)

    def set_log_file(self, new_log_file):
        """
        Change the log file path dynamically.
        
        Args:
            new_log_file (str): Path to the new log file
        
        This method will:
        - Remove the existing file handler
        - Create a new file handler with the new file path
        - Preserve the current log level and formatter
        """
        with Logger._lock:
            # Get current log level
            current_level = self.logger.level
            
            # Find and remove existing file handler (only one exists)
            for handler in self.logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    try:
                        handler.close()
                    finally:
                        self.logger.removeHandler(handler)
                    break  # Only one file handler exists
            
            # Create new file handler with current formatter and level
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
            new_fh = logging.FileHandler(new_log_file, encoding='utf-8')
            new_fh.setFormatter(formatter)
            new_fh.setLevel(current_level)
            self.logger.addHandler(new_fh)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def debug(self, msg):
        self.logger.debug(msg)

    def exception(self, msg):
        self.logger.exception(msg)