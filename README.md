# USB/UART Communication with a RAIN RFID UHF Reader Module
This repository holds a Pyhton library that can be used as an example to communicate with a specific RAIN RFID UHF reader module. The code is written based on PyQt and can be run as a QThread in another application. It takes advantage of pyqtSignal and QMutex, which are useful in applications needing multi-threading. 

Below, you can find information on system requirements and instructions to install dependencies. 


## System requirements
This script has only been tested on Ubuntu 22.04.2 LTS operating system. A fully functional application on any other OS or OS version is not guaranteed. To find the OS name and version in Linux, run any of the following commands:
```
cat /etc/os-release
lsb_release -a
hostnamectl
```


## Install the following packages
1) Install pyserial
```
pip3 install pyserial
```

2) Install pyqt5
```
pip3 install pyqt5
```
If there was any problem with installing using pip, try the following command
```
sudo apt-get install python3-pyqt5
```

