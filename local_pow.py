import os
import argparse
import random
import hashlib
import binascii
from datetime import datetime

parser = argparse.ArgumentParser(description='A locally run golden nonce discoverer for blocks.')
parser.add_argument("--d", default=10, type=int, help="The difficulty of nonce discovery. This corressponds to the number of leading zero bits required in the hash.")

args = parser.parse_args()

difficulty = args.d

max_nonce = 2 ** 32

# Create block with the data and provided nonce
def get_block(nonce):
    data = "COMSM0010cloud"
    block = data + str(nonce)    
    return block

def get_block_hash(block):
    block_hash = hashlib.sha256(str.encode(block))
    block_hash = hashlib.sha256(str.encode(block_hash.hexdigest()))
    return block_hash

# Get block hash in binary representation
def get_block_hash_binary(block_hash):
    block_hash_string = block_hash.hexdigest()
    # To get the leading zeroes in the binary representation, 
    # prepend a '1' to the hex string, and then strip the 
    # corresponding '1' from the output.
    block_hash_binary = bin(int('1'+block_hash_string, 16))[3:]    
    return block_hash_binary

# Nonce discovery
if __name__ == "__main__":
    start_time = datetime.now()
    nonce = 0
    
    # Brute force through all possible nonce values
    while (nonce <= max_nonce):
        block = get_block(nonce)
        block_hash = get_block_hash(block)
        block_hash_binary = get_block_hash_binary(block_hash)
        
        leading_zeroes = len(block_hash_binary.split('1', 1)[0])
        
        print(f'number of leading zeroes: {leading_zeroes}')

        if (leading_zeroes >= difficulty):
            print(f'nonce {nonce} contains require leading zeroes of {difficulty}')
            time_taken = (datetime.now() - start_time).total_seconds()
            print(f'time taken: {time_taken:.6f}')
            exit()
        
        nonce += 1




        

        