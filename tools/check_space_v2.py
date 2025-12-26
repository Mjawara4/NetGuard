import shutil
import os

try:
    total, used, free = shutil.disk_usage("/")
    with open("space_report_v2.txt", "w") as f:
        f.write(f"Total: {total // (2**30)} GB\n")
        f.write(f"Used: {used // (2**30)} GB\n")
        f.write(f"Free: {free // (2**30)} GB\n")
        f.write("Write test successful.")
except Exception as e:
    # try to print at least
    print(f"Error: {e}")
