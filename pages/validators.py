import re

from django.core.exceptions import ValidationError


ROOT_RELATIVE_URL_REGEX = re.compile(ur'^/([a-z0-9\-]+/)*$')

def is_root_relative_url(value):
    return bool(ROOT_RELATIVE_URL_REGEX.match(value) is not None)

def root_relative_url(value):
    if not is_root_relative_url(value):
        raise ValidationError("The URL must start and end with a slash, and "
                              "it can only contain letters, numbers, hyphens "
                              "(-), and underscores (_).")

