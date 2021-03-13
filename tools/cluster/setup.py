from setuptools import setup, find_packages

setup(
    name="microstack_cluster",
    description="Clustering client and server.",
    packages=find_packages(exclude=("tests",)),
    version="0.0.1",
    entry_points={
        'console_scripts': [
            'microstack_join = cluster.client:join',
            'microstack_add_compute = cluster.add_compute:main',
        ],
    }
)
