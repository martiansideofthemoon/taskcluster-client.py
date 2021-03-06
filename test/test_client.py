from __future__ import division, print_function
import types
import unittest
import time
import datetime
from six.moves import urllib
import os
import re
import json

import mock
import httmock
import requests

import base
import taskcluster.client as subject
import taskcluster.runtimeclient as rtclient
import taskcluster.exceptions as exc
import taskcluster.utils as utils


class ClientTest(base.TCTest):
    realTimeSleep = time.sleep

    def setUp(self):
        subject.config['credentials'] = {
            'clientId': 'clientId',
            'accessToken': 'accessToken',
        }
        keys = [
            base.createTopicExchangeKey('primary_key', constant='primary'),
            base.createTopicExchangeKey('norm1'),
            base.createTopicExchangeKey('norm2'),
            base.createTopicExchangeKey('norm3'),
            base.createTopicExchangeKey('multi_key', multipleWords=True),
        ]
        topicEntry = base.createApiEntryTopicExchange('topicName', 'topicExchange', routingKey=keys)
        entries = [
            base.createApiEntryFunction('no_args_no_input', 0, False),
            base.createApiEntryFunction('two_args_no_input', 2, False),
            base.createApiEntryFunction('no_args_with_input', 0, True),
            base.createApiEntryFunction('two_args_with_input', 2, True),
            base.createApiEntryFunction('NEVER_CALL_ME', 0, False),
            topicEntry
        ]
        self.apiRef = base.createApiRef(entries=entries)
        self.clientClass = subject.createApiClient('testApi', self.apiRef)
        self.client = self.clientClass()
        # Patch time.sleep so that we don't delay tests
        sleepPatcher = mock.patch('time.sleep')
        sleepSleep = sleepPatcher.start()
        sleepSleep.return_value = None
        self.addCleanup(sleepSleep.stop)

    def tearDown(self):
        time.sleep = self.realTimeSleep


