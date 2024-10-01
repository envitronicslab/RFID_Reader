import serial
import serial.tools.list_ports
from time                       import time
import math
import sys
import traceback
import inspect
from PyQt5.QtCore           import *
from PyQt5                  import QtTest

__author__ = "Y. Osroosh, Ph.D. <yosroosh@gmail.com>"

def get_fname():
    """
        Provides stack traceback information
    Returns:
        str: Name of method/function, where the exception occurred
    """
    tb = sys.exc_info()[-1]
    stk = traceback.extract_tb(tb, 1) 
    
    return stk[0][2]


def get_fun_name():
    """
        Returns name of method/function, where the function was called
    """
    fname = inspect.stack()[1][3]
    
    return fname


def wait_s(seconds: int):
    """
        Waits for the specified number of seconds as a safe alternative to using sleep()
    """
    i = 0
    while i < seconds:
        i += 1
        dieTime = QTime.currentTime().addSecs(1)
        while QTime.currentTime() < dieTime:
            QCoreApplication.processEvents(QEventLoop.AllEvents, 100)


def wait_ms(milli_seconds: int):
    """
        Waits for the specified number of milli seconds as a safe alternative to using sleep()
    """
    QtTest.QTest.qWait(milli_seconds)



class SerialPort():  
    """
        Port settings group for Serial Port communication
    """   
    def __init__(self, SerialSettings: dict):      
        self.serial_port = SerialSettings['serial_port']
        self.baud_rate = SerialSettings['baud_rate']
        self.parity = SerialSettings['parity']
        self.stopbits = SerialSettings['stopbits']
        self.bytesize = SerialSettings['bytesize']
        self.time_out = SerialSettings['time_out']
        self.com = serial.Serial()
        

    def serial_open(self):
        """
            Opens serial port
        """      
        # print("Opening serial port ({port})".format(port = self.serial_port), flush=True)
        
        error = None
        try:
            # Configure the serial connections 
            self.com = serial.Serial(	
                port = self.serial_port,    # Find DUT serial port using: "dmesg | grep tty", OR using the list_serial_ports method 
                baudrate = self.baud_rate,
                parity = self.parity,
                stopbits = self.stopbits,
                bytesize = self.bytesize,
                timeout = self.time_out
            ) 
            wait_ms(2000) # give the connection a second or two to settle
            self.flush_buffers()
    
            if self.com.is_open:
                print("Successfully opened serial port {}".format(self.serial_port), flush=True)                          
        
        except Exception as e1:
            error = "[{}] {}".format(get_fname(), str(e1))
            print("Error: {}".format(error), flush=True)
        
        return error
    
    
    def serial_close(self):
        """
            Closes serial port
        """      
        # print("Closing serial port ({port})".format(port = self.serial_port), flush=True)
        
        error = None
        try:
            if self.com.is_open:
                # close the serial port
                self.com.close()
                # print("Successfully closed the port...", flush=True)                          
        
        except Exception as e1:
            error = "[{}] {}".format(get_fname(), str(e1))
            print("Error: {}".format(error), flush=True)
        
        return error
    
    
    def flush_buffers(self):
        self.com.reset_input_buffer()  # flush input buffer, discarding all its contents
        self.com.reset_output_buffer() # flush output buffer, aborting current output and discard all that is in buffer
            

    def serial_send(self, cmd: bytes):
        """
            Writes data to a serial port
        """      
        # print("Writing data to serial port ({port}):".format(port = self.serial_port), flush=True)
        
        error = None
        try:
            if self.com.is_open:      
                self.flush_buffers() 
                      
                # Write to the serial port 
                # print("{}".format(cmd), flush=True)                             
                self.com.write(cmd)   

        except Exception as e1:
            error = "[{}] {}".format(get_fname(), str(e1))
            print("Error: {}".format(error), flush=True)

        return error  
        
        
    def serial_receive(self, rec_timeout: float = 5.000):
        """
            Reads data from serial port
        Args:
            timeout (float, optional): This is the time the method will wait for serial data before timing out. Defaults to ~5 second.
        Returns:
            tuple: error (if any) and data in (if any) are returned
        """
        # print("Receiving data from serial port ({port}):".format(port = self.serial_port), flush=True)        
        error = None
        data_in = None
        try:
            if self.com.is_open:         
                # Read from the serial port	
                data_in = b""                
                count = 0
                while count < (rec_timeout * 1000):
                    count += 1
                    ## bytesWaiting = self.com.inWaiting()
                    bytesWaiting = self.com.in_waiting
                    if(bytesWaiting != 0):
                        byte_in = self.com.read(bytesWaiting)
                        if byte_in:
                            data_in += byte_in   
                            break
                    wait_ms(1) 
                
                if data_in:
                    # print("{}".format(data_in), flush=True)
                    pass
                else:
                    error = "Err1: No bytes from the device"
                    # print(error, flush=True)  
                    pass                      
            else:
                error = "Err2: Cannot open serial port." 
                print(error, flush=True)                                 
        
        except Exception as e1:
            error = "[{}] {}".format(get_fname(), str(e1))
            print("Error: {}".format(error), flush=True)
        
        return error, data_in
        
    

# UHF RFID Reader UART settings
UHFReaderSerialSettings15 = {
    'serial_port': '/dev/ttymxc2',
    "baud_rate": 115200, 
    "parity": 'N',
    "stopbits": 1,
    "bytesize": 8,
    "time_out": 0.1
}
# Instantiate some object
uhf_ser = SerialPort(UHFReaderSerialSettings15)
