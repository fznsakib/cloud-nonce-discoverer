import os
import argparse
import random
import hashlib
import binascii

parser = argparse.ArgumentParser(description='A golden nonce discoverer for blocks discovered concurrently using AWS.')
parser.add_argument("--n", default=0, type=int, help="The number of Virtual Machines to distribute the brute force search to")
parser.add_argument("--d", default=10, type=int, help="The difficulty of nonce discovery. This corressponds to the number of leading zero bits required in the hash.")

args = parser.parse_args()

no_of_vms = args.n
difficulty = args.d

max_nonce = 2 ** 32

# Create block with the data and provided nonce
def get_block(nonce):
    data = "COMSM0010cloud"
    # Convert data into binary. Remove first two characters ('0b')
    bin_data = bin(int.from_bytes(data.encode(), 'big'))[2:]
    block = str(bin_data) + str(nonce)
    return block

def get_block_hash(block):
    block_bytes = str.encode(block)
    block_hash = hashlib.sha256(block_bytes)
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
    # Brute force through all possible nonce values
    for nonce in range(0, max_nonce):
        block = get_block(nonce)
        block_hash = get_block_hash(block)
        block_hash_binary = get_block_hash_binary(block_hash)

        leading_zeroes = len(block_hash_binary.split('1', 1)[0])

        # print(block_hash_binary)
        print(f'number of leading zeroes: {leading_zeroes}')

        if (leading_zeroes == difficulty):
            print(f'nonce {nonce} contains require leading zeroes of {difficulty}')
            print(f'block = {block_hash_binary}')
            exit()




        

        