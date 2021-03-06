#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is generated!  Do not edit!
'''
TaskCluster-Github Exchanges
'''
from __future__ import absolute_import, division, print_function

import logging
import taskcluster.baseclient as baseclient

log = logging.getLogger(__name__)


class GithubEvents(baseclient.BaseClient):
    '''
    TaskCluster-Github Exchanges
    The github service, typically available at
    `github.taskcluster.net`, is responsible for publishing a pulse
    message for supported github events.

    This document describes the exchange offered by the taskcluster
    github service
    '''
    version = 0
    referenceUrl = 'http://references.taskcluster.net/github/v1/exchanges.json'
    routingKeys = {
        'pullRequest': [
            {
                'constant': 'primary',
                'multipleWords': False,
                'name': 'routingKeyKind',
                'required': True,
            },
            {
                'multipleWords': False,
                'name': 'organization',
                'required': True,
            },
            {
                'multipleWords': False,
                'name': 'repository',
                'required': True,
            },
            {
                'multipleWords': False,
                'name': 'action',
                'required': True,
            },
        ],
        'push': [
            {
                'constant': 'primary',
                'multipleWords': False,
                'name': 'routingKeyKind',
                'required': True,
            },
            {
                'multipleWords': False,
                'name': 'organization',
                'required': True,
            },
            {
                'multipleWords': False,
                'name': 'repository',
                'required': True,
            },
        ],
    }

    def __init__(self, *args, **kwargs):
        self.classOptions = {}
        self.classOptions['exchangePrefix'] = 'exchange/taskcluster-github/v1/'
        super(GithubEvents, self).__init__(*args, **kwargs)

    def pullRequest(self, routingKeyPattern=None):
        '''
        GitHub Pull Request Event

        When a GitHub pull request event is posted it will be broadcast on this
        exchange with the designated `organization` and `repository`
        in the routing-key along with event specific metadata in the payload.

        Generate a routing key pattern for the pull-request exchange.
        This method takes a given routing key as a string or a dictionary.  For each given
        dictionary key, the corresponding routing key token takes its value.  For routing key
        tokens which are not specified by the dictionary, the * or # character is used depending
        on whether or not the key allows multiple words.

        This exchange takes the following keys:
        - ``routingKeyKind``
        - ``organization``
        - ``repository``
        - ``action``
        '''
        exchangeUrl = '%s/%s' % (self.options['exchangePrefix'].rstrip('/'),
                                 "pull-request".lstrip('/'))
        return self._makeTopicExchange(
            exchangeUrl,
            self.routingKeys['pullRequest'],
            routingKeyPattern
        )

    def push(self, routingKeyPattern=None):
        '''
        GitHub push Event

        When a GitHub push event is posted it will be broadcast on this
        exchange with the designated `organization` and `repository`
        in the routing-key along with event specific metadata in the payload.

        Generate a routing key pattern for the push exchange.
        This method takes a given routing key as a string or a dictionary.  For each given
        dictionary key, the corresponding routing key token takes its value.  For routing key
        tokens which are not specified by the dictionary, the * or # character is used depending
        on whether or not the key allows multiple words.

        This exchange takes the following keys:
        - ``routingKeyKind``
        - ``organization``
        - ``repository``
        '''
        exchangeUrl = '%s/%s' % (self.options['exchangePrefix'].rstrip('/'),
                                 "push".lstrip('/'))
        return self._makeTopicExchange(
            exchangeUrl,
            self.routingKeys['push'],
            routingKeyPattern
        )
