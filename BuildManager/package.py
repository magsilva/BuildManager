from BuildManager import *
from UserList import UserList
import commands
import string
import os

try:
    import rpm
except ImportError:
    rpm = None

__all__ = ["Package", "SpecPackage", "RpmPackage", "PackageList"]

class Package(object):
    def __init__(self, file, log):
        self.file = file
        self.absfile = os.path.abspath(file)
        self.type = None
        self.name = None
        self.version = None
        self.release = None
        self.epoch = None
        self.spec = None
        self.builddir = None
        self.log = log

    def __cmp__(self, pkg):
        def rpmvercmp(a, b):
            if a == b:
                return 0
            ai = 0
            bi = 0
            la = len(a)
            lb = len(b)
            while ai < la and bi < lb:
                while ai < la and not a[ai].isalnum(): ai += 1
                while bi < lb and not b[bi].isalnum(): bi += 1
                aj = ai
                bj = bi
                if a[aj].isdigit():
                    while aj < la and a[aj].isdigit(): aj += 1
                    while bj < lb and b[bj].isdigit(): bj += 1
                    isnum = 1
                else:
                    while aj < la and a[aj].isalpha(): aj += 1
                    while bj < lb and b[bj].isalpha(): bj += 1
                    isnum = 0
                if aj == ai or bj == bi:
                    return -1
                if isnum:
                    while ai < la and a[ai] == '0': ai += 1
                    while bi < lb and b[bi] == '0': bi += 1
                    if aj-ai > bj-bi: return 1
                    if bj-bi > aj-ai: return -1
                rc = cmp(a[ai:aj], b[bi:bj])
                if rc:
                    return rc
                ai = aj
                bi = bj
            if ai == la and bi == lb:
                return 0
            if ai == la:
                return -1
            else:
                return 1

        # compare epochs
        if self.epoch and not pkg.epoch:
            return 1
        if not self.epoch and pkg.epoch:
            return -1
        if self.epoch and pkg.epoch:
            if self.epoch < pkg.epoch:
                return -1
            if self.epoch > pkg.epoch:
                return 1

        # compare version and release
        rc = rpmvercmp( self.version, pkg.version)
        if rc:
            return rc
        return rpmvercmp( self.release, self.release)

    def get_build_dir(self):
        pass

    def create_builddir(self, unpackdir, rpm_dirs):
        unpackdir = os.path.abspath(unpackdir)
        builddir = self.get_build_dir()
        for directory in rpm_dirs:
            try:
                os.mkdir( os.path.join(unpackdir, directory))
            except OSError, e:
                if ( e.errno == 13 ):
                    raise Error, "couldn't create directory for RPM processing"
        return builddir


class SpecPackage(Package):
    def get_build_dir(self):
       return os.path.dirname(os.path.dirname(self.absfile))

    def __init__(self, file, log):
        def rpm_vars(str, vars):
            end = -1
            ret = []
            while 1:
                start = string.find(str, "%{", end+1)
                if start == -1:
                    ret.append(str[end+1:])
                    break
                ret.append(str[end+1:start])
                end = string.find(str, "}", start)
                if end == -1:
                    ret.append(str[start:])
                    break
                varname = str[start+2:end]
                if vars.has_key(varname):
                    ret.append(vars[varname])
                else:
                    ret.append(str[start:end+1])
            return string.join(ret,"")

        super(SpecPackage, self).__init__(file, log)
        self.spec = self.absfile
        self.builddir = os.path.dirname(os.path.dirname(self.absfile))
        try:
            f = open(self.spec,"r")
        except IOError:
            raise Error, "couldn't open spec file %s" % self.absfile

        defines = {}
        for line in f.readlines():
            lowerline = string.lower(line)
            if not self.name and lowerline[:5] == "name:":
                self.name = rpm_vars(string.strip(line[5:]), defines)
            elif not self.version and lowerline[:8] == "version:":
                self.version = rpm_vars(string.strip(line[8:]), defines)
            elif not self.release and lowerline[:8] == "release:":
                self.release = rpm_vars(string.strip(line[8:]), defines)
            elif lowerline[:7] == "%define":
                token = string.split(line[7:])
                if len(token) == 2:
                    defines[token[0]] = rpm_vars(token[1], defines)
            if self.name and self.version and self.release:
                break
        else:
            raise Error, "spec file %s doesn't define name, version or release" % self.file
        self.type = "spec"

        self.log = os.path.join( self.builddir, self.name + ".log" )


