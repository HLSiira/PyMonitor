#! /bin/bash
URL=https://camo.githubusercontent.com/4f68398833c00e26a8a85e5bd72afadee1d6a3caf24d59e05c77f204c469645c/68747470733a2f2f70726f66696c652d636f756e7465722e676c697463682e6d652f64756e6e6a6d3831342f636f756e742e737667
END=10

echo -n "Starting"
for i in {1..100}; do
    echo -n "-$i"
    curl -s $URL -o /dev/null
    sleep 4s
done
echo "-fin"
