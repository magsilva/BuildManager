#!/usr/bin/python
from distutils.core import setup
import re

verpat = re.compile("VERSION *= *\"(.*)\"")
data = open("bm").read()
m = verpat.search(data)
if not m:
    sys.exit("error: can't find VERSION")
VERSION = m.group(1)

setup(name="bm",
      version = VERSION,
      description = "BuildManager - rpm package building helper",
      author = "Gustavo Niemeyer",
      author_email = "niemeyer@conectiva.com",
      url = "http://moin.conectiva.com.br/BuildManager",
      license = "GPL",
      long_description =
"""\
BuildManager, or bm, is a program that wraps and extends rpm while building
packages. Its features allow one to batch process thousand of RPMS at once,
controling logs, rpm and srpm moving, filtering the list of files, ignoring
given packages, completely cleaning the build directories, and many other
features.
""",
      packages = ["BuildManager"],
      scripts = ["bm", "bmclean"],
      )
