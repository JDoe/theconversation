import settings
from markdown import markdown
from lib.markdown.mdx_video import VideoExtension
import datetime as dt

from mongoengine import *
from question import Question
from annotation import Annotation
from user import User
from content import Content

class Link(Content):
    url = StringField(max_length=65000)
    hackpad_id = StringField(max_length=65000)
    has_hackpad = BooleanField()

    def form_fields(self, form_errors=None, form_fields=[]):
        for form_field in form_fields:
            field = self._fields[form_field['name']]
            # Ignore ID field and ignored fields
            if form_field['name'] == self._meta['id_field'] or form_field['name'] in self.ignored_fields:
                continue

            # Fill value
            value = self._data.get(form_field['name'])
            value = value.replace('"', '\\"') if value else ''
            form_field['value'] = value

            # Generate the correct HTML
            field_html = ''
            if field.__class__ == StringField and not field.max_length:
                field_html = '<textarea name="{name}" class="post_{name}"' \
                                            'placeholder="{placeholder}">{value}</textarea>'
                field_html = field_html.format(**form_field)
            if field.__class__ == StringField and field.max_length:
                field_html = '<input name="{name}" type="text" class="post_{name}"' \
                                                ' placeholder="{placeholder}" value="{value}" />'
                field_html = field_html.format(**form_field)
            if field.__class__ == BooleanField:
                field_html = '<input name="{name}" type="checkbox" class="post_{name}"' \
                                        ' value="true" id="post_{name}" checked/>'
                field_html = field_html.format(**form_field)
                if form_field.has_key('label'):
                    label = '<label for="post_{name}" data-selected="{label_selected}">{label}</label>'
                    form_field['label_selected'] = form_field.get('label_selected', '').replace('"', "'")
                    field_html += label.format(**form_field)

            if not field_html:
                continue

            # Wrap the element with the provided wrapping function
            wrapper = form_field.get('wrapper', lambda x: x)
            field_html = wrapper(field_html)

            # Handle errors and return
            field_errors = form_errors.get(form_field['name'])
            yield (form_field['name'], field_html, field_errors)
