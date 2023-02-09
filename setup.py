#!/usr/bin/env python3
# encoding: utf-8
"""Python library for interfacing with Motion Blinds."""
import pathlib
from setuptools import find_packages, setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

setup(name='motionblinds',
      version='0.6.16',
      description='Python library for interfacing with Motion Blinds',
      long_description=README,
      long_description_content_type="text/markdown",
      url='https://github.com/starkillerOG/motion-blinds',
      author='starkillerOG',
      author_email='starkiller.og@gmail.com',
      license='MIT',
      packages=find_packages(),
      python_requires='>=3.6',
      install_requires=['pycryptodomex'],
      tests_require=[],
      platforms=['any'],
      zip_safe=False,
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: BSD License",
          "Operating System :: OS Independent",
          "Topic :: Software Development :: Libraries",
          "Topic :: Home Automation",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
          ])