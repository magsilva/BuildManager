#!/usr/bin/python
from BuildManager import Error
import optparse

__all__ = ["OptionParser"]

class CapitalizeHelpFormatter(optparse.IndentedHelpFormatter):

    def format_usage(self, usage):
        return optparse.IndentedHelpFormatter.format_usage(self, usage).capitalize()

    def format_heading(self, heading):
        return optparse.IndentedHelpFormatter.format_heading(self, heading).capitalize()

class OptionParser(optparse.OptionParser):

    def __init__(self, usage=None, help=None, **kwargs):
        if not "formatter" in kwargs:
            kwargs["formatter"] = CapitalizeHelpFormatter()
        optparse.OptionParser.__init__(self, usage, **kwargs)
        self._overload_help = help

    def format_help(self, formatter=None):
        if self._overload_help:
            return self._overload_help
        else:
            return optparse.OptionParser.format_help(self, formatter)

    def error(self, msg):
        raise Error, msg

# vim:et:ts=4:sw=4
