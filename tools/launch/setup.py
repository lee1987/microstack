from setuptools import setup, find_packages

setup(
    name="microstack_launch",
    description="Launch an instance!",
    packages=find_packages(exclude=("tests",)),
    version="0.0.1",
    entry_points={
        'console_scripts': [
            'microstack_launch = launch.main:main',
        ],
    },
)
