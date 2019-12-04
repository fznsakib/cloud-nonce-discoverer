import os
import sys
import boto3
import json
import signal
import argparse
import random
import hashlib
import binascii
import datetime
import time
from threading import Thread 

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""
AWS functions
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

def getQueueURL(queue_name):
    response = sqs.get_queue_url(QueueName=queue_name)
    queue_url = response['QueueUrl']
    return queue_url

max_nonce = 2 ** 32

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Argument Parsing
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

parser = argparse.ArgumentParser(description='A golden nonce discoverer for blocks running concurrently using AWS.')
parser.add_argument("--start", default=0, type=int, help="The number to start brute force search from.")
parser.add_argument("--end", default=max_nonce, type=int, help="The number to end brute force search at.")
parser.add_argument("--difficulty", default=10, type=int, help="The difficulty of nonce discovery. This corresponds to the number of leading zero bits required in the hash.")
parser.add_argument("--id", default='', type=str, help="The ID of the EC2 instance the script will be run on.")
parser.add_argument("--datetime", default='', type=str, help="The datetime represents the start of the overall process. Used as an identifier for the log for this process.")
parser.add_argument("--logscram", default=False, type=bool, help="Gives the option to collect logs from instances on scram.")

args = parser.parse_args()

start_nonce = args.start
max_nonce = args.end
difficulty = args.difficulty
instance_id = args.id
date_time = args.datetime
log_on_scram = args.logscram

log_group_name = 'PoW_logs'
log_stream_name = f'{date_time}-{instance_id}'

nonce_found = False
scram_requested = False

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Initialise interface to AWS
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

sqs = boto3.client('sqs', region_name='us-east-1')
sqs_resource = boto3.resource('sqs', region_name='us-east-1')
logs = boto3.client('logs', region_name='us-east-1')
s3 = boto3.resource('s3')

scram_queue_url = getQueueURL('scram_queue')
out_queue_url = getQueueURL('outqueue.fifo')
scram_queue = sqs_resource.Queue(scram_queue_url)
out_queue = sqs_resource.Queue(out_queue_url)


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Proof of Work helper functions
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

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


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Main threads
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

# Thread to search for golden nonce within search space
def findNonce():
    global nonce_found
    global current_nonce
    global start_time
    
    current_nonce = args.start
    start_time = datetime.datetime.now()
        
    # Brute force through all possible nonce values
    while (current_nonce <= max_nonce):        
        block = get_block(current_nonce)
        block_hash = get_block_hash(block)
        block_hash_binary = get_block_hash_binary(block_hash)
        leading_zeroes = len(block_hash_binary.split('1', 1)[0])

        # If the golden nonce is found
        if (leading_zeroes >= difficulty):
            time_taken = (datetime.datetime.now() - start_time).total_seconds()
            
            # Prepare message to send    
            message = {
                'success': True,
                'instanceId'  : instance_id,
                'goldenNonce' : current_nonce,
                'goldenHash'  : block_hash.hexdigest(),
                'searchStart' : start_nonce,
                'searchEnd'   : max_nonce,
                'searchTime'  : time_taken
            }
            
            # Send message to out_queue to notify the client that nonce 
            # has been found
            response = out_queue.send_message(
                MessageBody=(
                    json.dumps(message)
                ),
                MessageGroupId='0',
            )

            nonce_found = True
            break
        
        current_nonce += 1
    
    sys.exit(1)
           
# Thread acting as listener to scram_queue
def waitForExternalNonceDiscovery():
    global scram_requested
    
    message_received = False
    
    # Wait for notification for if nonce if found elsewhere
    while not message_received: 
        message = scram_queue.receive_messages(
            MaxNumberOfMessages=1,
            VisibilityTimeout=10,
            WaitTimeSeconds=20,
        )
        
        # Delete message from queue
        if message:
            message_received = True
            
            response = scram_queue.delete_messages(
                Entries=[{
                    'Id': message[0].message_id,
                    'ReceiptHandle': message[0].receipt_handle
                }]
            )
    
    time_taken = (datetime.datetime.now() - start_time).total_seconds()
    
    
    # Prepare message to log
    message = {
        'success': False,
        'instanceId' : instance_id,
        'lastNonce'  : current_nonce,
        'searchStart': start_nonce,
        'searchEnd'  : max_nonce,
        'searchTime' : float(f'{time_taken:.6f}'),
        'difficulty' : difficulty,
        'logOnScram' : True
    }
    
    # Create log stream
    response = logs.create_log_stream(
        logGroupName=log_group_name,
        logStreamName=log_stream_name
    )
    
    # Upload log to stream
    response = logs.put_log_events(
        logGroupName=log_group_name,
        logStreamName=log_stream_name,
        logEvents=[
            {
                'timestamp': int(round(time.time() * 1000)),
                'message': json.dumps(message)
            },
        ],
    )
    
    scram_requested = True
    sys.exit(1)  


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""
pow.py main()

# This Proof of Work script initiates two threads:
#   1. Search for the golden nonce within the given search space
#   2. Listen to scram_queue for when logging and shut down required

# The program will finish at the event of completion of either thread,
# signalling the discovery of the golden nonce to a scram request.
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

if __name__ == "__main__":
    if log_on_scram:
        t1 = Thread(target=findNonce, daemon=True)
        t2 = Thread(target=waitForExternalNonceDiscovery, daemon=True)

        t1.start()
        t2.start()
    else:
        findNonce()

    
    while (nonce_found == False) and (scram_requested == False):
        pass
    
    sys.stdout.write('EXIT PROGRAM')
    sys.exit()
    os.exit()
    




        

        