#!/usr/bin/env python
from setuptools import setup, find_packages
import io
import os
import sys


version = sys.version_info[:2]
if version < (3, 9):
    print('thebleep requires Python version 3.9 or later' +
          ' ({}.{} detected).'.format(*version))
    sys.exit(-1)

VERSION = '4.0.0'

# The README is the PyPI page. Read with an explicit encoding: it has em dashes
# and arrow keys in it, and a build on a machine whose default encoding is not
# UTF-8 would fail on them.
here = os.path.dirname(os.path.abspath(__file__))
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as readme:
    long_description = readme.read()

install_requires = ['psutil', 'colorama', 'decorator', 'pyte']
extras_require = {":sys_platform=='win32'": ['win_unicode_console']}

if sys.platform == "win32":
    scripts = ['scripts\\bleep.bat', 'scripts\\bleep.ps1']
    entry_points = {'console_scripts': [
        'thebleep = thebleep.entrypoints.main:main',
        'thebleep_firstuse = thebleep.entrypoints.not_configured:main']}
else:
    scripts = []
    entry_points = {'console_scripts': [
        'thebleep = thebleep.entrypoints.main:main',
        'bleep = thebleep.entrypoints.not_configured:main']}

setup(name='thebleep',
      version=VERSION,
      description='Corrects your previous console command. The maintained'
                  ' successor to The Fuck.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Miroslav Stampar',
      author_email='miroslav.stampar@gmail.com',
      url='https://github.com/stamparm/thebleep',
      project_urls={
          'Source': 'https://github.com/stamparm/thebleep',
          'Issues': 'https://github.com/stamparm/thebleep/issues',
          'Changelog':
              'https://github.com/stamparm/thebleep/blob/master/CHANGELOG.md',
      },
      license='MIT',
      keywords='shell console command correction typo cli productivity',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'Operating System :: MacOS',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Programming Language :: Python :: 3.11',
          'Programming Language :: Python :: 3.12',
          'Programming Language :: Python :: 3.13',
          'Programming Language :: Python :: 3.14',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Software Development',
          'Topic :: Terminals',
          'Topic :: Utilities',
      ],
      packages=find_packages(exclude=['ez_setup', 'examples',
                                      'tests', 'tests.*', 'release']),
      include_package_data=True,
      zip_safe=False,
      python_requires='>=3.9',
      install_requires=install_requires,
      extras_require=extras_require,
      scripts=scripts,
      entry_points=entry_points)
