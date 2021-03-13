import sys
import os
import unittest

import mock

# TODO: drop in test runner and get rid of this line.
sys.path.append(os.getcwd())  # noqa

from init.questions.question import (Question, InvalidQuestion, InvalidAnswer) # noqa


##############################################################################
#
# Test Fixtures
#
##############################################################################


class InvalidTypeQuestion(Question):
    _type = 'foo'
    config_key = 'invalid-type'


class GoodAutoQuestion(Question):
    _type = 'auto'
    config_key = 'good-auto-question'

    def yes(self, answer):
        return 'I am a good question!'


class GoodBooleanQuestion(Question):
    _type = 'boolean'
    config_key = 'good-bool-question'

    def yes(self, answer):
        return True

    def no(self, answer):
        return False


class GoodStringQuestion(Question):
    """Pass a string through to the output of Question.ask.

    # TODO right now, we have separate handlers for Truthy and Falsey
    answers, and this test class basically makes them do the same
    thing. Is this a good pattern?

    """
    _type = 'string'
    config_key = 'good-string-question'

    def yes(self, answer):
        return answer

    def no(self, answer):
        return answer


##############################################################################
#
# Tests Proper
#
##############################################################################


class TestQuestionClass(unittest.TestCase):
    """
    Test basic features of the Question class.

    """
    def test_invalid_type(self):

        with self.assertRaises(InvalidQuestion):
            InvalidTypeQuestion().ask()

    def test_valid_type(self):

        self.assertTrue(GoodBooleanQuestion())

    @mock.patch('init.questions.question.shell.check_output')
    @mock.patch('init.questions.question.shell.check')
    def test_auto_question(self, mock_check, mock_check_output):
        mock_check_output.return_value = ''

        self.assertEqual(GoodAutoQuestion().ask(), True)


class TestInput(unittest.TestCase):
    """
    Test input handling.

    Takes advantage of the fact that we can override the Question
    class's input handler.

    """
    @mock.patch('init.questions.question.shell.check_output')
    @mock.patch('init.questions.question.shell.check')
    def test_boolean_question(self, mock_check, mock_check_output):
        mock_check_output.return_value = 'true'

        q = GoodBooleanQuestion()

        for answer in ['yes', 'Yes', 'y']:
            q._input_func = lambda x: answer
            self.assertTrue(q.ask())

        for answer in ['No', 'n', 'no']:
            q._input_func = lambda x: answer
            self.assertFalse(q.ask())

        with self.assertRaises(InvalidAnswer):
            q._input_func = lambda x: 'foo'
            q.ask()

    @mock.patch('init.questions.question.shell.check_output')
    @mock.patch('init.questions.question.shell.check')
    def test_string_question(self, mock_check, mock_check_output):
        mock_check_output.return_value = 'somedefault'

        q = GoodStringQuestion()

        for answer in ['foo', 'bar', 'baz', 'yadayadayada']:
            q._input_func = lambda x: answer
            self.assertEqual(answer, q.ask())

        # Verify that a blank answer defaults properly
        q._input_func = lambda x: ''
        self.assertEqual('somedefault', q.ask())


if __name__ == '__main__':
    unittest.main()
