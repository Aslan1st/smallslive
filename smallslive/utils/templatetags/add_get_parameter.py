from django.template import Library, Node, resolve_variable

register = Library()

"""
The tag generates a parameter string in form '?param1=val1&param2=val2'.
The parameter list is generated by taking all parameters from current
request.GET and optionally overriding them by providing parameters to the tag.

This is a cleaned up version of http://djangosnippets.org/snippets/2105/. It
solves a couple of issues, namely:
 * parameters are optional
 * parameters can have values from request, e.g. request.GET.foo
 * native parsing methods are used for better compatibility and readability
 * shorter tag name

Usage: place this code in your appdir/templatetags/add_get_parameter.py
In template:
{% load add_get_parameter %}
<a href="{% add_get param1='const' param2=variable_in_context %}">
Link with modified params
</a>

It's required that you have 'django.core.context_processors.request' in
TEMPLATE_CONTEXT_PROCESSORS

Original version's URL: http://django.mar.lt/2010/07/add-get-parameter-tag.html
"""


class AddGetParameter(Node):
    def __init__(self, values):
        self.values = values

    def render(self, context):
        req = resolve_variable('request', context)
        params = req.GET.copy()
        for key, value in self.values.items():
            val = value.resolve(context)
            if val:
                params[key] = val
            elif key in params:
                del params[key]
        return '?%s' % params.urlencode()


@register.tag
def add_get(parser, token):
    pairs = token.split_contents()[1:]
    values = {}
    for pair in pairs:
        s = pair.split('=', 1)
        values[s[0]] = parser.compile_filter(s[1])
    return AddGetParameter(values)
