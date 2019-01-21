#!/usr/bin/python
import os
import re
import sys

script_path = sys.argv[1]

splitted_args = script_path.split("-t%")

script_path = splitted_args[1].split(".jmx")[0] + ".jmx"
    
print "----------------------------------"
with open(script_path.split(".")[0]+"_original.jmx", "r") as input_script:
        original_test = input_script.read()
        
        original_path = open(script_path, "w+")
        original_path.write(original_test)
        original_path.close()

os.remove(script_path.split(".")[0]+"_original.jmx")
    
