from setuptools import setup, find_packages

setup(
    name="microstack",
    description="The MicroStack command",
    packages=find_packages(exclude=("tests",)),
    version="0.0.1",
    entry_points={
        'console_scripts': [
            'microstack = microstack.main:main',
        ],
    }
)
