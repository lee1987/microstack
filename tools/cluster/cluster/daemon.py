import logging
import json

import semantic_version

import keystoneclient.exceptions as kc_exceptions

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest


from cluster.shell import check_output

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client as v3client

logger = logging.getLogger(__name__)


app = Flask(__name__)


API_VERSION = semantic_version.Version('1.0.0')


class Unauthorized(Exception):
    pass


class APIException(Exception):
    status_code = None
    message = ''

    def to_dict(self):
        return {'message': self.message}


class APIVersionMissing(APIException):
    status_code = 400
    message = 'An API version was not specified in the request.'


class APIVersionInvalid(APIException):
    status_code = 400
    message = 'Invalid API version was specified in the request.'


class APIVersionDropped(APIException):
    status_code = 410
    message = 'The requested join API version is no longer supported.'


class APIVersionNotImplemented(APIException):
    status_code = 501
    message = 'The requested join API version is not yet implemented.'


class InvalidJSONInRequest(APIException):
    status_code = 400
    message = 'The request includes invalid JSON.'


class IncorrectContentType(APIException):
    status_code = 400
    message = ('The request does not have a Content-Type header set to '
               'application/json.')


class MissingAuthDataInRequest(APIException):
    status_code = 400
    message = 'The request does not have the required authentication data.'


class InvalidAuthDataFormatInRequest(APIException):
    status_code = 400
    message = 'The authentication data in the request has invalid format.'


class InvalidAuthDataInRequest(APIException):
    status_code = 400
    message = 'The authentication data in the request is invalid.'


class AuthorizationFailed(APIException):
    status_code = 401
    message = ('Failed to pass authorization using the data provided in the'
               ' request')


class UnexpectedError(APIException):
    status_code = 500
    message = ('The clustering server has encountered an unexpected'
               ' error while handling the request.')


def _handle_api_version_exception(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.errorhandler(APIVersionMissing)
def handle_api_version_missing(error):
    return _handle_api_version_exception(error)


@app.errorhandler(APIVersionInvalid)
def handle_api_version_invalid(error):
    return _handle_api_version_exception(error)


@app.errorhandler(APIVersionDropped)
def handle_api_version_dropped(error):
    return _handle_api_version_exception(error)


@app.errorhandler(APIVersionNotImplemented)
def handle_api_version_not_implemented(error):
    return _handle_api_version_exception(error)


@app.errorhandler(IncorrectContentType)
def handle_incorrect_content_type(error):
    return _handle_api_version_exception(error)


@app.errorhandler(InvalidJSONInRequest)
def handle_invalid_json_in_request(error):
    return _handle_api_version_exception(error)


@app.errorhandler(InvalidAuthDataInRequest)
def handle_invalid_auth_data_format_in_request(error):
    return _handle_api_version_exception(error)


@app.errorhandler(InvalidAuthDataFormatInRequest)
def handle_invalid_auth_data_in_request(error):
    return _handle_api_version_exception(error)


@app.errorhandler(AuthorizationFailed)
def handle_authorization_failed(error):
    return _handle_api_version_exception(error)


@app.errorhandler(UnexpectedError)
def handle_unexpected_error(error):
    return _handle_api_version_exception(error)


def join_info():
    """Generate the configuration information to return to a client."""
    # TODO: be selective about what we return. For now, we just get everything.
    config = json.loads(check_output('snapctl', 'get', 'config'))
    info = {'config': config}
    return info


@app.route('/join', methods=['POST'])
def join():
    """Authorize a client node and return relevant config."""

    # Retrieve an API version from the request - it is a mandatory
    # header for this API.
    request_version = request.headers.get('API-Version')
    if request_version is None:
        logger.debug('The client has not specified the API-version header.')
        raise APIVersionMissing()
    else:
        try:
            api_version = semantic_version.Version(request_version)
        except ValueError:
            logger.debug('The client has specified an invalid API version.'
                         f': {request_version}')
            raise APIVersionInvalid()

    # Compare the API version used by the clustering service with the
    # one specified in the request and return an appropriate response.
    if api_version.major > API_VERSION.major:
        logger.debug('The client requested a version that is not'
                     f' supported yet: {api_version}.')
        raise APIVersionNotImplemented()
    elif api_version.major < API_VERSION.major:
        logger.debug('The client request version is no longer supported'
                     f': {api_version}.')
        raise APIVersionDropped()
    else:
        # Flask raises a BadRequest if the JSON content is invalid and
        # returns None if the Content-Type header is missing or not set
        # to application/json.
        try:
            req_json = request.json
        except BadRequest:
            logger.debug('The client has POSTed an invalid JSON'
                         ' in the request.')
            raise InvalidJSONInRequest()
        if req_json is None:
            logger.debug('The client has not specified the application/json'
                         ' content type in the request.')
            raise IncorrectContentType()

        # So far we don't have any minor versions with backwards-compatible
        # changes so just assume that all data will be present or error out.
        credential_id = req_json.get('credential-id')
        credential_secret = req_json.get('credential-secret')
        if not credential_id or not credential_secret:
            logger.debug('The client has not specified the required'
                         ' authentication data in the request.')
            return MissingAuthDataInRequest()

        # TODO: handle https here when TLS termination support is added.
        keystone_base_url = 'http://localhost:5000/v3'

        # In an unlikely event of failing to construct an auth object
        # treat it as if invalid data got passed in terms of responding
        # to the client.
        try:
            auth = v3.ApplicationCredential(
                auth_url=keystone_base_url,
                application_credential_id=credential_id,
                application_credential_secret=credential_secret
            )
        except Exception:
            logger.exception('An exception has occurred while trying to build'
                             ' an auth object for an application credential'
                             ' passed from the clustering client.')
            raise InvalidAuthDataInRequest()

        try:
            # Use the auth object with the app credential to create a session
            # which the Keystone client will use.
            sess = session.Session(auth=auth)
        except Exception:
            logger.exception('An exception has occurred while trying to build'
                             ' a Session object with auth data'
                             ' passed from the clustering client.')
            raise UnexpectedError()

        try:
            keystone_client = v3client.Client(session=sess)
        except Exception:
            logger.exception('An exception has occurred while trying to build'
                             ' a Keystone Client object with auth data'
                             ' passed from the clustering client.')
            raise UnexpectedError()

        try:
            # The add-compute command creates application credentials that
            # allow access to /v3/auth/catalog with an expiration time.
            # Authorization failures occur after an app credential expires
            # in which case an error is returned to the client.
            keystone_client.get(f'{keystone_base_url}/auth/catalog')
        except (kc_exceptions.AuthorizationFailure,
                kc_exceptions.Unauthorized):
            logger.exception('Failed to get a Keystone token'
                             ' with the application credentials'
                             ' passed from the clustering client.')
            raise AuthorizationFailed()
        except ValueError:
            logger.exception('Insufficient amount of parameters were'
                             ' used in the request to Keystone.')
            raise UnexpectedError()
        except kc_exceptions.ConnectionError:
            logger.exception('Failed to connect to Keystone')
            raise UnexpectedError()
        except kc_exceptions.SSLError:
            logger.exception('A TLS-related error has occurred while'
                             ' connecting to Keystone')
            raise UnexpectedError()

        # We were able to authenticate against Keystone using the
        # application credential and verify that it has not expired
        # so the information for a compute node to join the cluster can
        # now be returned.
        return json.dumps(join_info())


@app.route('/')
def home():
    status = {
        'status': 'running',
        'info': 'MicroStack clustering daemon.'

    }
    return json.dumps(status)
