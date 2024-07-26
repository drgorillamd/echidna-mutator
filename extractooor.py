import os
import json
from typing import List, Dict
import re

indentation = "    "

def read_json_files(directory: str) -> List[Dict]:
    json_data = []
    for filename in os.listdir(directory):
        if filename.endswith('.txt'):
            with open(os.path.join(directory, filename), 'r') as file:
                json_data.append(json.load(file))
    return json_data

def generate_test_function(json_data: List[Dict], test_number: int) -> str:
    function_name = f"test_echidna_corpus_{test_number}"
    test_function = f"{indentation}function {function_name}() public {{\n"
    
    for call in json_data:
        function_call = call['call']['contents'][0]
        args = call['call']['contents'][1]
        
        # Convert arguments to strings
        arg_strings = []
        for arg in args:
            if arg['tag'] == 'AbiUInt':
                arg_strings.append(parse_uint(arg))
            
            if arg['tag'] == 'AbiAddress':
                arg_strings.append(parse_address(arg))

            if arg['tag'] == 'AbiString':
                arg_strings.append(parse_string(arg))

            if arg['tag'] == 'AbiBytes':
                arg_strings.append(parse_bytes(arg))

            if arg['tag'] == 'AbiArrayDynamic':
                array = []
                for sub_arg in arg['contents'][1]:
                    if sub_arg['tag'] == 'AbiUInt':
                        array.append(parse_uint(sub_arg))
                    
                    if sub_arg['tag'] == 'AbiAddress':
                        array.append(parse_address(sub_arg))

                arg_strings.append(f"[{', '.join(array)}]")

        # Set up the environment for the call
        test_function += f"{2*indentation}vm.prank({call['src']});\n"

        if(call['value'] != "0x0000000000000000000000000000000000000000000000000000000000000000"):
            test_function += f"{2*indentation}vm.deal({call['src']}, {int(call['value'], 16)});\n"

        if(call['gasprice'] != "0x0000000000000000000000000000000000000000000000000000000000000000"):
            test_function += f"{2*indentation}vm.txGasPrice({int(call['gasprice'], 16)});\n"

        # todo: what are the 2 values?
        # test_function += f"    vm.warp({int(call['delay'][0], 16)});\n"
        
        # Generate the function call
        test_function += f"{2*indentation}echidnaTestProxy.{function_call}{{gas: {call['gas']}, value: {int(call['value'], 16)}}}({', '.join(arg_strings)});\n\n"
    
    test_function += "}\n"
    return test_function

def parse_uint(arg):
    return f"uint{str(int(arg['contents'][0]))}({str(int(arg['contents'][1]))})"

def parse_address(arg):
    return f"address({arg['contents']})"

def parse_string(arg):
    return f"{arg['contents']}"

def parse_bytes(arg):
    return f"bytes{arg['contents'][0]}({parse_haskell_bytestring(arg['contents'][1])})"

# Ask hell bytestring parser - todo - incorrect output!!
def parse_haskell_bytestring(s):
    escape_sequences = {
        'NUL': 0, 'SOH': 1, 'STX': 2, 'ETX': 3, 'EOT': 4, 'ENQ': 5, 'ACK': 6, 'BEL': 7,
        'BS': 8, 'HT': 9, 'LF': 10, 'VT': 11, 'FF': 12, 'CR': 13, 'SO': 14, 'SI': 15,
        'DLE': 16, 'DC1': 17, 'DC2': 18, 'DC3': 19, 'DC4': 20, 'NAK': 21, 'SYN': 22, 'ETB': 23,
        'CAN': 24, 'EM': 25, 'SUB': 26, 'ESC': 27, 'FS': 28, 'GS': 29, 'RS': 30, 'US': 31,
        'SP': 32, 'DEL': 127
    }

    bytes_list = []
    i = 0
    while i < len(s):
        if s[i] == '\\':
            if i + 1 < len(s) and s[i+1].isdigit():  # Octal escape
                j = i + 1
                while j < len(s) and j < i + 4 and s[j] in '01234567':
                    j += 1
                octal_str = s[i+1:j]
                byte_val = int(octal_str, 8)
                if byte_val > 255:
                    raise ValueError(f"Invalid octal value: {octal_str}")
                bytes_list.append(byte_val)
                i = j
            elif i + 1 < len(s) and s[i+1] in 'abfnrtv':  # Common escapes
                escape_char = s[i+1]
                bytes_list.append({
                    'a': 7, 'b': 8, 'f': 12, 'n': 10, 'r': 13, 't': 9, 'v': 11
                }[escape_char])
                i += 2
            elif i + 3 < len(s) and s[i+1:i+4] in escape_sequences:  # Named escapes
                escape = s[i+1:i+4]
                bytes_list.append(escape_sequences[escape])
                i += 4
            else:
                bytes_list.append(ord('\\'))
                i += 1
        else:
            bytes_list.append(ord(s[i]))
            i += 1

    return '0x'+''.join(f'{b:02x}' for b in bytes_list)

def generate_foundry_tests(directory: str, output_file: str):
    json_data_list = read_json_files(directory)
    
    with open(output_file, 'w') as file:
        file.write("// SPDX-License-Identifier: MIT\n")
        file.write("pragma solidity ^0.8.13;\n\n")
        file.write("import {Test} from \"forge-std/Test.sol\";\n")
        file.write("import {EchidnaTestProxy} from \"./EchidnaTestProxy.sol\";\n\n")
        file.write("contract EchidnaCorpusTest is Test {\n")
        file.write("    EchidnaTestProxy public echidnaTestProxy;\n\n")
        file.write("    function setUp() public {\n")
        file.write("        echidnaTestProxy = new EchidnaTestProxy();\n")
        file.write("    }\n\n")
        
        for i, json_data in enumerate(json_data_list):
            file.write(generate_test_function(json_data, i+1))
            file.write("\n")
        
        file.write("}\n")

# Usage
generate_foundry_tests("./", "EchidnaCorpusTest.sol")