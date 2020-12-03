from setuptools import setup

setup(
    name='igloader',
    version='0.1',
    description='HL7(R) FHIR(R) implementation guide uploader (from IG pack file).',
    url='https://github.com/nmdp-bioinformatics/igloader',
    author='Joel Schneider',
    author_email='jschneid@nmdp.org',
    license='Apache 2.0',
    packages=['igloader'],
    install_requires=[
        'requests',
    ]
)
