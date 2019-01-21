#!/usr/bin/python
import os
import re
import sys

script_path = sys.argv[1]
listener_path = sys.argv[2]

splitted_args = script_path.split("-t%")

script_path = splitted_args[1].split(".jmx")[0] + ".jmx"

with open(script_path, "r") as input_script, open(listener_path, "r") as listener_script:
    try:
        test = input_script.read()
        listener = listener_script.read()


        splitted = re.split("</TestPlan>\W+<hashTree>", test)

        modified_body = splitted[0] + "    </TestPlan>\n    <hashTree>\n" + listener + splitted[1]
        tests_path = os.path.dirname(script_path)
        test_name = os.path.basename(script_path)
        
        new_test = open("%s/%s_original.jmx" % (tests_path, test_name.split(".jmx")[0]), "w+")
        new_test.write(test)
        new_test.close()
        test_to_run = open("%s/%s" % (tests_path, test_name), "w+")
        test_to_run.write(modified_body)
        test_to_run.close()
    except Exception:
        print "There was errors"
    
