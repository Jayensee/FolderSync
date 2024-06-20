from time import time, sleep
from sys import exit as sys_exit
from hashlib import sha256
from pathlib import Path
from shutil import copy2
import argparse


#  Prints a log line to the console and adds it to the logs
def add_log_line(line):
    # Use global variables to avoid passing around variables that are only used here
    print(f"Sync {sync_count}: {line}")
    if split_logs:
        # Check if the logs folder exists, create it if it doesn't
        log_folder_path = Path(str(log_path).split(".", 1)[0])
        if not log_folder_path.is_dir():
            log_folder_path.mkdir()
        log_file_path = log_folder_path / f"log{sync_count:04}.txt"
    else:
        log_file_path = log_path

    # Check if the log file exists, create it if it doesn't
    if not log_file_path.is_file():
        with open(log_file_path, "w") as f:
            f.write("")    
    
    # Append the new line to the log file (prefixed by the sync number if not splitting)
    with open(log_file_path, "a") as f:
        f.write((f"Sync {sync_count}: " if not split_logs else "")  + f"{line}\n")   


def mkdir_log(path):
    add_log_line(f"CREATED FOLDER: {path}")
    path.mkdir()

def rmdir_log(path):
    add_log_line(f"DELETED FOLDER: {path}")
    path.rmdir()

def unlink_log(path):
    add_log_line(f"DELETED FILE: {path}")
    path.unlink()

def copy_log(src_path, dst_path, is_new):
    if is_new:
        add_log_line(f"CREATED FILE: {dst_path}")
    else:
        add_log_line(f"UPDATED FILE: {dst_path}")
    copy2(src_path, dst_path)


class Folder:
    def __init__(self, path, follow_symlinks):
        self.path = path
        self.recursive_map(follow_symlinks = follow_symlinks)
    
    # Returns a human-readable string with the paths to the sub-folders and files
    # Includes the number of items in each subfolder after their paths
    def __str__(self):
        string = f"Path: {self.path}\n"
        string += f"Sub-Folders: {len(self.subfolders)}\n"
        for subfolder in self.subfolders:
            string += f"\t{subfolder.path}"
            string += f"\t{len(subfolder.subfolders)+len(subfolder.files)}\n"
        string += f"Files: {len(self.files)}\n"
        for file in self.files:
            string += f"\t{file}\n"
        return string
    
    # Calls recursive_str with the default parameters
    def __repr__(self):
        return self.recursive_str()

    # Same as __str__ but applied recursively to subfolders
    def recursive_str(self, incr_str="| ", max_depth=2, depth=0, suppress_files=True):
        string = ""
        if depth == 0:
            string += f"Path: {self.path}\n"
            string += f"Sub-Folders: {len(self.subfolders)}\n"
        else:
            string += f"{incr_str*(depth-1)}{self.path}"
            if suppress_files:
                string += f" {len(self.files)+len(self.subfolders)}"
            string += "\n"

        for subfolder in self.subfolders:
            if depth == max_depth:
                string += f"{incr_str*depth}{subfolder.path}"
                string += f" ...{len(subfolder.subfolders)+len(subfolder.files)}\n"
            else:
                string += subfolder.recursive_str(incr_str, max_depth, depth+1,suppress_files)
        
        if depth == 0:
            string += f"Files: {len(self.files)}\n"
            if suppress_files:
                return string
        if not suppress_files:
            for file in self.files:
                if depth == 0:
                    string += " "
                string += f"{incr_str*depth}{file}\n"
        return string

    # Recursively maps the structure of the folder
    def recursive_map(self, follow_symlinks):
        self.subfolders = []
        self.files = []
        for path in self.path.iterdir():
            if path.is_dir():
                if (not follow_symlinks) and path.is_symlink():
                    continue
                subfolder = Folder(path, follow_symlinks)
                self.subfolders.append(subfolder)
            else:
                if (not follow_symlinks) and path.is_symlink():
                    continue
                self.files.append(File(path))
    
    # Deletes the folder and its contents
    def recursive_delete(self):
        for file in self.files:
            unlink_log(file.path)
        for subfolder in self.subfolders:
            subfolder.recursive_delete()
        rmdir_log(self.path)

    # Synchronizes the folder to the relpica folder
    def recursive_sync_to(self, replica_folder, follow_symlinks):
        # Delete all folders in the replica that aren't in the source
        indices_removed = []
        for index, subfolder in enumerate(replica_folder.subfolders):
            source_sub_path = self.path / subfolder.path.name
            if not source_sub_path.is_dir():
                indices_removed.append(index)
                subfolder.recursive_delete()
        for index in indices_removed[::-1]:
            replica_folder.subfolders.pop(index)

        # Create any missing folders in the replica
        folders_created = []
        for subfolder in self.subfolders:
            replica_sub_path = replica_folder.path / subfolder.path.name
            if not replica_sub_path.is_dir():
                mkdir_log(replica_sub_path)
                next_folder = Folder(replica_sub_path, follow_symlinks)
                folders_created.append(next_folder)
            else:
                for repl_subfolder in replica_folder.subfolders:
                    if repl_subfolder.path == replica_sub_path:
                        next_folder = repl_subfolder
                        break
            subfolder.recursive_sync_to(next_folder, follow_symlinks)
        replica_folder.subfolders += folders_created

        # Delete all files in the replica that aren't in the source
        indices_removed = []
        for index, file in enumerate(replica_folder.files):
            source_file_path = self.path / file.path.name
            if not source_file_path.is_file():
                indices_removed.append(index)
                unlink_log(file.path)
        for index in indices_removed[::-1]:
            replica_folder.files.pop(index)

        # Create any missing files and update files with a different checksum
        files_created = []
        for file in self.files:
            replica_file_path = replica_folder.path / file.path.name
            # Create missing files
            if not replica_file_path.is_file():
                copy_log(file.path, replica_file_path, True)
                files_created.append(File(replica_file_path))
            # Update changed files
            else:
                for repl_file in replica_folder.files:
                    if repl_file.path == replica_file_path:
                        file_on_replica = repl_file
                        break
                if file_on_replica.sha256 != file.sha256:
                    copy_log(file.path, replica_file_path, False)
                    file_on_replica.sha256 = file.sha256
        replica_folder.subfolders += files_created


