from BuildManager.fileutil import *
from BuildManager.package import *
from BuildManager import *
import os

class PackageCleaner(object):
    def __init__(self, opts):
        self.opts = opts

    def run(self):
        pkglist = PackageList()
        pkglist_check = PackageList()
        logger.info("creating package list")
        for filename in self.opts.args:
            pkglist.append(Package(filename))
        if self.opts.check:
            for directory in self.opts.check:
                logger.info("creating package check list for " + directory )
                for entry in os.listdir(directory):
                    entrypath = os.path.join(directory, entry)
                    if os.path.isfile(entrypath):
                        pkglist_check.append(Package(entrypath))
        logger.info("processing package list")
        for pkg in pkglist[:]:
            if pkglist.has_gt(pkg) or pkglist_check.has_gt(pkg):
                pkglist.remove(pkg)
                if self.opts.move:
                    move_file(pkg.file, self.opts.move, dryrun=self.opts.dryrun)
                elif self.opts.copy:
                    copy_file(pkg.file, self.opts.copy, dryrun=self.opts.dryrun)
                else:
                    logger.info("removing " + pkg.file)
                    if not self.opts.dryrun:
                        os.unlink(pkg.file)
        return True
