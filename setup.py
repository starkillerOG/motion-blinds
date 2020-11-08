#!/usr/bin/env python3
# encoding: utf-8
"""Python library for interfacing with Motion Blinds."""
from setuptools import find_packages, setup

setup(name='motionblinds',
      version='0.0.0',
      description='Python library for interfacing with Motion Blinds',
      long_description='Python library for interfacing with Motion Blinds',
      url='https://github.com/starkillerOG/motion-blinds',
      author='starkillerOG',
      author_email='starkiller.og@gmail.com',
      license='MIT',
      packages=find_packages(),
      install_requires=['pycryptodomex'],
      tests_require=[],
      platforms=['any'],
      zip_safe=False,
      classifiers=[
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: BSD License",
          "Operating System :: OS Independent",
          "Topic :: Software Development :: Libraries",
          "Topic :: Home Automation",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          ])