class File:
    def __init__(self, path):
        self.path = path
        self.sha256 = self.calculate_sha256()
    
    def __str__(self):
        return str(self.path)

    def calculate_sha256(self, chunk_size=8192):
        hash_function = sha256()
        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                hash_function.update(chunk)
        return hash_function.hexdigest()


if __name__=="__main__":
    parser = argparse.ArgumentParser(
        prog = "Folder Sync",
        description = "Creates a replica of a given source folder and "
                      "periodically updates it to keep the replica synchronized.")
    # Positional args
    parser.add_argument(
        "source", 
        type = str,
        help = "path to the source folder")
    parser.add_argument(
        "replica",
        type = str,
        nargs = "?",
        help = "path to the replica folder, if it doesn't exist then it "
               "will be created (default: ./replica)", 
        default = "./replica")
    parser.add_argument(
        "period", 
        type = int,
        nargs = "?",
        help = "time interval between synchronizations in seconds "
               "(default: 3600)", 
        default = 3600)
    parser.add_argument(
        "log_path",
        type = str,
        nargs = "?",
        help = "path to the log file, if log splitting is enabled then it's the path "
               "to the logs folder "
               "(default: ./sync_log.txt)", 
        default = "./sync_log.txt")
    # Optional Args
    parser.add_argument(
        "-s","--split_logs", 
        action = "store_true",
        help = "split the logs into multiple files")
    parser.add_argument(
        "--follow_symlinks", 
        action = "store_true",
        help = "follow symbolic links")
    args = parser.parse_args()

    # global log_path, split_logs, sync_count
    log_path = Path(args.log_path) 
    if "." not in log_path.name:
        log_path = Path(args.log_path+".txt") 

    split_logs = args.split_logs
    sync_count = 1

    replica_path = Path(args.replica)
    source_path = Path(args.source)

    period = args.period
    follow_symlinks = args.follow_symlinks

    # Synchronization loop
    while True:
        iter_start = time()
        try:
            # Check if the replica folder exists, create it if it doesn't
            if not replica_path.is_dir():
                mkdir_log(replica_path)

            # Create the source and replica Folder objects (recursively mapped out)
            source_folder = Folder(source_path, follow_symlinks)
            replica_folder = Folder(replica_path, follow_symlinks)

            source_folder.recursive_sync_to(replica_folder, follow_symlinks)

            sync_count += 1
            # Adjust sleeping time to account for execution time
            if time()-iter_start <= period:
                sleep(period + iter_start - time())
            else:
                sleep(args.period)
        except OSError:
            # Check if the source folder exists
            if not source_path.is_dir():
                try:
                    raise FileNotFoundError
                except FileNotFoundError:
                    print("ERROR: The source folder doesn't seem to exist, make "
                          "sure the path is correct")
                    sys_exit()
            if time()-iter_start <= period:
                sleep(period + iter_start - time())
            else:
                sleep(args.period)

 