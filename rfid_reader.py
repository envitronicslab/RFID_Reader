"""
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
// 
// Python class for USB/UART communication with a RAIN RFID UHF reader module
// Written by Yasin Osroosh, Ph.D.
// Email: yosroosh@gmail.com
// 
//@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
//@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

"""
import struct
import re
from PyQt5.QtCore           import QThread, pyqtSignal, QMutex
from serial_io              import *





class UHFReaderThread(QThread):
    """
        This class contains required methods to communicate with the UHF reader
    """
    # Define pyQt signals
    signal_give_uhf_meta_data = pyqtSignal(bool, dict)
    signal_tag_detected_audio = pyqtSignal()

    # Class constants
    REC_TIMEOUT = 1   # Receive timeout in seconds
    
    
    def __init__(self, serial_port: SerialPort):
        QThread.__init__(self)
 
        # Create a serial object for communication w/ the UHF reader
        self.ser = serial_port
        
        # Mutex to handle uhf_params safely
        self.mutex_uhf_params = QMutex()
        self.set_uhf_params(False, {})
        
    
    def run(self):   
        print("UHF Reader started (QThread)...", flush=True)
        self.start_reading()
        
    
    class UHFOperatingState():
        IDLE = '0000'
        TAG_READ = '0004'
    
    
    class Events():
        """
            Struct to hold event masks
        """
        TAG_SEEN = 0
        TAG_REMOVED = 1
        TAG_POWER_CHANGE = 2
        TAG_REPORT_TIMEOUT = 3
        GEN2_OP_COMPLETED = 4
        GEN2_OP_TIMEOUT = 5
    
    
    class OPParams():
        """
            Struct to hold operational parameters
        """
        TAG_TIMEOUT = 'Tag Time Out'
        TAG_TIMEOUT_CODE = '0001'
        TAG_POWER_CHANGE_THRESHOLD = 'Tag_Power_Change_Threshold'
        TAG_POWER_CHANGE_THRESHOLD_CODE = '0002'
        TAG_REPORT_TIMEOUT = 'Tag_Report_Timeout'
        TAG_REPORT_TIMEOUT_CODE = '0003'
        TRANSIENT_DETECT_TIME = 'Transient_Detect_Time'
        TRANSIENT_DETECT_TIME_CODE = '0004'
        TRANSIENT_COUNT = 'Transient_Count'
        TRANSIENT_COUNT_CODE = '0005'
        TRANSIENT_INTERVAL = 'Transient_Interval'
        TRANSIENT_INTERVAL_CODE = '0006'
        GEN2_OP_TIMEOUT = 'Gen2_Op_Timeout'  
        GEN2_OP_TIMEOUT_CODE = '0007' 
        RESPONSE_NOT_DEFINED = 'Response_Not_Defined'                  
        
    class UHFBytes():
        """
            Struct to hold KNOWN bytes from the UHF reader
        """
        # C/R & Opcode in the response message
        GET_VERSION = b'\x80\x04'
        GET_TEMP = b'\x80\x13'
        GET_OP_REGION = b'\x80\x03'
        SET_OP_REGION = b'\x80\x02'  
        GET_OP_PARAMS = b'\x80\x0B'
        SET_OP_PARAMS = b'\x80\x0A'
        GET_EVENT_MASK = b'\x80\x15'
        SET_EVENT_MASK = b'\x80\x14'   
        SET_TX_POWER = b'\x80\x05'
        GET_TX_POWER = b'\x80\x06'
        SET_ANT_ENABLES = b'\x80\x0E'
        GET_ANT_ENABLES = b'\x80\x0F'
        SET_OP_STATE = b'\x80\x0C'
        GET_OP_STATE = b'\x80\x0D'
        GET_TAG_REPORT = b'\x80\x09'
        KEEP_ALIVE = b'\x80\x01'
        # Status bytes
        STATUS_SUCCESS = b'\x00\x00'   
        STATUS_OP_REGION_INVALID = b'\x00\x05' 
        STATUS_INVALID_POWER_LEVEL = b'\x00\x06'  
        STATUS_INTERNAL_ERROR = b'\x00\x07'      
        # Framing bytes
        FRAMING_BYTES = b'\xf6('
        FRAMING_BYTES_LEN = 2
        
    
    def create_event_mask(self, tag_seen, tag_removed, tag_power_change, tag_report_timeout, gen2_op_completed, gen2_op_timeout):
        """
            Creates an event mask
        """
        event_mask = int('00{}{}{}{}{}{}'.format(gen2_op_timeout, gen2_op_completed, tag_report_timeout, tag_power_change, tag_removed, tag_seen), 2)
        # event_mask = '{:032b}'.format(event_mask)
                
        return event_mask
    
    
    def set_uhf_params(self, status, params):
        """
            Sets UHF parameters safely using mutex lock
        """
        if self.mutex_uhf_params.tryLock(-1):  
            # print("UHF params: {}".format(params), flush=True)             
            self.startReading = status        
            self.uhf_params = params  
            self.mutex_uhf_params.unlock()
            
            
    def get_uhf_params(self):
        """
            Gets UHF parameters safely using mutex lock
        """
        if self.mutex_uhf_params.tryLock(-1):  
            # print("UHF params: {}".format(params), flush=True)            
            status = self.startReading
            params = self.uhf_params
            self.mutex_uhf_params.unlock()
        return params, status
    
    
    def bit_status(self, x, n):
        """
            Checks whether n^th bit is set or not
        Args:
            x (int): 16-bit integer
            n (int): nth bit to check
        Returns:
            bool: True if the bit is set, False otherwise
        """
        return x & 1 << n != 0
    
    
    def int_to_hex_string(self, value: int, str_len: int = 4):
        """
            Converts integer value to hex string
        Args:
            value (int): integer value
            str_len (int, optional): hex string. Defaults to 4
        Returns:
            hex string
        """
        value_hex = format(value, 'x')
        hex_str = value_hex.rjust(str_len, '0')
        
        return hex_str
    

    def convert_binary_to_16bits(self, data_bin):
        """
            Converts binary to 16 bit integer
            
            'h' stands for signed 2-byte 16bit number
            'H' stands for unsigned 2-byte 16bit number
            Further reference available in python.struct docs
        Args:
            data_bin (binary)
        Returns:
            (bytes): 16-bit int
        """
        m8 = int(data_bin, 2)
        m16 = struct.pack('h', m8)
        
        return m16

    
    def code_to_param(self, code):
        """
            Converts code (hex or hex string) to operational parameter (string)
        """
        if type(code) is int:
            code_hex_string = '{:04x}'.format(code)
        else:
            code_hex_string = code
        
        match code_hex_string:
            case '0001':
                param = self.OPParams.TAG_TIMEOUT
            case '0002':
                param = self.OPParams.TAG_POWER_CHANGE_THRESHOLD
            case '0003':
                param = self.OPParams.TAG_REPORT_TIMEOUT
            case '0004':
                param = self.OPParams.TRANSIENT_DETECT_TIME
            case '0005':
                param = self.OPParams.TRANSIENT_COUNT
            case '0006':
                param = self.OPParams.TRANSIENT_INTERVAL
            case '0007':
                param = self.OPParams.GEN2_OP_TIMEOUT  
            case _:
                # Should never hit this line
                param = self.OPParams.RESPONSE_NOT_DEFINED
                
        return param
        

    def close_serial_port(self):
        # Close the serial port
        error = self.ser.serial_close() 
        
        return error        
        
        
    def wait_for_response_short(self, set_response, rec_timeout = REC_TIMEOUT):
        """
            Waits for a response from the UHF reader 
        Args:
            rec_timeout (float): time to wait for a response from the UHF reader in seconds. Defaults to REC_TIMEOUT
        Returns:
            tuple: 
                error (str): any error occurred during the process
                res (bytes): response from the UHF reader
        """
        # Get the response
        # print("Awaiting a response...", flush=True)
        
        res = None
        error = None
        error, res = self.ser.serial_receive(rec_timeout)         
        # Trim (synchronize?) the frame by getting rid of any bytes related to the 'keep alive' or additional framing bytes
        res_trimmed = res.split(self.UHFBytes.FRAMING_BYTES) 
        if len(res_trimmed) > 2:
            res = self.UHFBytes.FRAMING_BYTES + res_trimmed[2]
            if res[4:6] == set_response:
                pass
            else:
                res = self.UHFBytes.FRAMING_BYTES + res_trimmed[1]
        
        # Cut the response to its expected length
        length = int.from_bytes(res[2:4], 'big') + self.UHFBytes.FRAMING_BYTES_LEN
        # print("[wait_for_response_short] length: {}".format(length), flush=True)
        res = res[:length]
        
        # if error is None:
        #     print("response: {}".format(res), flush=True)  
 
        return error, res
    
    
    def wait_for_response_long(self, set_response): 
        """
            Waits for the UHF reader to complete param set (by sending keep alive) and returning a response
        Args:
            set_response (bytes): response to expect from the UHF reader
        Returns:
            status (bool): True if the response was received. False otherwise
        """
        # Build a 'keep alive' message/command
        length = '0004'
        cr_opcode = '0001' 
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)

        # Loop until the UHF reader tells the param is set!
        count = 0
        res = None
        error = None     
        while count < 5:
            count += 1
            error = self.send_cmd(msg)
            if error is None:
                error, res = self.wait_for_response_short(set_response)
                if res[4:6] == set_response:
                    break
            wait_ms(1000)
      
        return error, res
    
    
    def send_cmd(self, cmd: bytes):
        """
            Sends a command to the UHF reader and returns the response
        Args:
            cmd (bytes): command to send
        Returns:
            error (str): any error occurred during the process
        """
        error = None
        error = self.ser.serial_send(cmd)   

        return error

        
    def build_cmd(self, length, cr_opcode, word1 = None, word2 = None, word3 = None, word4 = None, word_type = 'str'):
        """
            Builds a UHF command
            
            "The overall format of a message starts with the following 6 byte header. The first two bytes contain a
            fixed framing pattern of 0xF628. The next two bytes contain the length of the message, including the 2
            length bytes but excluding the two framing bytes. The next two bytes contain a 15 bit opcode and a 1
            bit Command/Response indication."
        Args:
            length (_type_): length of the message
            cr_opcode (_type_): C/R + Opcode (15 bit opcode and a 1 bit Command/Response indication)
        Returns:
            bytes: built message in bytes
        """
        _FRAMING_BYTES = "F6 28" 
        msg_str = "{} {} {}".format(_FRAMING_BYTES, length, cr_opcode) 
        if word1 is not None: 
            if word_type == 'str':
                msg_bytes = bytes.fromhex(msg_str) + bytes(word1, "utf-8") + b'\x00'             
            elif word_type == 'int':
                if (word2 is None) and (word3 is None) and (word4 is None):
                    msg_bytes = bytes.fromhex(msg_str) + word1.to_bytes(2, 'big')
                else:
                    msg_bytes = bytes.fromhex(msg_str) + word1.to_bytes(2, 'big') + word2.to_bytes(2, 'big') + word3.to_bytes(2, 'big') + word4.to_bytes(2, 'big')            
            elif word_type == 'int32':
                msg_bytes = bytes.fromhex(msg_str) + word1.to_bytes(4, 'big')
            elif word_type == 'uint32_t':
                msg_bytes = bytes.fromhex(msg_str) + bytes.fromhex(word1) + word2.to_bytes(4, 'big')            
            elif word_type == 'byt':
                msg_bytes = bytes.fromhex(msg_str) + bytes.fromhex(word1)
                
            # Add zeros for the remaining bytes up to the length of the command
            for i in range(int(length, 16) - len(msg_bytes)):
                msg_bytes += b'\x00'
                
        else:
            msg_bytes = bytes.fromhex(msg_str)
            
        # print("Command bytes: {}".format(msg_bytes), flush=True)
        
        return msg_bytes


    def get_version(self):
        """
            Gets UHF reader version information
        """
        print("Getting UHF reader version information...", flush=True) 
        length = '0004'
        cr_opcode = '0004' 
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_VERSION)
        
        version = None  
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_VERSION:
                # parse response and get version info
                # example res = b'\xf6(\x00\x1c\x80\x04\x00\x001.2.0\x001.2.0\x002.0.0\x001.0\x00'
                Firmware_rev = res[8:13].decode('utf-8')
                SDK_rev = res[14:19].decode('utf-8')
                Software_rev = res[20:25].decode('utf-8')
                Hardware_rev = res[26:29].decode('utf-8')
                version = {
                    "FirmwareRev": Firmware_rev,
                    "SDKRev": SDK_rev,
                    "SoftwareRev": Software_rev,
                    "HardwareRev": Hardware_rev
                }
            else:
                error = "Unable to get device version information"
                print(error, flush=True)
                            
        return error, version
    
    
    def get_temp(self):
        """
            Gets UHF reader temperature
        """
        print("Getting UHF reader temperature...", flush=True) 
        length = '0004'
        cr_opcode = '0013' 
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_TEMP)
        
        temperature = None
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_TEMP:
                # parse response and get temp from res
                # example res = b'\xf6(\x00\x08\x80\x13\x00\x00\x10d'
                temperature = int.from_bytes(res[8:len(res)], 'big')/100
            else:
                error = "Unable to get temperature"
                print(error, flush=True)
                            
        return error, temperature


    def get_operational_params(self, code):
        """
            Gets the operational parameters
        """
        param = self.code_to_param(code)                
        print("Getting value for operational param '{}'...".format(param), flush=True)
        length = '0006'
        cr_opcode = '000B'  
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode, word1=code, word_type='byt')
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_OP_PARAMS)
        
        op_param = None    
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_OP_PARAMS:
                # parse response (res)
                # example res: b'\xf6(\x00\x0c\x80\x0b\x00\x00\x00\x01\x00\x00\xea`'
                rep = int.from_bytes(res[8:10], 'big') 
                param = self.code_to_param(rep)                                         
                value = int.from_bytes(res[10:], 'big')
                
                op_param = {
                    "param": param,
                    "value": value
                }              
            else:
                error = "Unable to get operational parameters"
                print(error, flush=True)
                
        return error, op_param    
    
    
    def set_operational_param(self, code, value):
        """
            Sets the operational parameters
        """
        param = self.code_to_param(code)  
        print("Setting operational param '{}' to '{}'...".format(param, value), flush=True)
        length = '000A'
        cr_opcode = '000A'   
        msg = self.build_cmd(length, cr_opcode, word1=code, word2=value, word_type='uint32_t')
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(1000)
            error, res = self.wait_for_response_short(self.UHFBytes.SET_OP_PARAMS)
            if res == b'':
                error, res = self.wait_for_response_long(self.UHFBytes.SET_OP_PARAMS)
               
        if error is None:
            # parse response (res)           
            if not res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.SET_OP_PARAMS:
                error = "Unable to set '{}' to '{}'".format(param, value)
                print(error, flush=True)
                
        return error
       
    
    def get_event_mask(self):
        """
            Gets event mask
            TODO: Needs more work. Because of errors in the module Binary-Interface (datasheet), I wasn't able to finalize this method and verify it works.
        """                        
        print("Getting 32-bit event mask...", flush=True)
        length = '0004'
        cr_opcode = '0015'  
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)
        print(msg, flush=True)
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_EVENT_MASK)
            
        print(res, flush=True)
        
        event_mask = None    
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_EVENT_MASK:
                # parse response (res)
                # example res: 
                mask_32bits = int.from_bytes(res[8:len(res)], 'big')                
                tag_seen = self.bit_status(mask_32bits,0)
                tag_removed = self.bit_status(mask_32bits,1)
                tag_power_change = self.bit_status(mask_32bits,2)
                tag_report_timeout = self.bit_status(mask_32bits,3)
                gen2_op_completed = self.bit_status(mask_32bits,4)
                gen2_op_timeout = self.bit_status(mask_32bits,5)
                
                event_mask = {
                    "tag_seen": tag_seen,
                    "tag_removed": tag_removed,
                    "tag_power_change": tag_power_change,
                    "tag_report_timeout": tag_report_timeout,
                    "gen2_op_completed": gen2_op_completed,
                    "gen2_op_timeout": gen2_op_timeout
                }           
            else:
                error = "Unable to get event mask"
                print(error, flush=True)
                
        return error, event_mask 
        
    
    def set_event_mask(self, tag_seen, tag_removed, tag_power_change, tag_report_timeout, gen2_op_completed, gen2_op_timeout):
        """
            Sets 32-bit event mask
            TODO: Needs more work. Because of errors in the module Binary-Interface (datasheet), I wasn't able to finalize this method and verify it works.
        """
        print("Setting 32-bit event mask...", flush=True)
        length = '0008'
        cr_opcode = '0014'         
        event_mask = int('00{}{}{}{}{}{}'.format(gen2_op_timeout, gen2_op_completed, tag_report_timeout, tag_power_change, tag_removed, tag_seen), 2)
        msg = self.build_cmd(length, cr_opcode, word1=event_mask, word_type='int32')
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(1000)
            error, res = self.wait_for_response_short(self.UHFBytes.SET_EVENT_MASK)
            if res == b'':
                error, res = self.wait_for_response_long(self.UHFBytes.SET_EVENT_MASK)
        
        print(res, flush=True)
              
        if error is None:
            # parse response (res)
            if not res[6:10] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.SET_EVENT_MASK:
                error = "Unable to set event mask!"
                print(error, flush=True)
                
        return error
    
    
    def get_op_region(self):
        """
            Gets current operating region
        """
        print("Getting current operating region...", flush=True)
        length = '0004'
        cr_opcode = '0003'         
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_OP_REGION)
        
        op_region = None    
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_OP_REGION:
                # parse response (res)
                # example res: b'\xf6(\x00\n\x80\x03\x00\x00FCC\x00'
                op_region = res[8:11].decode('utf-8')
            else:
                error = "Unable to get operating region"
                print(error, flush=True)
                
        return error, op_region

    
    def set_op_region(self, opRegion = 'FCC'):
        """
            Sets current operating region
        """
        print("Setting operating region...", flush=True)        
        length = self.int_to_hex_string(4 + len(opRegion) + 1)                
        cr_opcode = '0002'         
        op_reg = opRegion
        msg = self.build_cmd(length, cr_opcode, word1=op_reg)
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            error, res = self.wait_for_response_short(self.UHFBytes.SET_OP_REGION)
             
        if error is None:
            # parse response (res)
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.SET_OP_REGION:
                pass
            elif not res[6:8] == self.UHFBytes.STATUS_SUCCESS:
                error = "Invalid operating region: {}".format(opRegion)
                print(error, flush=True)
            else:
                error = "Unable to set operating region"
                print(error, flush=True)
                
        return error
    
    
    def get_tx_power(self):
        """
            Gets TX power for all four antennas
        """
        print("Getting TX power...", flush=True)
        length = '0004'
        cr_opcode = '0006'         
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_TX_POWER)
        
        tx_power = None         
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_TX_POWER:
                # parse response (res)
                # example res: b'\xf6(\x00\x0e\x80\x06\x00\x00\x0b\xb8\x0b\xb8\x0b\xb8\x0b\xb8'
                ant_1_power = int.from_bytes(res[8:10], 'big')/100
                ant_2_power = int.from_bytes(res[10:12], 'big')/100
                ant_3_power = int.from_bytes(res[12:14], 'big')/100
                ant_4_power = int.from_bytes(res[14:16], 'big')/100
                tx_power = {
                    "ant1power": ant_1_power,
                    "ant2power": ant_2_power,
                    "ant3power": ant_3_power,
                    "ant4power": ant_4_power
                }
            else:
                error = "Unable to get TX power"
                print(error, flush=True)
                
        return error, tx_power
        
    
    def set_tx_power(self, ant1TxPower, ant2TxPower, ant3TxPower, ant4TxPower):
        """
            Sets TX power for all four antennas
        """
        print("Setting TX power for antennas 1-4...", flush=True)
        length = '000C'
        cr_opcode = '0005'         
        ant_power1 = int(ant1TxPower * 100)
        ant_power2 = int(ant2TxPower * 100)
        ant_power3 = int(ant3TxPower * 100)
        ant_power4 = int(ant4TxPower * 100)
        msg = self.build_cmd(length, cr_opcode, word1=ant_power1, word2=ant_power2, word3=ant_power3, word4=ant_power4, word_type='int')
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(1000)
            error, res = self.wait_for_response_short(self.UHFBytes.SET_TX_POWER)
            if res == b'':
                error, res = self.wait_for_response_long(self.UHFBytes.SET_TX_POWER)
               
        if error is None:
            # parse response (res)
            if not res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.SET_TX_POWER:
                error = "Unable to set tx power to {}, {}, {}, {}".format(ant1TxPower, ant2TxPower, ant3TxPower, ant4TxPower)
                print(error, flush=True)
                
        return error


    def get_tag_report(self):
        """
            Gets tag report
        """
        print("Getting tag report...", flush=True)
        length = '0006'
        cr_opcode = '0009'   
        epc_length = '0000'      
        msg = self.build_cmd(length, cr_opcode, word1=epc_length, word_type='byt')
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_TAG_REPORT)

        tag_report = None    
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_TAG_REPORT:
                # parse response (res)
                # example res: b'\xf6(\x00(\x80\t\x00\x00\x00\x06\x06\x07\xe7.b\xb65\xce\x00\x02\x00\x14\x01\x11\x08\x00\x00\x00\x00\x00\x00\x00\x02GQ\x00\x13\x00\x03\x9e\xff\x03'
                rep = int.from_bytes(res[8:10], 'big') 
                match rep:
                    case 0x0001:
                        # A new tag was added to the observed tag population
                        reply_reason = 'New Tag Seen'
                    case 0x0002:
                        # A tag has not been seen for the configured tag timeout value
                        reply_reason = 'Tag Removed'
                    case 0x0003:
                        # The tag’s reported RSSI value has changed significantly since its last report.
                        reply_reason = 'Power Changed'
                    case 0x0004:
                        # A requested GEN2 operation for this tag has completed
                        reply_reason = 'GEN2 Op Completed'
                    case 0x0005:
                        # If configured, a tag will be periodically reported upon at a specified interval.
                        reply_reason = 'Tag Report Timeout'
                    case 0x0006:
                        # The host requested that one or more tags be reported upon.
                        reply_reason = 'Report Requested'
                    case _:
                        # Should never hit this line
                        reply_reason = 'Not defined'
                
                power_rssi_raw = int.from_bytes(res[10:12], byteorder='big', signed=True)
                power_dbm = int.from_bytes(res[12:14], byteorder='big', signed=True)
                timestamp = int.from_bytes(res[14:18], 'big')
                antenna = int.from_bytes(res[18:20], 'big')
                epc_length = int.from_bytes(res[20:len(res)], 'big')
                
                tag_report = {
                    "replyReason": reply_reason,
                    "powerRSSIRaw": power_rssi_raw,
                    "powerdBm": power_dbm,
                    "timestamp": timestamp,
                    "antenna": antenna,
                    "epcLength": epc_length              
                }  
            else:
                error = "Unable to get a tag report"
                print(error, flush=True)                     
                
        return error, tag_report


    def get_ant_enables(self):
        """
            Gets the status of all four antennas (enabled or disabled)
        """
        print("Getting antenna enables...", flush=True)
        length = '0004'
        cr_opcode = '000F'   
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_ANT_ENABLES)

        ant_enables = None    
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_ANT_ENABLES:
                # parse response (res)
                # example res: 
                bit_vector = int.from_bytes(res[8:len(res)], 'big')                
                ant_1_enables = self.bit_status(bit_vector,0)
                ant_2_enables = self.bit_status(bit_vector,1)
                ant_3_enables = self.bit_status(bit_vector,2)
                ant_4_enables = self.bit_status(bit_vector,3)
                ant_enables = {
                    "ant1enables": ant_1_enables,
                    "ant2enables": ant_2_enables,
                    "ant3enables": ant_3_enables,
                    "ant4enables": ant_4_enables
                }
            else:
                error = "Unable to get antenna enables!"
                print(error, flush=True)
                
        return error, ant_enables
    
    
    def set_ant_enables(self, ant1Enables, ant2Enables, ant3Enables, ant4Enables):
        """
            Enables/disables all four antennas 
        """
        print("Setting antenna enables...", flush=True)
        length = '0006'
        cr_opcode = '000E'   
        ant_enables = int('0000{}{}{}{}'.format(ant4Enables, ant3Enables, ant2Enables, ant1Enables), 2) 
        msg = self.build_cmd(length, cr_opcode, word1=ant_enables, word_type='int')
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(1000)
            error, res = self.wait_for_response_short(self.UHFBytes.SET_ANT_ENABLES)
            if res == b'':
                error, res = self.wait_for_response_long(self.UHFBytes.SET_ANT_ENABLES)
               
        if error is None:
            # parse response (res)
            # example: b'\xf6(\x00\x06\x80\x0e\x00\x00'
            if not res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.SET_ANT_ENABLES:
                error = "Unable to set antenna enables!"
                print(error, flush=True)
                
        return error    

    
    def set_op_state(self, op_state):
        """
            Sets operating state
        """
        print("Setting operating state...", flush=True)
        length = '0006'
        cr_opcode = '000C'   
        msg = self.build_cmd(length, cr_opcode, word1=op_state, word_type='byt')
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(1000)
            error, res = self.wait_for_response_short(self.UHFBytes.SET_OP_STATE)
            if res == b'':
                error, res = self.wait_for_response_long(self.UHFBytes.SET_OP_STATE)
               
        if error is None:
            # parse response (res)
            if not res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.SET_OP_STATE:
                error = "Unable to set operating state to '{}'".format(op_state)
                print(error, flush=True)
                
        return error   
    
    
    def get_op_state(self):
        """
            Gets operating state
        """
        print("Getting operating state...", flush=True)
        length = '0004'
        cr_opcode = '000D'         
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)
        
        res = None
        error = None
        error = self.send_cmd(msg)
        if error is None:
            wait_ms(500)
            error, res = self.wait_for_response_short(self.UHFBytes.GET_OP_STATE)
            # error, res = self.wait_for_response_long(self.UHFBytes.GET_OP_STATE)
        
        op_state = None    
        if error is None:
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.GET_OP_STATE:
                # parse response (res)
                # example res: b'\xf6(\x00\n\x80\r\x00\x00\x00\x00\x00\x00'
                rep = int.from_bytes(res[10:12], 'big') 
                match rep:
                    case 0x0000: 
                        op_state = 'Idle'
                    case 0x0001:
                        op_state = 'CW Test'
                    case 0x0002:
                        op_state = 'PRBS Test'
                    case 0x0003:
                        op_state = 'ETSI Burst Test'
                    case 0x0004:
                        op_state = 'Tag Read'
                    case 0x0005:
                        op_state = 'Over Temp'
                    case 0x0006:
                        op_state = 'Reader_Error'
                    case 0x0007:
                        op_state = 'Hard_Reset'
                    case 0x0008:
                        op_state = 'SW_Mismatch'
                    case 0x0009:
                        op_state = 'Bootloader'  
                    case _:
                        op_state = 'Not defined'
            else:
                error = "Unable to get operating state"
                print(error, flush=True)
                
        return error, op_state
    

    def keep_alive(self):
        """
            Sends 'Keep-Alive' message to the reader
        """
        # print("Keeping UHF reader alive...", flush=True) 
        length = '0004'
        cr_opcode = '0001' 
        msg = self.build_cmd(length=length, cr_opcode=cr_opcode)

        # Loop until the UHF reader is awake and we get a response from it!
        count = 0
        res = None
        error = None
        while count < 15:
            count += 1
            # print("count: {}".format(count), flush=True)
            error = self.send_cmd(msg)
            if error is None:
                error, res = self.wait_for_response_short(self.REC_TIMEOUT)
                if not (res is None) and (res != b''):
                    break
            wait_ms(1000)        
        # print("res: {}".format(res), flush=True)
            
        alive = None
        if error is None:
            # parse response (res)
            if res[6:8] == self.UHFBytes.STATUS_SUCCESS and res[4:6] == self.UHFBytes.KEEP_ALIVE:
                alive = True
            else:
                error = "Unable to keep UHF module alive"
                print(error, flush=True)
                
        return error, alive
    
 
    def start_reading(self):
        """
            This method is called as soon as the server starts running. It will send keep-alive messages 
            to the reader, until it receives an order to get a report. It then sets and gets a number of
            parameters and sends them back to the server.
        """
        # Open the serial port for communication
        err = self.ser.serial_open()
        if err is None:
            while True:       
                alive = None
                errorAll = None
                version = None
                temp = None
                op_reg = None
                tx_power = None
                ant_enables = None
                op_state = None
                tag_report = None
                tag_report_timeout = None
                event_mask = None
                
                error_keep_alive = None
                error_op_region_set = None
                error_set_tx_power = None
                error_set_ant_enables = None
                error_version_get = None
                error_temp_get = None
                error_op_reg_get = None
                error_tx_power_get = None
                error_get_ant_enables = None
                error_tag_report_get = None
                error_set_op_state = None
                error_op_state_get = None
                error_get_op_params = None
                error_set_op_params = None
                error_get_event_mask = None
                error_set_event_mask = None

                # Loops with 'Keep Alive' until the UHF reader receives a command from client to start reading
                startReading = False
                params = {}
                while not startReading:
                    params, startReading = self.get_uhf_params()
                    error_keep_alive, alive = self.keep_alive()
                    wait_ms(1000)
                self.set_uhf_params(False, {})
                
                if error_keep_alive is None:
                    ## Get parameters
                    tagReport = params["tagReport"]
                    soundEffect = params["soundEffect"]
                    opRegion = params["opRegion"]
                    ant1TxPower = params["ant1TxPower"]
                    ant2TxPower = params["ant2TxPower"]
                    ant3TxPower = params["ant3TxPower"]
                    ant4TxPower = params["ant4TxPower"]
                    ant1Enables = params["ant1Enables"]
                    ant2Enables = params["ant2Enables"]
                    ant3Enables = params["ant3Enables"]
                    ant4Enables = params["ant4Enables"]
                    print("[{}] UHF reader params: {}".format(get_fun_name(), params), flush=True)
                    
                    ## Sets
                    error_set_op_state = self.set_op_state(self.UHFOperatingState.IDLE) # Set operating state to idle to avoid interference
                    error_op_region_set = self.set_op_region(opRegion) 
                    error_set_tx_power = self.set_tx_power(ant1TxPower, ant2TxPower, ant3TxPower, ant4TxPower)
                    error_set_ant_enables = self.set_ant_enables(ant1Enables, ant2Enables, ant3Enables, ant4Enables)
                    # New params
                    # error_set_op_params = self.set_operational_param(self.OPParams.TAG_REPORT_TIMEOUT_CODE, 50000)
                    # error_set_event_mask = self.set_event_mask(1, 1, 1, 1, 1, 1)                
                    
                    ## Gets
                    # Now that the UHF reader is awake, get other information from it
                    error_version_get, version = self.get_version()        
                    error_temp_get, temp = self.get_temp()
                    error_op_reg_get, op_reg = self.get_op_region()
                    error_tx_power_get, tx_power = self.get_tx_power()
                    error_get_ant_enables, ant_enables = self.get_ant_enables()
                    # New params
                    # error_get_op_params, tag_report_timeout = self.get_operational_params(self.OPParams.TAG_REPORT_TIMEOUT_CODE)
                    # error_get_event_mask, event_mask = self.get_event_mask()

                    # Keep alive
                    error_keep_alive, alive = self.keep_alive()
                    error_keep_alive, alive = self.keep_alive()
                    
                    ## Read tags in the range
                    if tagReport:
                        error_set_op_state = self.set_op_state(self.UHFOperatingState.TAG_READ) # Must be set for tag read!
                        error_op_state_get, op_state = self.get_op_state() 
                                               
                        i = 0
                        while i < 10:
                            i += 1
                            error_tag_report_get, tag_report = self.get_tag_report()  
                            print("tag_report: {}".format(tag_report), flush=True)                     
                            if tag_report is not None:                            
                                break
                        
                        # Set operating state to IDLE as soon as down
                        error_set_op_state = self.set_op_state(self.UHFOperatingState.IDLE)
                        
                        # If soundEffect is enabled
                        if soundEffect:
                            # If a tag was detected, emit a signal to play an audio file
                            if not error_tag_report_get:
                                self.signal_tag_detected_audio.emit()

                # Aggregate error messages
                errorAll = {
                    "keep_alive": error_keep_alive,
                    "opSate_set": error_set_op_state,
                    "opRegion_set": error_op_region_set,
                    "SET_TX_POWER": error_set_tx_power,
                    "SET_ANT_ENABLES": error_set_ant_enables,
                    "version_get": error_version_get,
                    "temp_get": error_temp_get,
                    "op_reg_get": error_op_reg_get,
                    "tx_power_get": error_tx_power_get,
                    "GET_ANT_ENABLES": error_get_ant_enables,
                    "op_state_get": error_op_state_get,
                    "tag_report_get": error_tag_report_get
                }
                
                # Aggregate all reads into a dictionary
                meta_data = {
                    "error": errorAll,
                    "alive": alive,
                    "version": version,
                    "temp": temp,
                    "op_reg": op_reg,
                    "tx_power": tx_power,
                    "ant_enables": ant_enables,
                    "op_state": op_state,
                    "tag_report": tag_report
                }
                
                # Emit the data as a dictionary
                self.signal_give_uhf_meta_data.emit(True, meta_data)        
                print("[{}] Give-UHF-data signal emitted...: {}".format(get_fun_name(), err), flush=True)
 
        else:
            meta_data = {
                "error": err
            }
            self.signal_give_uhf_meta_data.emit(True, meta_data)        
            print("[{}] error: {}".format(get_fun_name(), err), flush=True)

        return err
    
      
  

    