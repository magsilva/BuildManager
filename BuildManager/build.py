from BuildManager.fileutil import *
from BuildManager.package import *
from BuildManager import *
import thread
import popen2
import select
import fcntl
import sys, os
import time
import shutil

__all__ = ["PackageBuilder"]

GLOBAL_PKGLIST_LOCK = thread.allocate_lock()

STAGE_UNPACK = 0
STAGE_PREP = 1
STAGE_COMPILE = 2
STAGE_INSTALL = 3
STAGE_SOURCE = 4
STAGE_BINARY = 5
STAGE_ALL = 6

STAGE_DICT = {"unpack": STAGE_UNPACK,
              "prep": STAGE_PREP,
              "compile": STAGE_COMPILE,
              "install": STAGE_INSTALL,
              "source": STAGE_SOURCE,
              "binary": STAGE_BINARY,
              "all": STAGE_ALL}

class PackageBuilder(object):
    def __init__(self, opts):
        self.opts = opts
        self.stage = STAGE_DICT[opts.mode]

    def run(self):
        self.pkglist = PackageList()
        logger.info("creating package list")
        for filename in self.opts.args:
            # Get filename extension
            ext = ""
            try:
                ext = filename[ filename.rindex(".") + 1: ]
            except ValueError:
                pass

            if not ext:
               raise Error, "unknown file extension of " + filename

            # Setting the filename extension to CamelCase
            ext = ext[0].upper() + ext[1:].lower()

            if not globals().has_key(ext + "Package"):
               raise Error, "unknown package extension of " + filename

            pkg = globals()[ext + "Package"](filename, self.opts.build_log)
            for ignore in self.opts.ignore:
                if ignore.match(pkg.name):
                    break
            else:
                self.pkglist.append(pkg)
 
        for directory in self.opts.filter_renew:
            self.filterpkglist(self.pkglist, directory, "not_has_ge")
        for directory in self.opts.filter_refresh:
            self.filterpkglist(self.pkglist, directory, "not_has_lt")

        self.pkgsleft = len(self.pkglist)
        if self.pkgsleft == 0:
            logger.info("no packages to process")
            return True

        logger.info("package list has %d packages" % self.pkgsleft)

        self.pkglist_lock = thread.allocate_lock()
        self.failures = 0
        if self.opts.parallel != 1:
            logger.info("starting threads")
            for i in range(self.opts.parallel-1):
                thread.start_new_thread(self.processlist, ())
        self.processlist()
        while self.pkgsleft > 0:
            time.sleep(2)
        return not self.failures

    def processlist(self):
        while 1:
            self.pkglist_lock.acquire()

            # No more work to do
            if not self.pkglist:
                self.pkglist_lock.release()
                return 1

            logger.info("package list has %d packages" % self.pkgsleft)
            pkg = self.pkglist.pop(0)
            self.pkglist_lock.release()

            logger.info("processing package %s-%s-%s" % (pkg.name, pkg.version, pkg.release))

            ret = self.buildpkg(pkg = pkg,
                           stage = self.stage,
                           unpack_dir = self.opts.unpack_dir,
                           rpm_dirs = self.opts.rpm_dirs,
                           passtrough = "" . join(self.opts.options),
                           show_log = self.opts.show_log,
                           dryrun = self.opts.dryrun)

            if ret:
                if pkg.type == "srpm":
                    if self.opts.move_succeeded_srpm:
                        move_file(pkg.file, self.opts.move_succeeded_srpm, dryrun=self.opts.dryrun)
                    elif self.opts.copy_succeeded_srpm:
                        copy_file(pkg.file, self.opts.copy_succeeded_srpm, dryrun=self.opts.dryrun)
                    elif self.opts.remove_succeeded_srpm:
                        logger.info("removing %s" % pkg.file)
                        if not self.opts.dryrun:
                            os.unlink(pkg.file)
                if self.opts.move_srpm:
                    directory = os.path.join(pkg.builddir, self.opts.dirs["srpms"])
                    for f in os.listdir(directory):
                        move_file(os.path.join(directory, f), self.opts.move_srpm, dryrun=self.opts.dryrun)
                if self.opts.move_rpm:
                    directory = os.path.join(pkg.builddir, self.opts.dirs["rpms"])
                    for subdir in os.listdir(directory):
                        subdir = os.path.join(directory, subdir)
                        for f in os.listdir(subdir):
                            move_file(os.path.join(subdir, f), self.opts.move_rpm, dryrun=self.opts.dryrun)
                if self.opts.move_log:
                    move_file(pkg.log, self.opts.move_log, dryrun=self.opts.dryrun)
                if self.opts.clean or self.opts.clean_on_success:
                    if pkg.builddir != "/":
                        logger.info("cleaning build directory")
                        if not self.opts.dryrun:
                            shutil.rmtree(pkg.builddir)
            else:
                self.failures += 1
                if pkg.type == "srpm":
                    if self.opts.move_failed_srpm:
                        move_file(pkg.file, self.opts.move_failed_srpm, dryrun=self.opts.dryrun)
                    elif self.opts.copy_failed_srpm:
                        copy_file(pkg.file, self.opts.copy_failed_srpm, dryrun=self.opts.dryrun)
                    elif self.opts.remove_failed_srpm:
                        logger.info("removing %s" % pkg.file)
                        if not self.opts.dryrun:
                            os.unlink(pkg.file)
                if self.opts.move_failed_log:
                    move_file(pkg.log, self.opts.move_failed_log, dryrun=self.opts.dryrun)
                if self.opts.clean:
                    if pkg.builddir != "/":
                        logger.info("cleaning build directory")
                        if not self.opts.dryrun:
                            shutil.rmtree(pkg.builddir)
            self.pkglist_lock.acquire()
            self.pkgsleft -= 1
            self.pkglist_lock.release()

    def filterpkglist(self, pkglist, directory, rule):
        filterlist = PackageList()
        logger.info("creating package list filter for " + directory)
        for filename in os.listdir(directory):
            filename = os.path.join(directory, filename)
            if os.path.isfile(filename):
                filterlist.append(Package(filename))
        logger.info("filtering")
        if rule[:4] == "not_":
            filterfunc_tmp = getattr(filterlist, rule[4:])
            filterfunc = lambda x: not filterfunc_tmp(x)
        else:
            filterfunc = getattr(filterlist, rule)
        pkglist[:] = filter(filterfunc, pkglist)


    def buildpkglist(self, pkglist, stage, unpack_dir, rpm_dirs, passtrough="", show_log=0, dryrun=0):
        while 1:
            GLOBAL_PKGLIST_LOCK.acquire()
            if not pkglist:
                GLOBAL_PKGLIST_LOCK.release()
                return 1
            pkg = pkglist.pop(0)
            GLOBAL_PKGLIST_LOCK.release()
            self.buildpkg(pkg, stage, unpack_dir, rpm_dirs, passtrough, show_log, dryrun)

    def buildpkg(self, pkg, stage, unpack_dir, rpm_dirs, passtrough="", show_log=0, dryrun=0):
        stagestr = ["unpacking",
                    "running prep stage",
                    "running prep and compile stage",
                    "running prep, compile, and install stages",
                    "building source package",
                    "building binary packages",
                    "building source and binary packages"][stage]
        logger.info(stagestr)
        ret = 0
        if pkg.type == "srpm" and not (dryrun or pkg.unpack(unpack_dir, rpm_dirs)):
            logger.error("failed unpacking")
            return 0
        else:
            status = 0
            if stage != STAGE_UNPACK:
                stagechar = ["p","c","i","s","b","a"][stage-1]
                if not dryrun and os.path.isdir( os.path.join( pkg.builddir, rpm_dirs["buildroot"] ) ):
                    tmppath = " --define '_tmppath %s/%s'" % pkg.builddir, rpm_dirs["buildroot"]
                else:
                    tmppath = ""
                cmd = "rpmbuild -b%s " \
                    " --define '_topdir %s%s'" \
                    " --define '_specdir %s'" \
                    " --define '_builddir %s'" \
                    " --define '_sourcedir %s'" \
                    " --define '_srcrpmdir %s'" \
                    " --define '_rpmdir %s' " \
                    " %s %s 2>&1" % (
                    stagechar,
                    pkg.builddir, tmppath,
                    rpm_dirs["specs"],
                    rpm_dirs["build"],
                    rpm_dirs["sources"],
                    rpm_dirs["srpms"],
                    rpm_dirs["rpms"],
                    passtrough,
                    pkg.spec )

                logger.debug("rpmbuild command: " + cmd)
                if not dryrun:
                    log = open(pkg.log, "w")
                    pop = popen2.Popen3(cmd)
                    fc = pop.fromchild
                    flags = fcntl.fcntl (fc.fileno(), fcntl.F_GETFL, 0)
                    flags = flags | os.O_NONBLOCK
                    fcntl.fcntl (fc.fileno(), fcntl.F_SETFL, flags)
                    while 1:
                        r,w,x = select.select([fc.fileno()], [], [], 2)
                        if r:
                            data = fc.read()
                            if show_log:
                                sys.stdout.write(data)
                            log.write(data)
                            log.flush()
                        status = pop.poll()
                        if status != -1:
                            break
                    log.close()
            if status == 0:
                logger.info("succeeded!")
                ret = 1
            else:
                logger.error("failed!")
                ret = 0
        return ret

# vim:et:ts=4:sw=4
