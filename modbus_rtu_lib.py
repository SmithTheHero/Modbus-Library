import serial
import struct
import os
from crc16 import crc16


class CrcError(Exception):
    pass


class FunctionError(Exception):
    pass


class Modbus:
    def __init__(self, port:str, baudrate:int, stopbits:int, read_timeout:float, write_timeout:float, echo=False, print_request=False, print_response=False, locale='en-US'):
        self.port = serial.Serial(port, baudrate=baudrate, stopbits=stopbits, timeout=read_timeout, write_timeout=write_timeout)
        self.echo = echo
        self.print_request = print_request
        self.print_response = print_response

        self.locale_table = {
            'ru-RU': {'no_respond':'Устройство не отвечает',
                      'crc_is_not_correct':'CRC не совпал',
                      'invalid_function':'Неверная функция',
                      'invalid_device_addr':'Адрес устройства находится вне диапазона (0-255)',
                      'invalid_integer_format':'Неверный формат целых чисел (не short, long или long long)',
                      'invalid_float_format':'Неверный формат чисел с плавающей точкой (не float или double)'},

            'en-US': {'no_respond':'Device is not responding',
                      'crc_is_not_correct':'CRC is not correct',
                      'invalid_function':'Invalid function',
                      'invalid_device_addr':'Device address is not in range (0-255)',
                      'invalid_integer_format':'Invalid integer format (is not short, long or long long)',
                      'invalid_float_format':'Invalid float format (is not float or double)'}
        }

        if locale in self.locale_table:
            self.locale = locale
        else:
            raise ValueError('Unknown locale (choose from {})'.format(tuple(i for i in self.locale_table)))


    def _check_device_addr(self, device_addr):
        if not 0 >= device_addr <= 255:
            raise ValueError(self.locale_table[self.locale]['invalid_device_addr'])


    def _read_echo(self, request):
        if self.echo:
            self.port.read(len(request))


    def _check_response(self, response):
        if len(response) == 0:
            raise TimeoutError(self.locale_table[self.locale]['no_respond'])


    def _check_crc(self, response):
        test_crc = crc16(response[0:-2])
        if test_crc != response[-2:]:
            raise CrcError(self.locale_table[self.locale]['crc_is_not_correct'])


    def _check_command(self, command, response):
        if response[1:2] != command:
            raise FunctionError(self.locale_table[self.locale]['invalid_function'])


    def _print_request(self, request):
        if self.print_request:
            formatted_request = ''
            for i in request:
                formatted_request += os.path.sep
                if len(str(hex(i))[1:]) == 3:
                    formatted_request += str(hex(i))[1:]
                else:
                    formatted_request += '0'.join(str(hex(i))[1:])
            print(formatted_request)


    def _print_response(self, response):
        if self.print_response:
            formatted_response = ''
            for i in response:
                formatted_response += os.path.sep
                if len(str(hex(i))[1:]) == 3:
                    formatted_response += str(hex(i))[1:]
                else:
                    formatted_response += '0'.join(str(hex(i))[1:])
            print(formatted_response)


    def _return_bytes(self, command:bytes, device_addr:int, start_reg_addr:int, regs_amount:int) -> bytes:
        self._check_device_addr(device_addr)
        byte_start_reg_addr = struct.pack('>H', start_reg_addr)
        byte_regs_amount = struct.pack('>H', regs_amount)

        request_wo_crc = bytes(device_addr) + command + byte_start_reg_addr + byte_regs_amount
        crc = crc16(request_wo_crc)

        request = request_wo_crc + crc
        self._print_request(request)
        self.port.write(request)
        self._read_echo(request)

        response = self.port.read(regs_amount * 2 + 5)
        self._print_response(response)
        self._check_response(response)
        self._check_crc(response)
        self._check_command(command, response)

        return response[3:-2]

    
    def read_do_integers(self, device_addr:int, start_reg_addr:int, ints_amount:int) -> list[int]:
        command = b'\x01'

        byte_data = self._return_bytes(command, device_addr, start_reg_addr, ints_amount)
        data = [int(i) for i in bin(int.from_bytes(byte_data, 'big'))[2:]]

        return data


    def read_di_integers(self, device_addr:int, start_reg_addr:int, ints_amount:int) -> list[int]:
        command = b'\x02'

        byte_data = self._return_bytes(command, device_addr, start_reg_addr, ints_amount)
        data = [int(i) for i in bin(int.from_bytes(byte_data, 'big'))[2:]]

        return data


    def read_ao_integers(self, device_addr:int, start_reg_addr:int, ints_amount:int, int_format='short', is_signed=False) -> list[int]:
        command = b'\x03'

        if int_format == 'short':
            int_format_char = 'h'
            regs_amount = ints_amount

        elif int_format == 'long':
            int_format_char = 'l'
            regs_amount = ints_amount*2

        elif int_format == 'long long':
            int_format_char = 'q'
            regs_amount = ints_amount*4

        else:
            raise ValueError(self.locale_table[self.locale]['invalid_integer_format'])

        if not is_signed:
            int_format_char.upper()

        byte_data = self._return_bytes(command, device_addr, start_reg_addr, regs_amount)
        data = [i for i in struct.unpack('>'+int_format_char*ints_amount, byte_data)]

        return data


    def read_ao_floats(self, device_addr:int, start_reg_addr:int, floats_amount:int, float_precision='float') -> list[float]:
        command = b'\x03'

        if float_precision == 'float':
            float_format_char = 'f'
            regs_amount = floats_amount*2

        elif float_precision == 'double':
            float_format_char = 'd'
            regs_amount = floats_amount*4

        else:
            raise ValueError(self.locale_table[self.locale]['invalid_float_format'])

        byte_data = self._return_bytes(command, device_addr, start_reg_addr, regs_amount)
        data = [i for i in struct.unpack('>'+float_format_char*floats_amount, byte_data)]

        return data