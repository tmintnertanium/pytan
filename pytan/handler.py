# -*- mode: Python; tab-width: 4; indent-tabs-mode: nil; -*-
# ex: set tabstop=4
# Please do not change the two lines above. See PEP 8, PEP 263.
"""PyTan: A wrapper around Tanium's SOAP API in Python

Like saran wrap. But not.

This requires Python 2.7
"""
import sys

# disable python from creating .pyc files everywhere
sys.dont_write_bytecode = True

import os
import logging
import io
from . import utils
from . import constants
from . import api
from .utils import HandlerError

mylog = logging.getLogger("handler")


class Handler(object):

    def __init__(self, username, password, host, port="444", loglevel=0,
                 debugformat=False, **kwargs):
        super(Handler, self).__init__()

        # use port 444 if you have direct access to it,
        # port 444 is direct access to API
        # port 443 uses apache forwarder which then goes to port 444

        # setup the console logging handler
        utils.setup_console_logging()
        # create all the loggers and set their levels based on loglevel
        utils.set_log_levels(loglevel)
        # change the format of console logging handler if need be
        utils.change_console_format(debugformat)

        if not username:
            raise HandlerError("Must supply username!")
        if not password:
            raise HandlerError("Must supply password!")
        if not host:
            raise HandlerError("Must supply host!")
        if not port:
            raise HandlerError("Must supply port!")
        try:
            port = int(port)
        except ValueError:
            raise HandlerError("port must be an integer!")

        utils.test_app_port(host, port)
        self.session = api.Session(host, port)
        self.session.authenticate(username, password)

    def __str__(self):
        str_tpl = "Handler for {}".format
        ret = str_tpl(self.session)
        return ret

    def ask(self, **kwargs):
        qtype = kwargs.get('qtype', '')
        if not qtype:
            err = (
                "Must supply question type as 'qtype'! Valid choices: {}"
            ).format
            raise HandlerError(err(', '.join(constants.Q_OBJ_MAP)))
        q_obj_map = utils.get_q_obj_map(qtype)
        kwargs.pop('qtype')
        result = getattr(self, q_obj_map['handler'])(**kwargs)
        return result

    def ask_saved(self, **kwargs):

        # get the saved_question object the user passed in
        q_objs = self.get('saved_question', **kwargs)

        if len(q_objs) != 1:
            err = (
                "Multiple saved questions returned, can only ask one "
                "saved question!\nArgs: {}\nReturned saved questions:\n\t{}"
            ).format
            q_obj_str = '\n\t'.join([str(x) for x in q_objs])
            raise HandlerError(err(kwargs, q_obj_str))

        q_obj = q_objs[0]

        # poll the Saved Question ID returned above to wait for results
        ask_kwargs = utils.get_ask_kwargs(**kwargs)
        asker = api.QuestionAsker(self.session, q_obj, **ask_kwargs)
        asker.run({'ProgressChanged': utils.progressChanged})

        # get the results
        req_kwargs = utils.get_req_kwargs(**kwargs)
        result = self.session.getResultData(q_obj, **req_kwargs)

        # add the sensors from this question to the ResultSet object
        # for reporting
        result.sensors = [x.sensor for x in q_obj.question.selects]
        return result

    def ask_manual(self, **kwargs):
        '''Parses a set of python objects into a Question object,
        adds the Question object, and returns the results for the Question ID
        of the added Question object
        '''

        # get our defs from kwargs and churn them into what we want
        sensor_defs = utils.parse_sensor_defs(**kwargs)
        q_filter_defs = utils.parse_question_filter_defs(**kwargs)
        q_option_defs = utils.parse_question_option_defs(**kwargs)

        # do basic validation of our defs
        sensor_defs = utils.val_sensor_defs(sensor_defs)
        q_filter_defs = utils.val_q_filter_defs(q_filter_defs)

        # get the sensor objects that are in our defs and add them as
        # d['sensor_obj']
        sensor_defs = self._get_sensor_defs(sensor_defs)
        q_filter_defs = self._get_sensor_defs(q_filter_defs)

        # build a SelectList object from our sensor_defs
        selectlist_obj = utils.build_selectlist_obj(sensor_defs)

        # build a Group object from our question filters/options
        group_obj = utils.build_group_obj(q_filter_defs, q_option_defs)

        # build a Question object from selectlist_obj and group_obj
        add_q_obj = utils.build_manual_q(selectlist_obj, group_obj)

        # add our Question and get a Question ID back
        q_obj = self.session.add(add_q_obj)

        # poll the Question ID returned above to wait for results
        ask_kwargs = utils.get_ask_kwargs(**kwargs)
        asker = api.QuestionAsker(self.session, q_obj, **ask_kwargs)
        asker.run({'ProgressChanged': utils.progressChanged})

        # get the results
        req_kwargs = utils.get_req_kwargs(**kwargs)
        result = self.session.getResultData(q_obj, **req_kwargs)

        # add the sensors from this question to the ResultSet object
        # for reporting
        result.sensors = [x['sensor_obj'] for x in sensor_defs]
        return result

    def ask_manual_human(self, **kwargs):
        '''Parses a set of "human" strings into python objects usable
        by ask_manual()
        '''

        if 'sensors' in kwargs:
            sensors = kwargs.pop('sensors')
        else:
            sensors = []

        if 'question_filters' in kwargs:
            q_filters = kwargs.pop('question_filters')
        else:
            q_filters = []

        if 'question_options' in kwargs:
            q_options = kwargs.pop('question_options')
        else:
            q_options = []

        sensor_defs = utils.dehumanize_sensors(sensors)
        q_filter_defs = utils.dehumanize_question_filters(q_filters)
        q_option_defs = utils.dehumanize_question_options(q_options)

        result = self.ask_manual(
            sensor_defs=sensor_defs,
            question_filter_defs=q_filter_defs,
            question_option_defs=q_option_defs,
            **kwargs
        )
        return result

    def export_obj(self, obj, export_format, **kwargs):
        objtype = type(obj)
        try:
            objclassname = objtype.__name__
        except:
            objclassname = 'Unknown'

        export_maps = constants.EXPORT_MAPS

        # build a list of supported object types
        supp_types = ', '.join(export_maps.keys())

        # see if supplied obj is a supported object type
        type_match = [
            x for x in export_maps if isinstance(obj, getattr(api, x))
        ]

        if not type_match:
            err = (
                "{} not a supported object to export, must be one of: {}"
            ).format
            raise HandlerError(err(objtype, supp_types))

        # get the export formats for this obj type
        export_formats = export_maps.get(type_match[0], '')
        if export_format not in export_formats:
            err = (
                "{!r} not a supported export format for {}, must be one of: {}"
            ).format(export_format, objclassname, ', '.join(export_formats))
            raise HandlerError(err)

        # perform validation on optional kwargs, if they exist
        opt_keys = export_formats.get(export_format, [])
        for opt_key in opt_keys:
            check_args = dict(opt_key.items() + {'d': kwargs}.items())
            utils.check_dictkey(**check_args)

        # filter out the kwargs that are specific to this obj type and
        # format type
        format_kwargs = {
            k: v for k, v in kwargs.iteritems()
            if k in [a['key'] for a in opt_keys]
        }

        # run the handler that is specific to this objtype, if it exists
        class_method_str = '_export_class_' + type_match[0]
        class_handler = getattr(self, class_method_str, '')
        if class_handler:
            result = class_handler(obj, export_format, **format_kwargs)
        else:
            err = "{!r} not supported by Handler!".format
            raise HandlerError(err(objclassname))
        return result

    def export_to_report_file(self, obj, export_format, report_file=None,
                              **kwargs):
        if report_file is None:
            report_file = "{}_{}.{}".format(
                type(obj).__name__, utils.get_now(), export_format,
            )
            report_file = os.path.join(os.getcwd(), report_file)
            m = "No report file name supplied, generated name: {!r}".format
            mylog.debug(m(report_file))

        report_dir = os.path.dirname(report_file)
        if not os.path.isdir(report_dir):
            os.makedirs(report_dir)
        result = self.export_obj(obj, export_format, **kwargs)
        with open(report_file, 'w') as fd:
            fd.write(result)
        m = "Report file {!r} written with {} bytes".format
        mylog.info(m(report_file, len(result)))

    def get(self, obj, **kwargs):
        obj_map = utils.get_obj_map(obj)
        api_attrs = obj_map['search']
        api_kwattrs = [kwargs.get(x, '') for x in api_attrs]

        # if the api doesn't support filtering for this object,
        # return all objects of this type
        if not api_attrs:
            return self.get_all(obj, **kwargs)

        # if api supports filtering for this object,
        # but no filters supplied in kwargs, raise
        if not any(api_kwattrs):
            err = "Getting a {} requires at least one filter: {}".format
            raise HandlerError(err(obj, api_attrs))

        # if there is a multi in obj_map, that means we can pass a list
        # type to the api. the list will an entry for each api_kw
        if obj_map['multi']:
            return self._get_multi(obj_map, **kwargs)

        # if there is a single in obj_map but not multi, that means
        # we have to find each object individually
        if obj_map['single']:
            return self._get_single(obj_map, **kwargs)

        err = "No single or multi search defined for {}".format
        raise HandlerError(err(obj))

    def get_all(self, obj, **kwargs):
        obj_map = utils.get_obj_map(obj)
        api_obj_all = getattr(api, obj_map['all'])()
        found = self._find(api_obj_all, **kwargs)
        return found

    # BEGIN PRIVATE METHODS
    def _find(self, api_object, **kwargs):
        req_kwargs = utils.get_req_kwargs(**kwargs)
        try:
            search_str = '; '.join([str(x) for x in api_object])
        except:
            search_str = api_object
        mylog.debug("Searching for {}".format(search_str))
        try:
            found = self.session.find(api_object, **req_kwargs)
        except Exception as e:
            mylog.error(e)
            err = "No results found searching for {}!!".format
            raise HandlerError(err(search_str))

        if utils.empty_obj(found):
            err = "No results found searching for {}!!".format
            raise HandlerError(err(search_str))

        mylog.debug("Found {}".format(found))
        return found

    def _get_multi(self, obj_map, **kwargs):
        api_attrs = obj_map['search']
        api_kwattrs = [kwargs.get(x, '') for x in api_attrs]
        api_kw = {k: v for k, v in zip(api_attrs, api_kwattrs)}

        # create a list object to append our searches to
        api_obj_multi = getattr(api, obj_map['multi'])()
        for k, v in api_kw.iteritems():
            if v and k not in obj_map['search']:
                continue  # if we can't search for k, skip

            if not v:
                continue  # if v empty, skip

            if utils.is_list(v):
                for i in v:
                    api_obj_single = getattr(api, obj_map['single'])()
                    setattr(api_obj_single, k, i)
                    api_obj_multi.append(api_obj_single)
            else:
                api_obj_single = getattr(api, obj_map['single'])()
                setattr(api_obj_single, k, v)
                api_obj_multi.append(api_obj_single)

        # find the multi list object
        found = self._find(api_obj_multi, **kwargs)
        return found

    def _get_single(self, obj_map, **kwargs):
        api_attrs = obj_map['search']
        api_kwattrs = [kwargs.get(x, '') for x in api_attrs]
        api_kw = {k: v for k, v in zip(api_attrs, api_kwattrs)}

        # we create a list object to append our single item searches to
        if obj_map.get('allfix', ''):
            found = getattr(api, obj_map['allfix'])()
        else:
            found = getattr(api, obj_map['all'])()

        for k, v in api_kw.iteritems():
            if v and k not in obj_map['search']:
                continue  # if we can't search for k, skip

            if not v:
                continue  # if v empty, skip

            if utils.is_list(v):
                for i in v:
                    api_obj_single = getattr(api, obj_map['single'])()
                    setattr(api_obj_single, k, i)
                    found.append(self._find(api_obj_single, **kwargs))
            else:
                api_obj_single = getattr(api, obj_map['single'])()
                setattr(api_obj_single, k, v)
                found.append(self._find(api_obj_single, **kwargs))

        return found

    def _get_sensor_defs(self, defs):
        s_obj_map = constants.GET_OBJ_MAP['sensor']
        search_keys = s_obj_map['search']

        for d in defs:
            def_search = {s: d.get(s, '') for s in search_keys if d.get(s, '')}

            # get the sensor object
            d['sensor_obj'] = self.get('sensor', **def_search)[0]
        return defs

    def _export_class_BaseType(self, obj, export_format, **kwargs):
        # run the handler that is specific to this export_format, if it exists
        format_method_str = '_export_format_' + export_format
        format_handler = getattr(self, format_method_str, '')
        if format_handler:
            result = format_handler(obj, **kwargs)
        else:
            err = "{!r} not coded for in Handler!".format
            raise HandlerError(err(export_format))
        return result

    def _export_class_ResultSet(self, obj, export_format, **kwargs):
        '''
        ensure kwargs[sensors] has all the sensors that correlate
        to the what_hash of each column, but only if header_add_sensor=True
        needed for: ResultSet.write_csv(header_add_sensor=True)
        '''
        header_add_sensor = kwargs.get('header_add_sensor', False)
        sensors = kwargs.get('sensors', [])
        if header_add_sensor:
            sensor_hashes = [x.hash for x in sensors]
            column_hashes = [x.what_hash for x in obj.columns]
            missing_hashes = [
                x for x in column_hashes if x not in sensor_hashes and x > 1
            ]
            if missing_hashes:
                missing_sensors = self.get('sensor', hash=missing_hashes)
                kwargs['sensors'] += list(missing_sensors)

        # run the handler that is specific to this export_format, if it exists
        format_method_str = '_export_format_' + export_format
        format_handler = getattr(self, format_method_str, '')
        if format_handler:
            result = format_handler(obj, **kwargs)
        else:
            err = "{!r} not coded for in Handler!".format
            raise HandlerError(err(export_format))
        return result

    def _export_format_csv(self, obj, **kwargs):
        if not hasattr(obj, 'write_csv'):
            err = "{!r} has no write_csv() method!".format
            raise HandlerError(err(obj))
        out = io.BytesIO()
        if getattr(obj, '_list_properties', ''):
            result = obj.write_csv(out, list(obj), **kwargs)
        else:
            result = obj.write_csv(out, obj, **kwargs)
        result = out.getvalue()
        return result

    def _export_format_json(self, obj, **kwargs):
        if not hasattr(obj, 'to_json'):
            err = "{!r} has no to_json() method!".format
            raise HandlerError(err(obj))
        result = obj.to_json(jsonable=obj, **kwargs)
        return result

    def _export_format_xml(self, obj, **kwargs):
        if not hasattr(obj, 'toSOAPBody'):
            err = "{!r} has no toSOAPBody() method!".format
            raise HandlerError(err(obj))
        result = obj.toSOAPBody(**kwargs)
        return result
