from setuptools import setup

setup(
    name='PyEngineIO-Client',
    version='1.0.5-beta',
    url='http://github.com/fuzeman/PyEngineIO-Client/',

    author='Dean Gardiner',
    author_email='me@dgardiner.net',

    description='Client for engine.io',
    packages=['pyengineio_client'],
    platforms='any',

    install_requires=[
        'PyEmitter',
        'PyEngineIO-Parser',

        'requests',
        'requests-futures',
        'websocket-client'
    ],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python'
    ],
)
