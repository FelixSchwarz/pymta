#!/usr/bin/env python

import gzip
import os
from StringIO import StringIO
import subprocess
import tarfile


def build_documentation(project_dir):
    doc_dir = os.path.join(project_dir, 'docs')
    subprocess.call(['make', 'html'], cwd=doc_dir)

def make_relative_filename(topdir, filename):
    assert filename.startswith(topdir)
    relative_filename = filename[len(topdir):]
    if relative_filename.startswith(os.sep):
        relative_filename = relative_filename[len(os.sep):]
    return relative_filename

def make_tarname(topdir, filename, path_prefix):
    relative_name = make_relative_filename(topdir, filename)
    tarname = '%s/%s' % (path_prefix, relative_name)
    return tarname

def create_tarball(project_dir, path_prefix):
    tar_fp = StringIO()
    tar = tarfile.open(fileobj=tar_fp, mode='w')
    
    filenames = ['docs', 'examples', 'pymta', 'tests', 'Changelog.txt', 'COPYING.txt', 'setup.py']
    for filename in filenames:
        filename = os.path.join(project_dir, filename)
        if os.path.isfile(filename):
            tarname = make_tarname(project_dir, filename, path_prefix)
            tar.add(filename, arcname=tarname)
        else:
            for (root, dirs, files) in os.walk(filename):
                for dirname in dirs:
                    tarname = make_tarname(project_dir, dirname, path_prefix)
                    tar.add(dirname, arcname=tarname)
                for fname in files:
                    if not fname.endswith('.pyc'):
                        fname = os.path.join(root, fname)
                        tarname = make_tarname(project_dir, fname, path_prefix)
                        tar.add(fname, tarname)
    tar.add('build/html', arcname='%s/docs/html' % path_prefix)
    tar.close()
    tar_fp.seek(0,0)
    return tar_fp

def main():
    # TODO: Get this from release.py
    name = 'pymta'
    release = '0.3.1'
    
    this_dir = os.path.abspath(os.path.dirname(__file__))
    build_documentation(this_dir)
    tar_fp = create_tarball(this_dir, '%s-%s' % (name, release))
    
    gz_filename = '%s-%s.tar.gz' % (name, release)
    gzip.open(gz_filename, 'wb').write(tar_fp.read())

if __name__ == '__main__':
    main()


