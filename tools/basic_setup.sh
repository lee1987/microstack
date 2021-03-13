#!/bin/bash

set -ex

sudo apt update
# install Firefox which will be used for Web UI testing in a headless mode.
sudo apt install -y firefox-geckodriver python3-petname python3-selenium
