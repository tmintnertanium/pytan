
# Copyright (c) 2014 Tanium Inc
#
# Generated from console.wsdl version 0.0.1     
#
#

from .base import BaseType


class GroupList(BaseType):

    OBJECT_LIST_TAG = 'groups'

    def __init__(self):
        BaseType.__init__(
            self,
            soap_tag = 'groups',
            simple_properties = {},
            complex_properties = {},
            list_properties = {'group': Group},
        )
        
        
        self.group = []

from group import Group
