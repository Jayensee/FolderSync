# FolderSync

```
Creates a replica of a given source folder and periodically updates it to keep the replica
synchronized. Uses SHA256 to check if files need to be replaced.

usage: python foldersync.py [-h] [-s] [--follow_symlinks] source [replica] [period] [log_path]
positional arguments:
  source             path to the source folder
  replica            path to the replica folder, if it doesn't exist then it will be     
                     created (default: ./replica)
  period             time interval between synchronizations in seconds (default: 3600)   
  log_path           path to the log file, if log splitting is enabled then it's the     
                     path to the logs folder (default: ./sync_log.txt)

options:
  -h, --help         show this help message and exit
  -s, --split_logs   split the logs into multiple files
  --follow_symlinks  follow symbolic links 
  ```
