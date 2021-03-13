"""config.py

Keep track of shared config, logging, etc. here.

----------------------------------------------------------------------

Copyright 2019 Canonical Ltd

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
import logging
import os


# Setup logging
log = logging.getLogger("microstack_init")
log.setLevel(logging.INFO)
stream = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream.setFormatter(formatter)
log.addHandler(stream)


class Env():
    """Singleton that tracks environment variables.

    Contains the env variables of the shell that called us. We also
    add the snapctl config values to it in the Setup Question.

    """
    _global_config = {}
    _global_config.update(**os.environ)

    def __init__(self):
        self.__dict__ = self._global_config

    def get_env(self):
        """Get a mapping friendly dict."""
        return self.__dict__
