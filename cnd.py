import os
import boto3
import json
import argparse
import random
import hashlib
import binascii
import datetime

max_nonce = 2 ** 32

parser = argparse.ArgumentParser(description='A golden nonce discoverer for blocks running concurrently using AWS.')
parser.add_argument("--start", default=0, type=int, help="The number to start brute force search from")
parser.add_argument("--end", default=max_nonce, type=int, help="The number to end brute force search at")
parser.add_argument("--d", default=10, type=int, help="The difficulty of nonce discovery. This corresponds to the number of leading zero bits required in the hash.")

args = parser.parse_args()

start_nonce = args.start
max_nonce = args.end
difficulty = args.d

sqs = boto3.client('sqs', region_name='us-east-1')

def getQueueURL(queue_name):
    response = sqs.get_queue_url(QueueName=queue_name)
    queue_url = response['QueueUrl']
    return queue_url

# Create block with the data and provided nonce
def get_block(nonce):
    data = "COMSM0010cloud"
    # Convert data into binary. Remove first two characters ('0b')
    bin_data = bin(int.from_bytes(data.encode(), 'big'))[2:]
    block = str(bin_data) + str(nonce)
    return block

def get_block_hash(block):
    block_hash = hashlib.sha256(str.encode(block))
    return block_hash

# Get block hash in binary representation
def get_block_hash_binary(block_hash):
    block_hash_string = block_hash.hexdigest()
    # To get the leading zeroes in the binary representation, 
    # prepend a '1' to the hex string, and then strip the 
    # corresponding '1' from the output.
    block_hash_binary = bin(int('1'+block_hash_string, 16))[3:]
    return block_hash_binary

def nonce_found(golden_nonce, block_binary, time_taken):
    # f = open("home/ec2-user/nonce.txt", "w")
    # f.write(str(golden_nonce))
    # f.close()
    
    # Send result to queue for local machine to read
    out_queue_url = getQueueURL('outqueue.fifo')
    message = {
        'nonce' : golden_nonce,
        'blockBinary': block_binary,
        'timeTaken': time_taken
    }
    response = sqs.send_message(
        QueueUrl=out_queue_url,
        MessageBody=(
            json.dumps(message)
        ),
        MessageGroupId='0',
    )

# Nonce discovery
if __name__ == "__main__":
    start_time = datetime.datetime.now()
    current_nonce = start_nonce
    golden_nonce = 0
    
    # Brute force through all possible nonce values
    while (current_nonce <= max_nonce):
        block = get_block(current_nonce)
        block_hash = get_block_hash(block)
        block_hash_binary = get_block_hash_binary(block_hash)
        leading_zeroes = len(block_hash_binary.split('1', 1)[0])

        if (leading_zeroes == difficulty):
            time_taken = (datetime.datetime.now() - start_time).total_seconds()
            nonce_found(current_nonce, block_hash_binary, time_taken)
            break
        
        current_nonce += 1
        

            




        

        