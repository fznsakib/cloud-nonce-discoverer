import os
import random
import hashlib
import binascii


maxNonce = 2 ** 32

def generateNonce():
    maxNonce = 2 ** 32
    return random.randint(0, maxNonce)

# Create block with the data and provided nonce
def getBlock(nonce):
    data = "COMSM0010cloud"
    # Convert data into binary. Remove first two characters ('0b')
    binData = bin(int.from_bytes(data.encode(), 'big'))[2:]
    block = str(binData) + str(nonce)
    return block

# Get hash of provided block
def getBlockHash(block):
    blockBytes = str.encode(block)
    blockHash = hashlib.sha256(blockBytes)
    return blockHash

# Get block hash in binary representation
def getBlockHashBinary(blockHash):
    blockHashString = blockHash.hexdigest()
    
    # To get the leading zeroes in the binary representation, 
    # prepend a '1' to the hex string, and then strip the 
    # corresponding '1' from the output.
    blockHashBinary = bin(int('1'+blockHashString, 16))[3:]
    return blockHashBinary

if __name__ == "__main__":

    # Brute force through all possible nonce values
    for nonce in range(0, maxNonce):
        block = getBlock(nonce)
        blockHash = getBlockHash(block)
        blockHashBinary = getBlockHashBinary(blockHash)
        print(blockHashBinary)


        

        