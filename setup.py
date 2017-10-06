from setuptools import setup, find_packages

setup(
    name="schoolsoftapi",
    version="0.3.0",
    packages=find_packages(),
    install_requires=['requests', 'xlrd'],
    description="SchooSoft API",
    long_description=open('README.rst').read(),
    author="William Wu",
    author_email="william@pylabs.org",
    url="https://github.com/fossnio/schoolsoftapi",
    license="GPL 3",
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3'
    ]
)
