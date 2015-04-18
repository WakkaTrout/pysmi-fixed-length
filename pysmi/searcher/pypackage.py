import os
import sys
import time
import imp
import struct
from pysmi.searcher.base import AbstractSearcher
from pysmi.searcher.pyfile import PyFileSearcher
from pysmi import debug
from pysmi import error

class PyPackageSearcher(AbstractSearcher):
    suffixes = {}
    for sfx, mode, typ in imp.get_suffixes():
        if typ not in suffixes:
            suffixes[typ] = []
        suffixes[typ].append((sfx, mode))

    def __init__(self, package):
        self._package = package

    def __str__(self):
        return '%s{"%s"}' % (self.__class__.__name__, self._package)

    def _parseDosTime(self, dosdate, dostime):
        t = (((dosdate >> 9) & 0x7f) + 1980,   # year
             ((dosdate >> 5) & 0x0f),          # month
             dosdate & 0x1f,                   # mday
             (dostime >> 11) & 0x1f,           # hour
             (dostime >> 5) & 0x3f,            # min
             (dostime & 0x1f) * 2,             # sec
             -1,                               # wday
             -1,                               # yday
             -1)                               # dst
        return time.mktime(t)

    def getTimestamp(self, mibname, rebuild=False):
        if rebuild:
            debug.logger & debug.flagSearcher and debug.logger('pretend %s is very old' % mibname)
            return 0  # beginning of time
        try:
            p = __import__(self._package, globals(), locals(), ['__init__'])
            if hasattr(p, '__loader__') and hasattr(p.__loader__, '_files'):
                self.__loader = p.__loader__
                self._package = self._package.replace('.', os.sep)
                debug.logger & debug.flagSearcher and debug.logger('%s is an importable egg at %s' % (self._package, os.path.split(p.__file__)[0]))
            else:
                debug.logger & debug.flagSearcher and debug.logger('%s is not an egg, trying it as a package directory' % self._package)
                return PyFileSearcher(os.path.split(p.__file__)[0]).getTimestamp(mibname)

        except ImportError:
            raise error.PySmiCompiledFileNotFoundError('%s is not importable, trying as a path' % self._package, searcher=self)

        for format in imp.PY_COMPILED, imp.PY_SOURCE:
            for pySfx, pyMode in self.suffixes[format]:
                f = os.path.join(self._package, mibname.upper()) + pySfx
                if f not in self.__loader._files:
                    debug.logger & debug.flagSearcher and debug.logger('%s is not in %s' % (f, self._package))
                    continue
                if format == imp.PY_COMPILED:
                    pyData = self.__loader.get_data(f)
                    if pyData[:4] == imp.get_magic():
                        pyData = pyData[4:]
                        pyTime = struct.unpack('<L', pyData[:4])[0]
                        debug.logger & debug.flagSearcher and debug.logger('found %s, mtime %s' % (f, time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(pyTime))))
                        return pyTime
                    else:
                        debug.logger & debug.flagSearcher and debug.logger('bad magic in %s' % f)
                        continue
                else:
                    pyTime = self._parseDosTime(
                        self.__loader._files[f][6],
                        self.__loader._files[f][5]
                    )

                    debug.logger & debug.flagSearcher and debug.logger('found %s, mtime %s' % (f, time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(pyTime))))
                    return pyTime

        raise error.PySmiCompiledFileNotFoundError('no file %s found' % mibname, searcher=self)

if __name__ == '__main__':
    from pysmi import debug

    debug.setLogger(debug.Debug('all'))

    f = PyPackageSearcher('pysnmp.smi.mibs')
    f.getTimestamp('SNMPv2-SMI')

    f = PyPackageSearcher('pysnmp_mibs')
    f.getTimestamp('SNMP-REPEATER-MIB')

