from setuptools import setup

setup(
    name = 'polytaxis-monitor',
    version = '0.0.1',
    author = 'Rendaw',
    author_email = 'spoo@zarbosoft.com',
    url = 'https://github.com/Rendaw/polytaxis-monitor',
    download_url = 'https://github.com/Rendaw/polytaxis-monitor/tarball/v0.0.1',
    license = 'BSD',
    description = 'Indexes polytaxis tags for lookup by various programs',
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
    ],
    packages = [
        'polytaxis_monitor', 
        'ptq', 
    ],
    entry_points = {
        'console_scripts': [
            'polytaxis-monitor = polytaxis_monitor.main:main',
            'ptq = ptq.main:main',
        ],
    },
)