class RpmPackage(Package):
    def get_build_dir(self):
        unpackdir = os.path.abspath(self.unpackdir)
        return "%s/%s-%s-%s-topdir" % (unpackdir, self.name, self.version, self.release)

    def __init__(self, file, log):
        super(RpmPackage, self).__init__(file, log)
        # Try to find out RPM package's information from RPM database
        if not rpm:
            cmd = "rpm -qp --queryformat='%%{NAME} %%{EPOCH} %%{VERSION} %%{RELEASE} %%{SOURCERPM}' %s " %self.file
            status, output = commands.getstatusoutput(cmd)
            if status != 0:
                raise Error, "error querying rpm file %s" % self.file
            else:
                tokens = string.split(output, " ")
                if len(tokens) != 5:
                    raise Error, "unexpected output querying rpm file %s: %s" % (self.file, output)
                else:
                    self.name, self.epoch, self.version, self.release, srpm = tokens
                    if self.epoch == "(none)":
                        self.epoch = None
                    if srpm != "(none)":
                        self.type = "rpm"
                    else:
                        self.type = "srpm"
        else:
            # Boost up query if rpm module is available
            f = open(self.file)
            if hasattr(rpm, "headerFromPackage"):
                h = rpm.headerFromPackage(f.fileno())[0]
            else:
                ts = rpm.TransactionSet()
                h = ts.hdrFromFdno(f.fileno())
            f.close()
            self.name = h[rpm.RPMTAG_NAME]
            self.epoch = h[rpm.RPMTAG_EPOCH]
            self.version = h[rpm.RPMTAG_VERSION]
            self.release = h[rpm.RPMTAG_RELEASE]
            if h[rpm.RPMTAG_SOURCERPM]:
                self.type = "rpm"
            else:
                self.type = "srpm"

        self.log = os.path.join( self.unpackdir, self.name + ".log" )

    def unpack(self, unpackdir, rpm_dirs):
        if self.type == "srpm":
            self.builddir = self.create_builddir(unpackdir, rpm_dirs)
            if self.builddir:
                return self.install_srpm( rpm_dirs )    
    
    def install_srpm(self, rpm_dirs):
        cmd = "rpm -i" \
            " --define '_topdir %s'" \
            " --define '_specdir %s'" \
            " --define '_builddir %s'" \
            " --define '_sourcedir %s'" \
            " --define '_srcrpmdir %s'" \
            " --define '_rpmdir %s'" \
            " %s &> %s" % (
            self.builddir,
            rpm_dirs["specs"],
            rpm_dirs["build"],
            rpm_dirs["sources"],
            rpm_dirs["srpms"],
            rpm_dirs["rpms"],
            self.file,
            self.log )
        status, output = commands.getstatusoutput(cmd)
        if status != 0:
            raise Error, "error installing package " + self.file
        else:
            spec = os.path.join(self.builddir, rpm_dirs["specs"], self.name + ".spec")
            if not os.path.isfile(spec):
                listdir = os.listdir(os.path.join( self.builddir, rpm_dirs["specs"]))
                for f in listdir[:]:
                    if f[-len(".spec"):] != ".spec":
                        listdir.remove(f)
                if len(listdir) != 1:
                    raise Error, "can't guess spec file for " + self.file
                else:
                    self.spec = os.path.join(self.builddir, rpm_dirs["specs"], listdir[0])
                    return 1
            else:
                self.spec = spec
                return 1


class PackageList(UserList):
    def has_lt(self, pkg):
        for mypkg in self.data:
            if mypkg.name == pkg.name \
               and mypkg.type == pkg.type \
               and mypkg < pkg:
                return 1
        return 0

    def has_le(self, pkg):
        for mypkg in self.data:
            if mypkg.name == pkg.name \
               and mypkg.type == pkg.type \
               and mypkg <= pkg:
                return 1
        return 0
    
    def has_eq(self, pkg):
        for mypkg in self.data:
            if mypkg.name == pkg.name \
               and mypkg.type == pkg.type \
               and mypkg == pkg:
                return 1
        return 0
    
    def has_ge(self, pkg):
        for mypkg in self.data:
            if mypkg.name == pkg.name \
               and mypkg.type == pkg.type \
               and mypkg >= pkg:
                return 1
        return 0

    def has_gt(self, pkg):
        for mypkg in self.data:
            if mypkg.name == pkg.name \
               and mypkg.type == pkg.type \
               and mypkg > pkg:
                return 1
        return 0

# vim:ts=4:sw=4:et
