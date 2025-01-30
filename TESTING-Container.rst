-----------------
Setup environment
-----------------
Navigate to the project's root directory and execute the following command to build the testing container locally::
  docker build . -f tools/Dockerfile_Testing -t testing-container
To run the Nodepool tests, a running Zookeeper is required. Zookeeper also needs to be configured for TLS and a certificate authority set up to handle socket authentication. Because of these complexities, it's recommended to use the helper script to set up these dependencies and to configure and run the Noodepool environment::
  ROOTCMD=sudo tools/test-setup-docker.sh
Now access the bash in `nodepool-testing-container` by executing::
  docker-compose -f tools/docker-compose.yaml exec zuul-testing-container bash

To run individual tests with nox::
  nox -s tests -- path.to.module.Class.Test


dump threads:
/zuul/.nox/tests/bin/python -m pip install pystack

ps aux

pystack remote PID