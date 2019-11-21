#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2013 Concentric Sky, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from setuptools import setup, find_packages
import re
import os
import sys

name = 'django-sky-visitor'
package = 'sky_visitor'
description = 'Extension to the django authentication/user system.'
url = 'http://github.com/concentricsky/django-sky-visitor/'
author = 'Concentric Sky'
author_email = 'django@concentricsky.com'
license = 'Apache 2.0'
install_requires = []
classifiers = [
    'Operating System :: MacOS :: MacOS X',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python',
    'Framework :: Django',
    'License :: OSI Approved :: Apache Software License',
    'Topic :: Software Development :: Libraries',
]

try:
    longdesc = open('README.md').read()
except Exception:
    longdesc = description

def get_version():
    """
    Return package version as listed in `sky_visitor.__version__` in `init.py`.
    """
    import sky_visitor
    return '.'.join([str(i) for i in sky_visitor.__version__])


def get_package_data(packages):
    """
    Return all files under the root package, that are not in a
    package themselves.
    """
    result = {}
    for package in packages:
        walk = [(dirpath.replace(package + os.sep, '', 1), filenames)
                for dirpath, dirnames, filenames in os.walk(package)
                if not os.path.exists(os.path.join(dirpath, '__init__.py'))]

        filepaths = []
        for base, filenames in walk:
            filepaths.extend([os.path.join(base, filename)
                              for filename in filenames])
        result[package]=filepaths
    return result

if sys.argv[-1] == 'publish':
    os.system("python setup.py sdist upload")
    args = {'version': get_version(name)}
    print("You probably want to also tag the version now:")
    print(("  git tag -a %(version)s -m 'version %(version)s'" % args))
    print("  git push --tags")
    sys.exit()

setup(
    name=name,
    version=get_version(),
    url=url,
    license=license,
    long_description=longdesc,
    description=description,
    author=author,
    author_email=author_email,
    packages=find_packages(),
    package_data=get_package_data(['example_project', 'sky_visitor']),
    install_requires=install_requires,
)



