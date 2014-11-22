#!/usr/bin/env python -ttB

import sys

# disable python from creating .pyc files everywhere
sys.dont_write_bytecode = True

import os
import unittest

my_file = os.path.abspath(__file__)
my_dir = os.path.dirname(my_file)
root_dir = os.path.join(my_dir, os.pardir, os.pardir, 'pytan')
root_dir = os.path.abspath(root_dir)
path_adds = [my_dir, root_dir]

for aa in path_adds:
    if aa not in sys.path:
        sys.path.insert(0, aa)

import api
import json


class TestToJsonable(unittest.TestCase):

    def test_user_to_jsonable(self):
        user = api.User()
        user.id = 1
        user.name = 'Tanium'
        user_role_list = api.UserRoleList()
        user.roles = user_role_list
        user_role = api.UserRole()
        user_role_list.append(user_role)
        user_role.id = 3
        user_role.name = 'Administrator'
        permissions = api.UserPermissions()
        user_role.permissions = permissions
        permissions.permission = 'Administrator'
        user_role = api.UserRole()
        user_role_list.append(user_role)
        user_role.id = 5
        user_role.name = 'Question Asker'
        permissions = api.UserPermissions()
        user_role.permissions = permissions
        permissions.permission = 'Question Asker'
        self.maxDiff = None
        exp = {
            'id': 1,
            'name': 'Tanium',
            'roles': {
                'role': [
                    {
                        'id': 3,
                        'name': 'Administrator',
                        'permissions': {'permission': 'Administrator'},
                    },
                    {
                        'id': 5,
                        'name': 'Question Asker',
                        'permissions': {'permission': 'Question Asker'},
                    },
                ],
            },
        }
        self.assertEquals(user.to_jsonable(include_type=False), exp)

    def test_with_jsonable_property(self):
        sensor = api.Sensor()
        pd = [{"name": "param1"}, {"name": "param2"}]
        sensor.parameter_definition = json.dumps(pd)
        self.assertEquals(sensor.to_jsonable(
            explode_json_string_values=True,
            include_type=False),
            {'parameter_definition': [{'name': 'param1'}, {'name': 'param2'}]})

    def test_to_json(self):
        user = api.User()
        user.name = 'Test'
        exp = """{\n  "_type": "user", \n  "name": "Test"\n}"""
        self.assertEqual(api.BaseType.to_json(user), exp)

    def test_to_json_list(self):
        users = [api.User(), api.User()]
        exp = (
            '[\n  {\n    "_type": "user"\n  }, \n  {\n    "_type": '
            '"user"\n  }\n]'
        )
        self.assertEqual(api.BaseType.to_json(users), exp)