class TestSubArgsInRoute(ClientTest):

    def test_valid_no_subs(self):
        provided = {'route': '/no/args/here', 'name': 'test'}
        expected = 'no/args/here'
        result = self.client._subArgsInRoute(provided, {})
        self.assertEqual(expected, result)

    def test_valid_one_sub(self):
        provided = {'route': '/one/<argToSub>/here', 'name': 'test'}
        expected = 'one/value/here'
        arguments = {'argToSub': 'value'}
        result = self.client._subArgsInRoute(provided, arguments)
        self.assertEqual(expected, result)

    def test_invalid_one_sub(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._subArgsInRoute({
                'route': '/one/<argToSub>/here',
                'name': 'test'
            }, {'unused': 'value'})

    def test_invalid_route_no_sub(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._subArgsInRoute({
                'route': 'askldjflkasdf',
                'name': 'test'
            }, {'should': 'fail'})

    def test_invalid_route_no_arg(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._subArgsInRoute({
                'route': 'askldjflkasdf',
                'name': 'test'
            }, {'should': 'fail'})


class TestProcessArgs(ClientTest):

    def test_no_args(self):
        self.assertEqual({}, self.client._processArgs({'args': [], 'name': 'test'}))

    def test_positional_args_only(self):
        expected = {'test': 'works', 'test2': 'still works'}
        entry = {'args': ['test', 'test2'], 'name': 'test'}
        actual = self.client._processArgs(entry, 'works', 'still works')
        self.assertEqual(expected, actual)

    def test_keyword_args_only(self):
        expected = {'test': 'works', 'test2': 'still works'}
        entry = {'args': ['test', 'test2'], 'name': 'test'}
        actual = self.client._processArgs(entry, test2='still works', test='works')
        self.assertEqual(expected, actual)

    def test_int_args(self):
        expected = {'test': 'works', 'test2': 42}
        entry = {'args': ['test', 'test2'], 'name': 'test'}
        actual = self.client._processArgs(entry, 'works', 42)
        self.assertEqual(expected, actual)

    def test_keyword_and_positional(self):
        entry = {'args': ['test'], 'name': 'test'}
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._processArgs(entry, 'broken', test='works')

    def test_invalid_not_enough_args(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._processArgs({'args': ['test'], 'name': 'test'})

    def test_invalid_too_many_positional_args(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._processArgs({'args': ['test'], 'name': 'test'}, 'enough', 'one too many')

    def test_invalid_too_many_keyword_args(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._processArgs({
                'args': ['test'],
                'name': 'test'
            }, test='enough', test2='one too many')

    def test_invalid_missing_arg_positional(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._processArgs({'args': ['test', 'test2'], 'name': 'test'}, 'enough')

    def test_invalid_not_enough_args_because_of_overwriting(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._processArgs({
                'args': ['test', 'test2'],
                'name': 'test'
            }, 'enough', test='enough')

    def test_invalid_positional_not_string_empty_dict(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._processArgs({'args': ['test'], 'name': 'test'}, {})

    def test_invalid_positional_not_string_non_empty_dict(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client._processArgs({'args': ['test'], 'name': 'test'}, {'john': 'ford'})


# This could probably be done better with Mock
class ObjWithDotJson(object):

    def __init__(self, status_code, x):
        self.status_code = status_code
        self.x = x

    def json(self):
        return self.x

    def raise_for_status(self):
        if self.status_code >= 300 or self.status_code < 200:
            raise requests.exceptions.HTTPError()


class TestMakeHttpRequest(ClientTest):

    def setUp(self):

        ClientTest.setUp(self)

    def test_success_first_try(self):
        with mock.patch.object(utils, 'makeSingleHttpRequest') as p:
            expected = {'test': 'works'}
            p.return_value = ObjWithDotJson(200, expected)

            v = self.client._makeHttpRequest('GET', 'http://www.example.com', None)
            p.assert_called_once_with('GET', 'http://www.example.com', None, mock.ANY)
            self.assertEqual(expected, v)

    def test_success_first_try_payload(self):
        with mock.patch.object(utils, 'makeSingleHttpRequest') as p:
            expected = {'test': 'works'}
            p.return_value = ObjWithDotJson(200, expected)

            v = self.client._makeHttpRequest('GET', 'http://www.example.com', {'payload': 2})
            p.assert_called_once_with('GET', 'http://www.example.com',
                                      utils.dumpJson({'payload': 2}), mock.ANY)
            self.assertEqual(expected, v)

    def test_success_fifth_try_status_code(self):
        with mock.patch.object(utils, 'makeSingleHttpRequest') as p:
            expected = {'test': 'works'}
            sideEffect = [
                ObjWithDotJson(500, None),
                ObjWithDotJson(500, None),
                ObjWithDotJson(500, None),
                ObjWithDotJson(500, None),
                ObjWithDotJson(200, expected)
            ]
            p.side_effect = sideEffect
            expectedCalls = [mock.call('GET', 'http://www.example.com', None, mock.ANY)
                             for x in range(self.client.options['maxRetries'])]

            v = self.client._makeHttpRequest('GET', 'http://www.example.com', None)
            p.assert_has_calls(expectedCalls)
            self.assertEqual(expected, v)

    def test_exhaust_retries_try_status_code(self):
        with mock.patch.object(utils, 'makeSingleHttpRequest') as p:
            msg = {'message': 'msg', 'test': 'works'}
            sideEffect = [
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),  # exhaust retries
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),
                ObjWithDotJson(500, msg),
                ObjWithDotJson(200, {'got this': 'wrong'})
            ]
            p.side_effect = sideEffect
            expectedCalls = [mock.call('GET', 'http://www.example.com', None, mock.ANY)
                             for x in range(self.client.options['maxRetries'] + 1)]

            with self.assertRaises(exc.TaskclusterRestFailure):
                try:
                    self.client._makeHttpRequest('GET', 'http://www.example.com', None)
                except exc.TaskclusterRestFailure as err:
                    self.assertEqual('msg', str(err))
                    self.assertEqual(500, err.status_code)
                    self.assertEqual(msg, err.body)
                    raise err
            p.assert_has_calls(expectedCalls)

    def test_success_fifth_try_connection_errors(self):
        with mock.patch.object(utils, 'makeSingleHttpRequest') as p:
            expected = {'test': 'works'}
            sideEffect = [
                requests.exceptions.RequestException,
                requests.exceptions.RequestException,
                requests.exceptions.RequestException,
                requests.exceptions.RequestException,
                ObjWithDotJson(200, expected)
            ]
            p.side_effect = sideEffect
            expectedCalls = [mock.call('GET', 'http://www.example.com', None, mock.ANY)
                             for x in range(self.client.options['maxRetries'])]

            v = self.client._makeHttpRequest('GET', 'http://www.example.com', None)
            p.assert_has_calls(expectedCalls)
            self.assertEqual(expected, v)

    def test_failure_status_code(self):
        with mock.patch.object(utils, 'makeSingleHttpRequest') as p:
            p.return_value = ObjWithDotJson(500, None)
            expectedCalls = [mock.call('GET', 'http://www.example.com', None, mock.ANY)
                             for x in range(self.client.options['maxRetries'])]
            with self.assertRaises(exc.TaskclusterRestFailure):
                self.client._makeHttpRequest('GET', 'http://www.example.com', None)
            p.assert_has_calls(expectedCalls)

    def test_failure_connection_errors(self):
        with mock.patch.object(utils, 'makeSingleHttpRequest') as p:
            p.side_effect = requests.exceptions.RequestException
            expectedCalls = [mock.call('GET', 'http://www.example.com', None, mock.ANY)
                             for x in range(self.client.options['maxRetries'])]
            with self.assertRaises(exc.TaskclusterConnectionError):
                self.client._makeHttpRequest('GET', 'http://www.example.com', None)
            p.assert_has_calls(expectedCalls)


class TestOptions(ClientTest):

    def setUp(self):
        ClientTest.setUp(self)
        self.clientClass2 = subject.createApiClient('testApi', base.createApiRef())
        self.client2 = self.clientClass2({'baseUrl': 'http://notlocalhost:5888/v2'})

    def test_defaults_should_work(self):
        self.assertEqual(self.client.options['baseUrl'], 'https://fake.taskcluster.net/v1')
        self.assertEqual(self.client2.options['baseUrl'], 'http://notlocalhost:5888/v2')

    def test_change_default_doesnt_change_previous_instances(self):
        prevMaxRetries = subject._defaultConfig['maxRetries']
        with mock.patch.dict(subject._defaultConfig, {'maxRetries': prevMaxRetries + 1}):
            self.assertEqual(self.client.options['maxRetries'], prevMaxRetries)

    def test_credentials_which_cannot_be_encoded_in_unicode_work(self):
        badCredentials = {
            'accessToken': u"\U0001F4A9",
            'clientId': u"\U0001F4A9",
        }
        with self.assertRaises(exc.TaskclusterAuthFailure):
            subject.Index({'credentials': badCredentials})


class TestMakeApiCall(ClientTest):
    """ This class covers both the _makeApiCall function logic as well as the
    logic involved in setting up the api member functions since these are very
    related things"""

    def setUp(self):
        ClientTest.setUp(self)
        patcher = mock.patch.object(self.client, 'NEVER_CALL_ME')
        never_call = patcher.start()
        never_call.side_effect = AssertionError
        self.addCleanup(never_call.stop)

    def test_creates_methods(self):
        self.assertIsInstance(self.client.no_args_no_input, types.MethodType)

    def test_methods_setup_correctly(self):
        # Because of how scoping works, I've had trouble where the last API Entry
        # dict is used for all entires, which is wrong.  This is to make sure that
        # the scoping stuff isn't broken
        self.assertIsNot(self.client.NEVER_CALL_ME, self.client.no_args_no_input)

    def test_hits_no_args_no_input(self):
        expected = 'works'
        with mock.patch.object(self.client, '_makeHttpRequest') as patcher:
            patcher.return_value = expected

            actual = self.client.no_args_no_input()
            self.assertEqual(expected, actual)

            patcher.assert_called_once_with('get', 'no_args_no_input', None)

    def test_hits_two_args_no_input(self):
        expected = 'works'
        with mock.patch.object(self.client, '_makeHttpRequest') as patcher:
            patcher.return_value = expected

            actual = self.client.two_args_no_input('argone', 'argtwo')
            self.assertEqual(expected, actual)

            patcher.assert_called_once_with('get', 'two_args_no_input/argone/argtwo', None)

    def test_hits_no_args_with_input(self):
        expected = 'works'
        with mock.patch.object(self.client, '_makeHttpRequest') as patcher:
            patcher.return_value = expected

            actual = self.client.no_args_with_input({})
            self.assertEqual(expected, actual)

            patcher.assert_called_once_with('get', 'no_args_with_input', {})

    def test_hits_two_args_with_input(self):
        expected = 'works'
        with mock.patch.object(self.client, '_makeHttpRequest') as patcher:
            patcher.return_value = expected

            actual = self.client.two_args_with_input('argone', 'argtwo', {})
            self.assertEqual(expected, actual)

            patcher.assert_called_once_with('get', 'two_args_with_input/argone/argtwo', {})

    def test_input_is_procesed(self):
        expected = 'works'
        expected_input = {'test': 'does work'}
        with mock.patch.object(self.client, '_makeHttpRequest') as patcher:
            patcher.return_value = expected

            actual = self.client.no_args_with_input(expected_input)
            self.assertEqual(expected, actual)

            patcher.assert_called_once_with('get', 'no_args_with_input', expected_input)

    def test_kwargs(self):
        expected = 'works'
        with mock.patch.object(self.client, '_makeHttpRequest') as patcher:
            patcher.return_value = expected

            actual = self.client.two_args_with_input({}, arg0='argone', arg1='argtwo')
            self.assertEqual(expected, actual)

            patcher.assert_called_once_with('get', 'two_args_with_input/argone/argtwo', {})

    def test_mixing_kw_and_positional_fails(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client.two_args_no_input('arg1', arg2='arg2')

    def test_missing_input_raises(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client.no_args_with_input()


# TODO: I should run the same things through the node client and compare the output
class TestTopicExchange(ClientTest):

    def test_string_pass_through(self):
        expected = 'johnwrotethis'
        actual = self.client.topicName(expected)
        self.assertEqual(expected, actual['routingKeyPattern'])

    def test_exchange(self):
        expected = 'test/v1/topicExchange'
        actual = self.client.topicName('')
        self.assertEqual(expected, actual['exchange'])

    def test_exchange_trailing_slash(self):
        self.client.options['exchangePrefix'] = 'test/v1/'
        expected = 'test/v1/topicExchange'
        actual = self.client.topicName('')
        self.assertEqual(expected, actual['exchange'])

    def test_constant(self):
        expected = 'primary.*.*.*.#'
        actual = self.client.topicName({})
        self.assertEqual(expected, actual['routingKeyPattern'])

    def test_does_insertion(self):
        expected = 'primary.*.value2.*.#'
        actual = self.client.topicName({'norm2': 'value2'})
        self.assertEqual(expected, actual['routingKeyPattern'])

    def test_too_many_star_args(self):
        with self.assertRaises(exc.TaskclusterTopicExchangeFailure):
            self.client.topicName({'taskId': '123'}, 'another')

    def test_both_args_and_kwargs(self):
        with self.assertRaises(exc.TaskclusterTopicExchangeFailure):
            self.client.topicName({'taskId': '123'}, taskId='123')

    def test_no_args_no_kwargs(self):
        expected = 'primary.*.*.*.#'
        actual = self.client.topicName()
        self.assertEqual(expected, actual['routingKeyPattern'])
        actual = self.client.topicName({})
        self.assertEqual(expected, actual['routingKeyPattern'])


class TestBuildUrl(ClientTest):

    def test_build_url_positional(self):
        expected = 'https://fake.taskcluster.net/v1/two_args_no_input/arg0/arg1'
        actual = self.client.buildUrl('two_args_no_input', 'arg0', 'arg1')
        self.assertEqual(expected, actual)

    def test_build_url_keyword(self):
        expected = 'https://fake.taskcluster.net/v1/two_args_no_input/arg0/arg1'
        actual = self.client.buildUrl('two_args_no_input', arg0='arg0', arg1='arg1')
        self.assertEqual(expected, actual)

    def test_fails_to_build_url_for_missing_method(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client.buildUrl('non-existing')

    def test_fails_to_build_not_enough_args(self):
        with self.assertRaises(exc.TaskclusterFailure):
            self.client.buildUrl('two_args_no_input', 'not-enough-args')


class TestBuildSignedUrl(ClientTest):

    def test_builds_surl_positional(self):
        expected = 'https://fake.taskcluster.net/v1/two_args_no_input/arg0/arg1?bewit=X'
        actual = self.client.buildSignedUrl('two_args_no_input', 'arg0', 'arg1')
        actual = re.sub('bewit=[^&]*', 'bewit=X', actual)
        self.assertEqual(expected, actual)

    def test_builds_surl_keyword(self):
        expected = 'https://fake.taskcluster.net/v1/two_args_no_input/arg0/arg1?bewit=X'
        actual = self.client.buildSignedUrl('two_args_no_input', arg0='arg0', arg1='arg1')
        actual = re.sub('bewit=[^&]*', 'bewit=X', actual)
        self.assertEqual(expected, actual)


class TestMockHttpCalls(ClientTest):

    """Test entire calls down to the requests layer, ensuring they have
    well-formed URLs and handle request and response bodies properly.  This
    verifies that we can call real methods with both position and keyword
    args"""

    def setUp(self):
        ClientTest.setUp(self)
        self.fakeResponse = ''

        def fakeSite(url, request):
            self.gotUrl = urllib.parse.urlunsplit(url)
            self.gotRequest = request
            return self.fakeResponse
        self.fakeSite = fakeSite

    def test_no_args_no_input(self):
        with httmock.HTTMock(self.fakeSite):
            self.client.no_args_no_input()
        self.assertEqual(self.gotUrl, 'https://fake.taskcluster.net/v1/no_args_no_input')

    def test_two_args_no_input(self):
        with httmock.HTTMock(self.fakeSite):
            self.client.two_args_no_input('1', '2')
        self.assertEqual(self.gotUrl, 'https://fake.taskcluster.net/v1/two_args_no_input/1/2')

    def test_no_args_with_input(self):
        with httmock.HTTMock(self.fakeSite):
            self.client.no_args_with_input({'x': 1})
        self.assertEqual(self.gotUrl, 'https://fake.taskcluster.net/v1/no_args_with_input')
        self.assertEqual(json.loads(self.gotRequest.body), {"x": 1})

    def test_no_args_with_empty_input(self):
        with httmock.HTTMock(self.fakeSite):
            self.client.no_args_with_input({})
        self.assertEqual(self.gotUrl, 'https://fake.taskcluster.net/v1/no_args_with_input')
        self.assertEqual(json.loads(self.gotRequest.body), {})

    def test_two_args_with_input(self):
        with httmock.HTTMock(self.fakeSite):
            self.client.two_args_with_input('a', 'b', {'x': 1})
        self.assertEqual(self.gotUrl,
                         'https://fake.taskcluster.net/v1/two_args_with_input/a/b')
        self.assertEqual(json.loads(self.gotRequest.body), {"x": 1})

    def test_kwargs(self):
        with httmock.HTTMock(self.fakeSite):
            self.client.two_args_with_input(
                {'x': 1}, arg0='a', arg1='b')
        self.assertEqual(self.gotUrl,
                         'https://fake.taskcluster.net/v1/two_args_with_input/a/b')
        self.assertEqual(json.loads(self.gotRequest.body), {"x": 1})


class BaseAuthentication(base.TCTest):
    """Base Authentication test class, for integration testing.

    This will be run against both the runtime- and buildtime- generated
    Auth classes.

    The methods don't begin with test_ because nosetests sniff those out.
    """

    def testClass(self, *args, **kwargs):
        """Define this with Auth
        """
        pass

    def no_creds_needed(self):
        """we can call methods which require no scopes with an unauthenticated
        client"""
        # mock this request so we don't depend on the existence of a client
        @httmock.all_requests
        def auth_response(url, request):
            self.assertEqual(urllib.parse.urlunsplit(url),
                             'https://auth.taskcluster.net/v1/clients/abc')
            self.failIf('Authorization' in request.headers)
            headers = {'content-type': 'application/json'}
            content = {"clientId": "abc"}
            return httmock.response(200, content, headers, None, 5, request)

        with httmock.HTTMock(auth_response):
            client = self.testClass({"credentials": {}})
            result = client.client('abc')
            self.assertEqual(result, {"clientId": "abc"})

    def permacred_simple(self):
        """we can call methods which require authentication with valid
        permacreds"""
        client = self.testClass({
            'credentials': {
                'clientId': 'tester',
                'accessToken': 'no-secret',
            }
        })
        result = client.testAuthenticate({
            'clientScopes': ['test:a'],
            'requiredScopes': ['test:a'],
        })
        self.assertEqual(result, {'scopes': ['test:a'], 'clientId': 'tester'})

    def permacred_simple_authorizedScopes(self):
        client = self.testClass({
            'credentials': {
                'clientId': 'tester',
                'accessToken': 'no-secret',
            },
            'authorizedScopes': ['test:a', 'test:b'],
        })
        result = client.testAuthenticate({
            'clientScopes': ['test:*'],
            'requiredScopes': ['test:a'],
        })
        self.assertEqual(result, {'scopes': ['test:a', 'test:b'],
                                  'clientId': 'tester'})

    def unicode_permacred_simple(self):
        """Unicode strings that encode to ASCII in credentials do not cause issues"""
        client = self.testClass({
            'credentials': {
                'clientId': u'tester',
                'accessToken': u'no-secret',
            }
        })
        result = client.testAuthenticate({
            'clientScopes': ['test:a'],
            'requiredScopes': ['test:a'],
        })
        self.assertEqual(result, {'scopes': ['test:a'], 'clientId': 'tester'})

    def invalid_unicode_permacred_simple(self):
        """Unicode strings that do not encode to ASCII in credentials cause issues"""
        with self.assertRaises(exc.TaskclusterAuthFailure):
            self.testClass({
                'credentials': {
                    'clientId': u"\U0001F4A9",
                    'accessToken': u"\U0001F4A9",
                }
            })

    def permacred_insufficient_scopes(self):
        """A call with insufficient scopes results in an error"""
        client = self.testClass({
            'credentials': {
                'clientId': 'tester',
                'accessToken': 'no-secret',
            }
        })
        # TODO: this should be TaskclsuterAuthFailure; most likely the client
        # is expecting AuthorizationFailure instead of AuthenticationFailure
        with self.assertRaises(exc.TaskclusterRestFailure):
            client.testAuthenticate({
                'clientScopes': ['test:*'],
                'requiredScopes': ['something-more'],
            })

    def temporary_credentials(self):
        """we can call methods which require authentication with temporary
        credentials generated by python client"""
        tempCred = subject.createTemporaryCredentials(
            'tester',
            'no-secret',
            datetime.datetime.utcnow() - datetime.timedelta(hours=10),
            datetime.datetime.utcnow() + datetime.timedelta(hours=10),
            ['test:xyz'],
        )
        client = self.testClass({
            'credentials': tempCred,
        })

        result = client.testAuthenticate({
            'clientScopes': ['test:*'],
            'requiredScopes': ['test:xyz'],
        })
        self.assertEqual(result, {'scopes': ['test:xyz'], 'clientId': 'tester'})

    def named_temporary_credentials(self):
        tempCred = subject.createTemporaryCredentials(
            'tester',
            'no-secret',
            datetime.datetime.utcnow() - datetime.timedelta(hours=10),
            datetime.datetime.utcnow() + datetime.timedelta(hours=10),
            ['test:xyz'],
            name='credName'
        )
        client = self.testClass({
            'credentials': tempCred,
        })

        result = client.testAuthenticate({
            'clientScopes': ['test:*', 'auth:create-client:credName'],
            'requiredScopes': ['test:xyz'],
        })
        self.assertEqual(result, {'scopes': ['test:xyz'], 'clientId': 'credName'})

    def temporary_credentials_authorizedScopes(self):
        tempCred = subject.createTemporaryCredentials(
            'tester',
            'no-secret',
            datetime.datetime.utcnow() - datetime.timedelta(hours=10),
            datetime.datetime.utcnow() + datetime.timedelta(hours=10),
            ['test:xyz:*'],
        )
        client = self.testClass({
            'credentials': tempCred,
            'authorizedScopes': ['test:xyz:abc'],
        })

        result = client.testAuthenticate({
            'clientScopes': ['test:*'],
            'requiredScopes': ['test:xyz:abc'],
        })
        self.assertEqual(result, {'scopes': ['test:xyz:abc'],
                                  'clientId': 'tester'})

    def named_temporary_credentials_authorizedScopes(self):
        tempCred = subject.createTemporaryCredentials(
            'tester',
            'no-secret',
            datetime.datetime.utcnow() - datetime.timedelta(hours=10),
            datetime.datetime.utcnow() + datetime.timedelta(hours=10),
            ['test:xyz:*'],
            name='credName'
        )
        client = self.testClass({
            'credentials': tempCred,
            'authorizedScopes': ['test:xyz:abc'],
        })

        result = client.testAuthenticate({
            'clientScopes': ['test:*', 'auth:create-client:credName'],
            'requiredScopes': ['test:xyz:abc'],
        })
        self.assertEqual(result, {'scopes': ['test:xyz:abc'],
                                  'clientId': 'credName'})

    def signed_url(self):
        """we can use a signed url built with the python client"""
        client = self.testClass({
            'credentials': {
                'clientId': 'tester',
                'accessToken': 'no-secret',
            }
        })
        signedUrl = client.buildSignedUrl(methodName='testAuthenticateGet')
        response = requests.get(signedUrl)
        response.raise_for_status()
        response = response.json()
        response['scopes'].sort()
        self.assertEqual(response, {
            'scopes': sorted(['test:*', u'auth:create-client:test:*']),
            'clientId': 'tester',
        })

    def signed_url_bad_credentials(self):
        client = self.testClass({
            'credentials': {
                'clientId': 'tester',
                'accessToken': 'wrong-secret',
            }
        })
        signedUrl = client.buildSignedUrl(methodName='testAuthenticateGet')
        response = requests.get(signedUrl)
        with self.assertRaises(requests.exceptions.RequestException):
            response.raise_for_status()
        self.assertEqual(401, response.status_code)

    def temp_credentials_signed_url(self):
        tempCred = subject.createTemporaryCredentials(
            'tester',
            'no-secret',
            datetime.datetime.utcnow() - datetime.timedelta(hours=10),
            datetime.datetime.utcnow() + datetime.timedelta(hours=10),
            ['test:*'],
        )
        client = self.testClass({
            'credentials': tempCred,
        })
        signedUrl = client.buildSignedUrl(methodName='testAuthenticateGet')
        response = requests.get(signedUrl)
        response.raise_for_status()
        response = response.json()
        self.assertEqual(response, {
            'scopes': ['test:*'],
            'clientId': 'tester',
        })

    def signed_url_authorizedScopes(self):
        client = self.testClass({
            'credentials': {
                'clientId': 'tester',
                'accessToken': 'no-secret',
            },
            'authorizedScopes': ['test:authenticate-get'],
        })
        signedUrl = client.buildSignedUrl(methodName='testAuthenticateGet')
        response = requests.get(signedUrl)
        response.raise_for_status()
        response = response.json()
        self.assertEqual(response, {
            'scopes': ['test:authenticate-get'],
            'clientId': 'tester',
        })

    def temp_credentials_signed_url_authorizedScopes(self):
        tempCred = subject.createTemporaryCredentials(
            'tester',
            'no-secret',
            datetime.datetime.utcnow() - datetime.timedelta(hours=10),
            datetime.datetime.utcnow() + datetime.timedelta(hours=10),
            ['test:*'],
        )
        client = self.testClass({
            'credentials': tempCred,
            'authorizedScopes': ['test:authenticate-get'],
        })
        signedUrl = client.buildSignedUrl(methodName='testAuthenticateGet')
        response = requests.get(signedUrl)
        response.raise_for_status()
        response = response.json()
        self.assertEqual(response, {
            'scopes': ['test:authenticate-get'],
            'clientId': 'tester',
        })


@unittest.skipIf(os.environ.get('NO_TESTS_OVER_WIRE'), "Skipping tests over wire")
class TestRuntimeAuthentication(BaseAuthentication):

    @property
    def testClass(self):
        return rtclient.createApiClient('Auth', base.APIS_JSON['Auth'])

    def test_no_creds_needed(self):
        self.no_creds_needed()

    def test_permacred_simple(self):
        self.permacred_simple()

    def test_permacred_simple_authorizedScopes(self):
        self.permacred_simple_authorizedScopes()

    def test_unicode_permacred_simple(self):
        self.unicode_permacred_simple()

    def test_invalid_unicode_permacred_simple(self):
        self.invalid_unicode_permacred_simple()

    def test_permacred_insufficient_scopes(self):
        self.permacred_insufficient_scopes()

    def test_temporary_credentials(self):
        self.temporary_credentials()

    def test_named_temporary_credentials(self):
        self.named_temporary_credentials()

    def test_temporary_credentials_authorizedScopes(self):
        self.temporary_credentials_authorizedScopes()

    def test_named_temporary_credentials_authorizedScopes(self):
        self.named_temporary_credentials_authorizedScopes()

    def test_signed_url(self):
        self.signed_url()

    def test_signed_url_bad_credentials(self):
        self.signed_url_bad_credentials()

    def test_temp_credentials_signed_url(self):
        self.temp_credentials_signed_url()

    def test_signed_url_authorizedScopes(self):
        self.signed_url_authorizedScopes()

    def test_temp_credentials_signed_url_authorizedScopes(self):
        self.temp_credentials_signed_url_authorizedScopes()


@unittest.skipIf(os.environ.get('NO_TESTS_OVER_WIRE'), "Skipping tests over wire")
class TestBuildtimeAuthentication(BaseAuthentication):

    testClass = subject.Auth

    def test_no_creds_needed(self):
        self.no_creds_needed()

    def test_permacred_simple(self):
        self.permacred_simple()

    def test_permacred_simple_authorizedScopes(self):
        self.permacred_simple_authorizedScopes()

    def test_unicode_permacred_simple(self):
        self.unicode_permacred_simple()

    def test_invalid_unicode_permacred_simple(self):
        self.invalid_unicode_permacred_simple()

    def test_permacred_insufficient_scopes(self):
        self.permacred_insufficient_scopes()

    def test_temporary_credentials(self):
        self.temporary_credentials()

    def test_named_temporary_credentials(self):
        self.named_temporary_credentials()

    def test_temporary_credentials_authorizedScopes(self):
        self.temporary_credentials_authorizedScopes()

    def test_named_temporary_credentials_authorizedScopes(self):
        self.named_temporary_credentials_authorizedScopes()

    def test_signed_url(self):
        self.signed_url()

    def test_signed_url_bad_credentials(self):
        self.signed_url_bad_credentials()

    def test_temp_credentials_signed_url(self):
        self.temp_credentials_signed_url()

    def test_signed_url_authorizedScopes(self):
        self.signed_url_authorizedScopes()

    def test_temp_credentials_signed_url_authorizedScopes(self):
        self.temp_credentials_signed_url_authorizedScopes()
