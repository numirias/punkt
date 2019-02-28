
from os import path
import sys

from setuptools import setup, find_packages


# Open encoding isn't available for Python 2.7 (sigh)
if sys.version_info < (3, 0):
    from io import open

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup_requirements = []
test_requirements = []

setup(
    author='numirias',
    author_email='numirias@users.noreply.github.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.7',
    ],
    description='Dotfiles management',
    entry_points={
        'console_scripts': [
            'punkt=punkt.cli:main',
        ],
    },
    install_requires=[
        'click',
        'colorama',
    ],
    license='MIT license',
    long_description=long_description,
    long_description_content_type='text/markdown',
    # Include data files specified in MANIFEST.in
    include_package_data=True,
    name='punkt',
    packages=find_packages(where='src'),
    package_dir={'':'src'},
    setup_requires=setup_requirements,
    # TODO Needed?
    test_suite='test',
    # TODO Needed?
    tests_require=test_requirements,
    url='https://github.com/numirias/punkt',
    version='0.1',
)
