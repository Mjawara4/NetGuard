import shutil
import os

try:
    total, used, free = shutil.disk_usage("/")
    with open("space_report.txt", "w") as f:
        f.write(f"Total: {total // (2**30)} GB\n")
        f.write(f"Used: {used // (2**30)} GB\n")
        f.write(f"Free: {free // (2**30)} GB\n")
except Exception as e:
    with open("space_report.txt", "w") as f:
        f.write(f"Error: {e}")
