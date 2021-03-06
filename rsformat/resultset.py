"""Manage a resultset thatrsformatter will understand"""

import logging
import sys
import datetime
from collections import namedtuple, OrderedDict
import types

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)

DEFAULT = "\033[0m"
BOLD = "\033[1m"


class Results(object):
    """
    Collection of ResultSet objects with focus on initialization flexibility
    """
    def __init__(self, result_sets=None, config=None):
        self.setCount = 0
        self.converter = None  # TODO add plugin support to convert common result frameworks
        self._manageconfig(config)
        self._initresultsets(result_sets)

    def _initresultsets(self, result_sets):
        """
        Determine what type of resultsets were passed in handle accordingly.
        Supports list, generator, or iterator
        """
        if isinstance(result_sets, types.GeneratorType):
            self.generate_resultsets = result_sets
            return
        if result_sets is None:
            result_sets = []
        try:
            self.generate_resultsets = (row for row in result_sets)  # generator
        except TypeError:
            raise TypeError("Result resultset must be iterable")

    def _manageconfig(self, opts):
        """
        Validate config for resultset
        """
        if opts is None:
            opts = {}
        if type(opts) != dict:
            raise TypeError("config for Result needs to be dict type")
        self.config = dict(opts)
    # def intialize_resultsets(self)


class ResultSet(object):
    """
    Single set of results containing row objects.
    """
    def __init__(self, results, headers=None, order_map=None):
        if order_map:
            om = {}
            for k in order_map.keys():
                col = order_map.get('col')
                om[k] = col if col is not None else order_map[k].get('alias')
            self.order_map = self._sort_order_map(om)
            self.order_map_raw = order_map
        else:
            self.order_map = order_map
            self.order_map_raw = order_map
        self.headers, self.header_source = self._manageheaders(headers)
        self.rowdef = namedtuple("RsRow", self.headers, rename=True)
        self.generate_rows = None
        self.rows = []
        self.errors = []
        self.row_count = 0
        self.error_count = 0
        # self.results = results
        self._initresults(results)
        self.initialize_rows()

    def _initresults(self, results):
        """
        Determine what type results were passed and handle accordingly.
        """
        if isinstance(results, types.GeneratorType):
            self.generate_rows = results
            return
        try:
            self.generate_rows = (row for row in results)  # generator
        except TypeError:
            raise TypeError("ResultSet results must be iterable")

    def initialize_rows(self):
        """
        Process rows from a generator object
        """
        for row in self.generate_rows:
            # log.debug("processing row: %s" % (row))
            self.addrow(row)
        log.debug("rows: %s, rowcount: %s, errors: %s, errorcount: %s" % (len(self.rows), self.row_count, self.errors, self.error_count))

    def addrow(self, row):
        """
        Add a single row to resultset
        """
        try:
            self.rows.append(Row(row, self.rowdef, self.order_map_raw))
            self.row_count += 1
        except Exception as e:
            self.errors.append(row)
            self.error_count += 1
            print("Error adding row: %s" % e)

    def _manageheaders(self, headers):
        """
        Type checking for headers and order map provided to result set
        """
        if self.order_map is not None and headers is not None:
            # use headers if both are provided
            # raise TypeError("ResultSet() requires and order_map or headers, not both")
            if type(headers) != list:
                raise TypeError("ResultSet() requires headers as list when no order_map provided")
            else:
                return list(headers), "headers priority"
        if self.order_map is None:
            if headers is None:
                raise TypeError("ResultSet() requires headers or order_map (neither given)")
            elif type(headers) != list:
                raise TypeError("ResultSet() requires headers as list when no order_map provided")
            else:
                return headers, "headers"
        if headers is None:
            if type(self.order_map) != OrderedDict:
                raise TypeError("ResultSet() requires order_map as dict with no headers. provided:  type(self.order_map)")
            else:
                return list(self.order_map.values()), "order_map"

    @staticmethod
    def _sort_order_map(order_map):
        """
        returns and ordered dict of keys based on an order_map dict with floats/ints as keys
        """
        if type(order_map) != dict:
            raise TypeError("must provide dict to define ordermapping as '{float: key_string}'. provided %s" % order_map)
        try:
            converted_keys = [(k, float(k)) for k in order_map.keys()]
        except ValueError as e:
            print("ValueError: {0}".format(e))
            print("%s[TIP]%s     : check that all keys provided in order map can be converted to floats" % ('\033[1m', '\033[0m'))
            raise

        return OrderedDict([(ck, order_map[k]) for k, ck in sorted(converted_keys, key=lambda x: x[1])])


