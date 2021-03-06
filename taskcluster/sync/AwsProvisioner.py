#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is generated!  Do not edit!
'''
AWS Provisioner API Documentation
'''
from __future__ import absolute_import, division, print_function

import logging
import taskcluster.baseclient as baseclient

log = logging.getLogger(__name__)


class AwsProvisioner(baseclient.BaseClient):
    '''
    AWS Provisioner API Documentation
    The AWS Provisioner is responsible for provisioning instances on EC2 for use in
    TaskCluster.  The provisioner maintains a set of worker configurations which
    can be managed with an API that is typically available at
    aws-provisioner.taskcluster.net/v1.  This API can also perform basic instance
    management tasks in addition to maintaining the internal state of worker type
    configuration information.

    The Provisioner runs at a configurable interval.  Each iteration of the
    provisioner fetches a current copy the state that the AWS EC2 api reports.  In
    each iteration, we ask the Queue how many tasks are pending for that worker
    type.  Based on the number of tasks pending and the scaling ratio, we may
    submit requests for new instances.  We use pricing information, capacity and
    utility factor information to decide which instance type in which region would
    be the optimal configuration.

    Each EC2 instance type will declare a capacity and utility factor.  Capacity is
    the number of tasks that a given machine is capable of running concurrently.
    Utility factor is a relative measure of performance between two instance types.
    We multiply the utility factor by the spot price to compare instance types and
    regions when making the bidding choices.

    When a new EC2 instance is instantiated, its user data contains a token in
    `securityToken` that can be used with the `getSecret` method to retrieve
    the worker's credentials and any needed passwords or other restricted
    information.  The worker is responsible for deleting the secret after
    retrieving it, to prevent dissemination of the secret to other proceses
    which can read the instance user data.
    '''
    version = 0
    referenceUrl = 'http://references.taskcluster.net/aws-provisioner/v1/api.json'
    routes = {
        'createWorkerType': '/worker-type/{workerType}',
        'updateWorkerType': '/worker-type/{workerType}/update',
        'workerType': '/worker-type/{workerType}',
        'removeWorkerType': '/worker-type/{workerType}',
        'listWorkerTypes': '/list-worker-types',
        'createSecret': '/secret/{token}',
        'getSecret': '/secret/{token}',
        'instanceStarted': '/instance-started/{instanceId}/{token}',
        'removeSecret': '/secret/{token}',
        'getLaunchSpecs': '/worker-type/{workerType}/launch-specifications',
        'awsState': '/aws-state',
        'state': '/state/{workerType}',
        'ping': '/ping',
        'backendStatus': '/backend-status',
        'apiReference': '/api-reference',
    }

    def __init__(self, *args, **kwargs):
        self.classOptions = {}
        self.classOptions['baseUrl'] = 'https://aws-provisioner.taskcluster.net/v1'
        super(AwsProvisioner, self).__init__(*args, **kwargs)

    def createWorkerType(self, workerType, payload):
        '''
        Create new Worker Type

        Create a worker type.  A worker type contains all the configuration
        needed for the provisioner to manage the instances.  Each worker type
        knows which regions and which instance types are allowed for that
        worker type.  Remember that Capacity is the number of concurrent tasks
        that can be run on a given EC2 resource and that Utility is the relative
        performance rate between different instance types.  There is no way to
        configure different regions to have different sets of instance types
        so ensure that all instance types are available in all regions.
        This function is idempotent.

        Once a worker type is in the provisioner, a back ground process will
        begin creating instances for it based on its capacity bounds and its
        pending task count from the Queue.  It is the worker's responsibility
        to shut itself down.  The provisioner has a limit (currently 96hours)
        for all instances to prevent zombie instances from running indefinitely.

        The provisioner will ensure that all instances created are tagged with
        aws resource tags containing the provisioner id and the worker type.

        If provided, the secrets in the global, region and instance type sections
        are available using the secrets api.  If specified, the scopes provided
        will be used to generate a set of temporary credentials available with
        the other secrets.

        This method takes:
        - ``workerType``
        '''
        route = self.makeRoute('createWorkerType', replDict={
            'workerType': workerType,
        })
        return self._makeHttpRequest('put', route, payload)

    def updateWorkerType(self, workerType, payload):
        '''
        Update Worker Type

        Provide a new copy of a worker type to replace the existing one.
        This will overwrite the existing worker type definition if there
        is already a worker type of that name.  This method will return a
        200 response along with a copy of the worker type definition created
        Note that if you are using the result of a GET on the worker-type
        end point that you will need to delete the lastModified and workerType
        keys from the object returned, since those fields are not allowed
        the request body for this method

        Otherwise, all input requirements and actions are the same as the
        create method.

        This method takes:
        - ``workerType``
        '''
        route = self.makeRoute('updateWorkerType', replDict={
            'workerType': workerType,
        })
        return self._makeHttpRequest('post', route, payload)

    def workerType(self, workerType):
        '''
        Get Worker Type

        Retreive a copy of the requested worker type definition.
        This copy contains a lastModified field as well as the worker
        type name.  As such, it will require manipulation to be able to
        use the results of this method to submit date to the update
        method.

        This method takes:
        - ``workerType``
        '''
        route = self.makeRoute('workerType', replDict={
            'workerType': workerType,
        })
        return self._makeHttpRequest('get', route)

    def removeWorkerType(self, workerType):
        '''
        Delete Worker Type

        Delete a worker type definition.  This method will only delete
        the worker type definition from the storage table.  The actual
        deletion will be handled by a background worker.  As soon as this
        method is called for a worker type, the background worker will
        immediately submit requests to cancel all spot requests for this
        worker type as well as killing all instances regardless of their
        state.  If you want to gracefully remove a worker type, you must
        either ensure that no tasks are created with that worker type name
        or you could theoretically set maxCapacity to 0, though, this is
        not a supported or tested action

        This method takes:
        - ``workerType``
        '''
        route = self.makeRoute('removeWorkerType', replDict={
            'workerType': workerType,
        })
        return self._makeHttpRequest('delete', route)

    def listWorkerTypes(self):
        '''
        List Worker Types

        Return a list of string worker type names.  These are the names
        of all managed worker types known to the provisioner.  This does
        not include worker types which are left overs from a deleted worker
        type definition but are still running in AWS.

        This method takes no arguments.
        '''
        route = self.makeRoute('listWorkerTypes')
        return self._makeHttpRequest('get', route)

    def createSecret(self, token, payload):
        '''
        Create new Secret

        Insert a secret into the secret storage.  The supplied secrets will
        be provided verbatime via `getSecret`, while the supplied scopes will
        be converted into credentials by `getSecret`.

        This method is not ordinarily used in production; instead, the provisioner
        creates a new secret directly for each spot bid.

        This method takes:
        - ``token``
        '''
        route = self.makeRoute('createSecret', replDict={
            'token': token,
        })
        return self._makeHttpRequest('put', route, payload)

    def getSecret(self, token):
        '''
        Get a Secret

        Retrieve a secret from storage.  The result contains any passwords or
        other restricted information verbatim as well as a temporary credential
        based on the scopes specified when the secret was created.

        It is important that this secret is deleted by the consumer (`removeSecret`),
        or else the secrets will be visible to any process which can access the
        user data associated with the instance.

        This method takes:
        - ``token``
        '''
        route = self.makeRoute('getSecret', replDict={
            'token': token,
        })
        return self._makeHttpRequest('get', route)

    def instanceStarted(self, instanceId, token):
        '''
        Report an instance starting

        An instance will report in by giving its instance id as well
        as its security token.  The token is given and checked to ensure
        that it matches a real token that exists to ensure that random
        machines do not check in.  We could generate a different token
        but that seems like overkill

        This method takes:
        - ``instanceId``
        - ``token``
        '''
        route = self.makeRoute('instanceStarted', replDict={
            'instanceId': instanceId,
            'token': token,
        })
        return self._makeHttpRequest('get', route)

    def removeSecret(self, token):
        '''
        Remove a Secret

        Remove a secret.  After this call, a call to `getSecret` with the given
        token will return no information.

        It is very important that the consumer of a
        secret delete the secret from storage before handing over control
        to untrusted processes to prevent credential and/or secret leakage.

        This method takes:
        - ``token``
        '''
        route = self.makeRoute('removeSecret', replDict={
            'token': token,
        })
        return self._makeHttpRequest('delete', route)

    def getLaunchSpecs(self, workerType):
        '''
        Get All Launch Specifications for WorkerType

        This method returns a preview of all possible launch specifications
        that this worker type definition could submit to EC2.  It is used to
        test worker types, nothing more

        **This API end-point is experimental and may be subject to change without warning.**

        This method takes:
        - ``workerType``
        '''
        route = self.makeRoute('getLaunchSpecs', replDict={
            'workerType': workerType,
        })
        return self._makeHttpRequest('get', route)

    def awsState(self):
        '''
        Get AWS State for all worker types

        This method is a left over and will be removed as soon as the
        tools.tc.net UI is updated to use the per-worker state

        **DEPRECATED.**

        This method takes no arguments.
        '''
        route = self.makeRoute('awsState')
        return self._makeHttpRequest('get', route)

    def state(self, workerType):
        '''
        Get AWS State for a worker type

        Return the state of a given workertype as stored by the provisioner.
        This state is stored as three lists: 1 for all instances, 1 for requests
        which show in the ec2 api and 1 list for those only tracked internally
        in the provisioner.

        This method takes:
        - ``workerType``
        '''
        route = self.makeRoute('state', replDict={
            'workerType': workerType,
        })
        return self._makeHttpRequest('get', route)

    def ping(self):
        '''
        Ping Server

        Documented later...

        **Warning** this api end-point is **not stable**.

        This method takes no arguments.
        '''
        route = self.makeRoute('ping')
        return self._makeHttpRequest('get', route)

    def backendStatus(self):
        '''
        Backend Status

        **Warning** this api end-point is **not stable**.

        This method takes no arguments.
        '''
        route = self.makeRoute('backendStatus')
        return self._makeHttpRequest('get', route)

    def apiReference(self):
        '''
        api reference

        Get an API reference!

        **Warning** this api end-point is **not stable**.

        This method takes no arguments.
        '''
        route = self.makeRoute('apiReference')
        return self._makeHttpRequest('get', route)
