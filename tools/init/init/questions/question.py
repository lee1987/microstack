"""question.py

Contains our Question class, which knows how to ask a question, then
run abitrary code.

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


from typing import Tuple

from init import shell


class InvalidQuestion(Exception):
    """Exception to raies in the case where a Question subclass has not
    been properly implemented.

    """


class InvalidAnswer(Exception):
    """Exception to raise in the case where the user has specified an
    invalid answer.

    """


class AnswerNotImplemented(Exception):
    """Exception to raise in the case where a 'yes' or 'no' routine has
    not been overriden in the subclass, as required.

    """


class Question():
    """
    Ask the user a question, and then run code as appropriate.

    Contains a support for always defaulting to yes.

    """
    _valid_types = [
        'boolean',  # Yes or No, and variants thereof
        'string',  # Accept (and sanitize) any string
        'auto'  # Don't actually ask a question -- just execute self.yes(True)
    ]

    _question = '(required)'
    config_key = None  # Must be overriden
    interactive = False
    _type = 'auto'  # can be boolean, string or auto
    _invalid_prompt = 'Please answer Yes or No.'
    _retries = 3

    def __init__(self):

        if self._type not in ['boolean', 'string', 'auto']:
            raise InvalidQuestion(
                'Invalid type {} specified'.format(self._type))

        if self.config_key is None and self._type != 'auto':
            raise InvalidQuestion(
                "No config key specified. "
                "We don't know how to load or save this question!")

    def _input_func(self, prompt):

        if not self.interactive:
            return
        return input(prompt)

    def _validate(self, answer: str) -> Tuple[str, bool]:
        """Validate an answer.

        :param anwser: raw input from the user.

        Returns the answer, and whether or not the answer was valid.

        """
        if self._type == 'auto':
            return True, True

        if self._type == 'string':
            # Allow people to negate a string by passing nil.
            if answer.lower() == 'nil':
                return None, True
            return answer, True

        # self._type is boolean
        if answer.lower() in ['y', 'yes']:
            return True, True

        if answer.lower() in ['n', 'no']:
            return False, True

        return answer, False

    def _load(self):
        """Get the current value of the answer to this question.

        Useful for loading defaults during init, and for loading
        operator specified settings during updates.

        """
        if self._type == 'auto':
            return

        answer = shell.check_output(
            'snapctl', 'get', '{key}'.format(key=self.config_key)
        )
        # Convert boolean values in to human friendly "yes" or "no"
        # values.
        if answer.strip().lower() == 'true':
            answer = 'yes'
        if answer.strip().lower() == 'false':
            answer = 'no'

        # Convert null to None
        if answer.strip().lower() == 'null':
            answer = None

        return answer

    def _save(self, answer):
        """Save off our answer, for later retrieval.

        Store the value of this question's answer in the questions
        namespace in the snap config.

        """
        # By this time in the process 'yes' or 'no' answers will have
        # been converted to booleans. Convert them to a lowercase
        # 'true' or 'false' string for storage in the snapctl config.
        if self._type == 'auto':
            return

        if self._type == 'boolean':
            answer = str(answer).lower()

        if answer is None:
            answer = 'null'

        shell.check('snapctl', 'set', '{key}={val}'.format(
            key=self.config_key, val=answer))

        return answer

    def yes(self, answer: str) -> None:
        """Routine to run if the user answers 'yes' or with a value.

        Can be a noop.

        """
        pass

    def no(self, answer: str) -> None:
        """Routine to run if the user answers 'no'

        Can be a noop.

        """
        pass

    def after(self, answer: str) -> None:
        """Routine to run after the answer has been saved to snapctl config.

        Can be a noop.

        """
        pass

    def ask(self) -> None:
        """Ask the user a question.

        Run self.yes or self.no as appropriate. Raise an error if the
        user cannot specify a valid answer after self._retries tries.

        Save off the answer for later retrieval, and run any cleanup
        routines.

        """
        default = self._load()

        prompt = "{question}{choice}[default={default}] > ".format(
            question=self._question,
            choice=' (yes/no) ' if self._type == 'boolean' else ' ',
            default=default)

        for i in range(0, self._retries):
            awr, valid = self._validate(
                self._type == 'auto' or self._input_func(prompt) or default)
            if valid:
                if awr:
                    self.yes(awr)
                else:
                    self.no(awr)
                self._save(awr)
                self.after(awr)
                return awr
            prompt = '{} is not valid. {} > '.format(awr, self._invalid_prompt)

        raise InvalidAnswer('Too many invalid answers.')
