#!/bin/bash

#IFS= read var << EOF
#$(foo)
#EOF

read -t 1 foo
echo "You entered '$foo'"
