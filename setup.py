from setuptools import setup

setup(
    name = 'polytaxis-utils',
    version = '0.0.1',
    author = 'Rendaw',
    author_email = 'spoo@zarbosoft.com',
    url = 'https://github.com/Rendaw/ptutils',
    download_url = 'https://github.com/Rendaw/ptutils/tarball/v0.0.1',
    license = 'BSD',
    description = 'Utilities for working with polytaxis files.',
    long_description = open('readme.md', 'r').read(),
    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
    ],
    install_requires = [
        'polytaxis',
        'appdirs',
        'watchdog',
        'natsort',
        'python-magic',
        'ExifRead',
        'pytaglib',
    ],
    packages = [
        'polytaxis_monitor', 
        'ptq', 
        'polytaxis_import',
        'polytaxis_cleanup',
        'unpt',
    ],
    entry_points = {
        'console_scripts': [
            'polytaxis-monitor = polytaxis_monitor.main:main',
            'ptq = ptq.main:main',
            'polytaxis-import = polytaxis_import.main:main',
            'polytaxis-cleanup = polytaxis_cleanup.main:main',
            'unpt = unpt.main:main',
        ],
    },
)