class Row(object):
    """
    Row of data that can be initialized from tuple, list, dict
    """

    __slots__ = ('data')

    def __init__(self, values, rowdef=None, order_map=None):
        self.data = self._normalize_row(values, rowdef, order_map)

    def rowdef(self):
        return self.data._fields

    def get(self, key):
        return self.data[self.data._fields.index(key)]

    def as_csv(self):
        return "%s," % ",".join(prop if prop else "" for prop in self.data)

    @staticmethod
    def _normalize_row(values, rowdef, order_map):
        """
        return a named tuple of values if provided bounded iterable dict, tuple, etc
        """
        tp = type(values)
        if tp == list:
            return rowdef._make(values)
        elif tp == tuple:
            return rowdef._make(values)
        elif tp == dict:
            # filtered is a new dict only the named fields of the rowdef
            filtered = {k: format(values.get(k, None), order_map[i].get('format', [])) for i, k in enumerate(rowdef._fields)}
            return rowdef(**filtered)
        else:
            raise TypeError("must provide values as bounded iterable for new Row")


def format(value, formatters):
    """Runs a value through a formatter pipeline"""
    # print("formatting value: %s with formatters: %s" % (value, formatters))
    for fmt in formatters:
        type = fmt.get('type')
        name = "format_%s" % (type)
        func = None
        try:
            func = getattr(sys.modules[__name__], name)
        except AttributeError:
            print("Function does not exist: %s" % name)
        if isinstance(func, types.FunctionType):
            value = func(value, fmt)
    return value


def format_value(value, props):
    val = props.get('value')
    return val


def format_conversion(value, props):
    tp = props.get('convert')
    if value in(None, ''):
        return value
    if tp == "int":
        return int(value)
    elif tp == "float":
        return float(value)
    elif tp == "str":
        return "%s" % value
    else:
        raise ValueError("Must provide type as int float or str. provided: %s" % tp)


def format_date(value, props):
    """Date formatter"""
    if value in(None, ''):
        return value
    fmt_from = props.get('from', None)
    fmt_to = props.get('to', None)
    if fmt_from is None:
        raise ValueError("must provide from format with date formatting")
    if fmt_to is None:
        raise ValueError("must provide to format with date formatting")
    try:
        new_date = datetime.datetime.strptime(value, fmt_from)
        return new_date.strftime(fmt_to)
    except Exception:
        raise ValueError("problem formatting date with strptime for value %s and format %s -> %s" % (value, fmt_from, fmt_to))


def format_mapping(value, props):
    """Map formatter"""
    maps = props.get('maps')
    default = props.get('default')
    for map in maps:
        map_from = map.get('from')
        map_to = map.get('to')
        if value == map_from:
            return map_to
    if default is not None:
        return default
    return value


def format_string(value, props):
    """String formatter"""
    func = props.get('func')
    if func is None:
        raise ValueError("must provide a func for string format")

    return perform_format_string(value, func, props)


def perform_format_string(value, string_func, props):
    name = "_format_string_%s" % (string_func)
    func = None
    try:
        func = getattr(sys.modules[__name__], name)
    except AttributeError:
        print("Function does not exist: %s" % name)
    if isinstance(func, types.FunctionType):
        return func(value, props)


def _format_string_format(value, props):
    tmpl = props.get('tmpl')
    if tmpl is None:
        raise ValueError("must provide a tmpl property for string format")
    if value in (None, ''):
        return value
    return tmpl.format(value)


def _format_string_upper(value, props):
    return value.upper()


def _format_string_lower(value, props):
    return value.lower()


def _format_string_replace(value, props):
    find = props.get('find')
    replace = props.get('replace')
    return value.replace(find, replace)


if __name__ == "__main__":
    log.info("testing logger in main")
