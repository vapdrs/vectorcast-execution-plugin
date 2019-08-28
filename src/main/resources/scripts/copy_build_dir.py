#
# The MIT License
#
# Copyright 2016 Vector Software, East Greenwich, Rhode Island USA
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
import os
import fnmatch
import sys
import subprocess
import tarfile
import sqlite3
import shutil

global build_dir

def make_relative(path, workspace):
    path = path.replace("\\","/")

    # if the paths match
    if path.startswith(workspace):
        path = path[len(workspace)+1:]
        
    # if the paths match except for first character (d:\ changed to j:\)
    elif path[1:].startswith(workspace[1:]):
        path = path[len(workspace)+1:]
        
    elif "workspace" in path:
        # if paths are different, find the workspace in the jenkins path
        workspaceIndex = path.find("workspace")
        
        path = path[workspaceIndex:].split("/",2)[2]
        
    else:
        print "  Warning: Unable to convert source file: " + path + " to relative path based on WORKSPACE: " + workspace
        # something went wildy wrong -- raise an exception
        # raise Exception ("Problem updating database path to remove workspace:\n\n   PATH: " + path + "\n   WORKSPACE: " + workspace)
    
    return path

    
def updateDatabase(conn, nocase, workspace, updateWhat, updateFrom):
    sql = "SELECT id, %s FROM %s" % (updateWhat, updateFrom)
    files = conn.execute(sql)
    for id_, path in files:
        relative = make_relative(path,workspace)    
        sql = "UPDATE %s SET %s = '%s' WHERE id=%s COLLATE NOCASE" % (updateFrom, updateWhat, relative, id_)
        conn.execute(sql)
        
def addFile(tf, file):
    global build_dir
    for f in os.listdir(build_dir):
        if fnmatch.fnmatch(f, file):
            tf.add(os.path.join(build_dir, f))

def addConvertCoverFile(tf, file, workspace, nocase):
    global build_dir
    
    print "Updating cover.db"
    fullpath = build_dir + os.path.sep + file
    bakpath = fullpath + '.bk'
    if os.path.isfile(fullpath):
        conn = sqlite3.connect(fullpath)
        if conn:
            shutil.copyfile(fullpath, bakpath)

            # update the database paths to be relative from workspace
            updateDatabase(conn, nocase, workspace, "LIS_file", "instrumented_files")
            updateDatabase(conn, nocase, workspace, "display_path", "source_files")
            updateDatabase(conn, nocase, workspace, "path", "source_files")
            
            conn.commit()
            conn.close()
            addFile(tf, file)
            os.remove(fullpath)
            shutil.move(bakpath, fullpath)

def addConvertMasterFile(tf, file, workspace, nocase):
    global build_dir
    print "Updating master.db"
    fullpath = build_dir + os.path.sep + file
    bakpath = fullpath + '.bk'
    if os.path.isfile(fullpath):
        conn = sqlite3.connect(fullpath)
        if conn:
            shutil.copyfile(fullpath, bakpath)
            updateDatabase(conn, nocase, workspace, "path", "sourcefiles")
            conn.commit()
            conn.close()
            addFile(tf, file)
            os.remove(fullpath)
            shutil.move(bakpath, fullpath)

if __name__ == '__main__':
                
    ManageProjectName = sys.argv[1]
    Level = sys.argv[2]
    BaseName = sys.argv[3]
    Env = sys.argv[4]
    workspace = os.getenv("WORKSPACE")
    if sys.platform.startswith('win32'):
        workspace = workspace.replace("\\", "/")
        nocase = "COLLATE NOCASE"
    else:
        nocase = ""

    exe_env = os.environ.copy()
    if 'VECTORCAST_DIR' in os.environ:
        exe_env['PATH'] = os.pathsep.join([os.environ.get('PATH', ''), exe_env['VECTORCAST_DIR']])

    p = subprocess.Popen("manage --project " + ManageProjectName + " --build-directory-name --level " + Level + " -e " + Env,shell=True,stdout=subprocess.PIPE, env=exe_env)
    out, err = p.communicate()
    list = out.split(os.linesep)
    build_dir = ''
    for str in list:
        if "Build Directory:" in str:
            length = len(str.split()[0]) + 1 + len(str.split()[1]) + 1 
            build_dir = os.path.relpath(str[length:])

    if build_dir != "":
        build_dir = build_dir + os.path.sep + Env
        tf = tarfile.open(BaseName + "_build.tar", mode='w')
        try:
            addConvertCoverFile (tf, "cover.db", workspace, nocase)
            addConvertMasterFile(tf, "master.db", workspace, nocase)
            addFile(tf, "testcase.db")
            addFile(tf, "COMMONDB.VCD")
            addFile(tf, "UNITDATA.VCD")
            addFile(tf, "UNITDYNA.VCD")
            addFile(tf, "manage.xml")
            addFile(tf, "*.LIS")
        finally:
            tf.close()
