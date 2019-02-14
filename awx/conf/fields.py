# Python
import logging
import urllib.parse as urlparse
from collections import OrderedDict

# Django
from django.core.validators import URLValidator
from django.utils.translation import ugettext_lazy as _

# Django REST Framework
from rest_framework.fields import (  # noqa
    BooleanField, CharField, ChoiceField, DictField, EmailField, IntegerField,
    ListField, NullBooleanField
)

logger = logging.getLogger('awx.conf.fields')

# Use DRF fields to convert/validate settings:
# - to_representation(obj) should convert a native Python object to a primitive
#   serializable type. This primitive type will be what is presented in the API
#   and stored in the JSON field in the datbase.
# - to_internal_value(data) should convert the primitive type back into the
#   appropriate Python type to be used in settings.


class CharField(CharField):

    def to_representation(self, value):
        # django_rest_frameworks' default CharField implementation casts `None`
        # to a string `"None"`:
        #
        # https://github.com/tomchristie/django-rest-framework/blob/cbad236f6d817d992873cd4df6527d46ab243ed1/rest_framework/fields.py#L761
        if value is None:
            return None
        return super(CharField, self).to_representation(value)


class IntegerField(IntegerField):

    def get_value(self, dictionary):
        ret = super(IntegerField, self).get_value(dictionary)
        # Handle UI corner case
        if ret == '' and self.allow_null and not getattr(self, 'allow_blank', False):
            return None
        return ret


class StringListField(ListField):

    child = CharField()

    def to_representation(self, value):
        if value is None and self.allow_null:
            return None
        return super(StringListField, self).to_representation(value)


class StringListBooleanField(ListField):

    default_error_messages = {
        'type_error': _('Expected None, True, False, a string or list of strings but got {input_type} instead.'),
    }
    child = CharField()

    def to_representation(self, value):
        try:
            if isinstance(value, (list, tuple)):
                return super(StringListBooleanField, self).to_representation(value)
            elif value in NullBooleanField.TRUE_VALUES:
                return True
            elif value in NullBooleanField.FALSE_VALUES:
                return False
            elif value in NullBooleanField.NULL_VALUES:
                return None
            elif isinstance(value, str):
                return self.child.to_representation(value)
        except TypeError:
            pass

        self.fail('type_error', input_type=type(value))

    def to_internal_value(self, data):
        try:
            if isinstance(data, (list, tuple)):
                return super(StringListBooleanField, self).to_internal_value(data)
            elif data in NullBooleanField.TRUE_VALUES:
                return True
            elif data in NullBooleanField.FALSE_VALUES:
                return False
            elif data in NullBooleanField.NULL_VALUES:
                return None
            elif isinstance(data, str):
                return self.child.run_validation(data)
        except TypeError:
            pass
        self.fail('type_error', input_type=type(data))


class URLField(CharField):

    def __init__(self, **kwargs):
        schemes = kwargs.pop('schemes', None)
        self.allow_plain_hostname = kwargs.pop('allow_plain_hostname', False)
        super(URLField, self).__init__(**kwargs)
        validator_kwargs = dict(message=_('Enter a valid URL'))
        if schemes is not None:
            validator_kwargs['schemes'] = schemes
        self.validators.append(URLValidator(**validator_kwargs))

    def to_representation(self, value):
        if value is None:
            return ''
        return super(URLField, self).to_representation(value)

    def run_validators(self, value):
        if self.allow_plain_hostname:
            try:
                url_parts = urlparse.urlsplit(value)
                if url_parts.hostname and '.' not in url_parts.hostname:
                    netloc = '{}.local'.format(url_parts.hostname)
                    if url_parts.port:
                        netloc = '{}:{}'.format(netloc, url_parts.port)
                    if url_parts.username:
                        if url_parts.password:
                            netloc = '{}:{}@{}' % (url_parts.username, url_parts.password, netloc)
                        else:
                            netloc = '{}@{}' % (url_parts.username, netloc)
                    value = urlparse.urlunsplit([url_parts.scheme, netloc, url_parts.path, url_parts.query, url_parts.fragment])
            except Exception:
                raise  # If something fails here, just fall through and let the validators check it.
        super(URLField, self).run_validators(value)


class KeyValueField(DictField):
    child = CharField()
    default_error_messages = {
        'invalid_child': _('"{input}" is not a valid string.')
    }

    def to_internal_value(self, data):
        ret = super(KeyValueField, self).to_internal_value(data)
        for value in data.values():
            if not isinstance(value, (str, int, float)):
                if isinstance(value, OrderedDict):
                    value = dict(value)
                self.fail('invalid_child', input=value)
        return ret


class ListTuplesField(ListField):
    default_error_messages = {
        'type_error': _('Expected a list of tuples of max length 2 but got {input_type} instead.'),
    }

    def to_representation(self, value):
        if isinstance(value, (list, tuple)):
            return super(ListTuplesField, self).to_representation(value)
        else:
            self.fail('type_error', input_type=type(value))

    def to_internal_value(self, data):
        if isinstance(data, list):
            for x in data:
                if not isinstance(x, (list, tuple)) or len(x) > 2:
                    self.fail('type_error', input_type=type(x))

            return super(ListTuplesField, self).to_internal_value(data)
        else:
            self.fail('type_error', input_type=type(data))
