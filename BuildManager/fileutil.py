# This module was originally part of distutils.
from BuildManager import *
import os

__all__ = ["copy_file", "move_file"]

# for generating verbose output in 'copy_file()'
_copy_action = { None:   'copying',
                 'hard': 'hard linking',
                 'sym':  'symbolically linking' }


def _copy_file_contents (src, dst, buffer_size=16*1024):
    """Copy the file 'src' to 'dst'; both must be filenames.  Any error
    opening either file, reading from 'src', or writing to 'dst', raises
    BuildManagerFileError.  Data is read/written in chunks of 'buffer_size'
    bytes (default 16k).  No attempt is made to handle anything apart from
    regular files.
    """
    # Stolen from shutil module in the standard library, but with
    # custom error-handling added.

    fsrc = None
    fdst = None
    try:
        try:
            fsrc = open(src, 'rb')
        except os.error, (errno, errstr):
            raise Error, "could not open %s: %s" % (src, errstr)
        
        try:
            fdst = open(dst, 'wb')
        except os.error, (errno, errstr):
            raise Error, "could not create %s: %s" % (dst, errstr)
        
        while 1:
            try:
                buf = fsrc.read(buffer_size)
            except os.error, (errno, errstr):
                raise Error, "could not read from %s: %s" % (src, errstr)
            
            if not buf:
                break

            try:
                fdst.write(buf)
            except os.error, (errno, errstr):
                raise Error, "could not write to %s: %s" % (dst, errstr)
            
    finally:
        if fdst:
            fdst.close()
        if fsrc:
            fsrc.close()

def copy_file (src, dst, preserve_mode=1, preserve_times=1, link=None,
               dryrun=False):

    """Copy a file 'src' to 'dst'.  If 'dst' is a directory, then 'src' is
    copied there with the same name; otherwise, it must be a filename.  (If
    the file exists, it will be ruthlessly clobbered.)  If 'preserve_mode'
    is true (the default), the file's mode (type and permission bits, or
    whatever is analogous on the current platform) is copied.  If
    'preserve_times' is true (the default), the last-modified and
    last-access times are copied as well. 

    'link' allows you to make hard links (os.link) or symbolic links
    (os.symlink) instead of copying: set it to "hard" or "sym"; if it is
    None (the default), files are copied.  Don't set 'link' on systems that
    don't support it: 'copy_file()' doesn't check if hard or symbolic
    linking is available.

    Under Mac OS, uses the native file copy function in macostools; on
    other systems, uses '_copy_file_contents()' to copy file contents.

    Return a tuple (dest_name, copied): 'dest_name' is the actual name of
    the output file, and 'copied' is true if the file was copied (or would
    have been copied, if 'dryrun' true).
    """
    from stat import ST_ATIME, ST_MTIME, ST_MODE, S_IMODE

    if not os.path.isfile(src):
        raise Error, "can't copy '%s': doesn't exist or not a regular file" % src

    if os.path.isdir(dst):
        directory = dst
        dst = os.path.join(dst, os.path.basename(src))
    else:
        directory = os.path.dirname(dst)

    try:
        action = _copy_action[link]
    except KeyError:
        raise ValueError, "invalid value '%s' for 'link' argument" % link
    if os.path.basename(dst) == os.path.basename(src):
        logger.info("%s %s to %s" % (action, src, directory))
    else:
        logger.info("%s %s to %s" % (action, src, dst))
            
    if dryrun:
        return (dst, 1)

    # If linking (hard or symbolic), use the appropriate system call
    # (Unix only, of course, but that's the caller's responsibility)
    if link == 'hard':
        if not (os.path.exists(dst) and os.path.samefile(src, dst)):
            os.link(src, dst)
    elif link == 'sym':
        if not (os.path.exists(dst) and os.path.samefile(src, dst)):
            os.symlink(src, dst)

    # Otherwise (not linking), copy the file contents and
    # (optionally) copy the times and mode.
    else:
        _copy_file_contents(src, dst)
        if preserve_mode or preserve_times:
            st = os.stat(src)
            if preserve_times:
                os.utime(dst, (st[ST_ATIME], st[ST_MTIME]))
            if preserve_mode:
                os.chmod(dst, S_IMODE(st[ST_MODE]))

    return (dst, 1)

def move_file (src, dst, dryrun=False):

    """Move a file 'src' to 'dst'.  If 'dst' is a directory, the file will
    be moved into it with the same name; otherwise, 'src' is just renamed
    to 'dst'.  Return the new full name of the file.

    Handles cross-device moves on Unix using 'copy_file()'.  What about
    other systems???
    """
    from os.path import exists, isfile, isdir, basename, dirname
    import errno
    
    logger.info("moving %s to %s" % (src, dst))

    if dryrun:
        return dst

    if not isfile(src):
        raise Error, "can't move %s: not a regular file" % src

    if isdir(dst):
        dst = os.path.join(dst, basename(src))
    elif exists(dst):
        raise Error, "can't move %s: destination %s already exists" % (src, dst)

    if not isdir(dirname(dst)):
        raise Error, "can't move %s: destination %s not a valid path" % (src, dst)

    copy_it = 0
    try:
        os.rename(src, dst)
    except os.error, (num, msg):
        if num == errno.EXDEV:
            copy_it = 1
        else:
            raise Error, "couldn't move %s to %s: %s" % (src, dst, msg)

    if copy_it:
        copy_file(src, dst)
        try:
            os.unlink(src)
        except os.error, (num, msg):
            try:
                os.unlink(dst)
            except os.error:
                pass
            raise Error, "couldn't move %s to %s by copy/delete: delete %s failed: %s" % (src, dst, src, msg)

    return dst

def write_file (filename, contents):
    """Create a file with the specified name and write 'contents' (a
    sequence of strings without line terminators) to it.
    """
    f = open(filename, "w")
    for line in contents:
        f.write(line + "\n")
    f.close()

