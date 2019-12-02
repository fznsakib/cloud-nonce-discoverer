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


max_nonce = 2 ** 32

parser = argparse.ArgumentParser(description='A golden nonce discoverer for blocks running concurrently using AWS.')
parser.add_argument("--start", default=0, type=int, help="The number to start brute force search from.")
parser.add_argument("--end", default=max_nonce, type=int, help="The number to end brute force search at.")
parser.add_argument("--difficulty", default=10, type=int, help="The difficulty of nonce discovery. This corresponds to the number of leading zero bits required in the hash.")
parser.add_argument("--id", default='', type=str, help="The ID of the EC2 instance the script will be run on.")
parser.add_argument("--log", default='', type=str, help="The name of the log group this script will log to.")


args = parser.parse_args()

start_nonce = args.start
current_nonce = args.start
max_nonce = args.end
difficulty = args.difficulty
instance_id = args.id

log_group_name = args.log
log_stream_name = instance_id

sqs = boto3.client('sqs', region_name='us-east-1')
sqs_resource = boto3.resource('sqs', region_name='us-east-1')
logs = boto3.client('logs', region_name='us-east-1')
s3 = boto3.resource('s3')

i_found_nonce = False
they_found_nonce = False

# Create log stream
response = logs.create_log_stream(
    logGroupName=log_group_name,
    logStreamName=log_stream_name
)

def getQueueURL(queue_name):
    response = sqs.get_queue_url(QueueName=queue_name)
    queue_url = response['QueueUrl']
    return queue_url


ec2_queue_url = getQueueURL('scram_queue')
ec2_queue = sqs_resource.Queue(ec2_queue_url)

# def terminate(signum, frame):
#     sys.stdout.write('HELLO IN EXIT HANDLER')  
#     exit()
    

# signal.signal(signal.SIGINT, terminate)
# signal.signal(signal.SIGTERM, terminate)
# signal.signal(signal.SIGABRT, terminate)



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

def nonce_found(golden_nonce, block_binary, time_taken):
    
    # Send result to queue for local machine to read
    out_queue_url = getQueueURL('outqueue.fifo')
    message = {
        'nonce' : golden_nonce,
        'blockBinary': block_binary,
        'timeTaken': time_taken,
        'instanceId': instance_id
    }
    response = sqs.send_message(
        QueueUrl=out_queue_url,
        MessageBody=(
            json.dumps(message)
        ),
        MessageGroupId='0',
    )
    
    response = ec2_queue.send_message(
        MessageBody=(
            json.dumps(message)
        ),
        MessageGroupId='0',
    )
    
    
    timestamp = int(round(time.time() * 1000))
    
    response = logs.put_log_events(
        logGroupName=log_group_name,
        logStreamName=log_stream_name,
        logEvents=[
            {
                'timestamp': timestamp,
                'message': json.dumps(message)
            },
        ],
    )
    sys.stdout.write('NONCE FOUND')  
    sys.exit(1)

def waitForExternalNonceDiscovery():
    global they_found_nonce
    message_received = False
    
    while not message_received: 
        message = ec2_queue.receive_messages(
            MaxNumberOfMessages=1,
            VisibilityTimeout=10,
            WaitTimeSeconds=20,
        )

        sys.stdout.write('CANT FIND MESSAGE\n')
        
        if message:
            sys.stdout.write('EC2 MESSAGE RECEIVED FROM OTHER INSTANCE\n')
            message_received = True
            response = ec2_queue.delete_messages(
                Entries=[{
                    'Id': message[0].message_id,
                    'ReceiptHandle': message[0].receipt_handle
                }]
            )
    
    timestamp = int(round(time.time() * 1000))
    
    message = {
        'nonceFoundByMe' : False
    }
    
    response = logs.put_log_events(
        logGroupName=log_group_name,
        logStreamName=log_stream_name,
        logEvents=[
            {
                'timestamp': timestamp,
                'message': json.dumps(message)
            },
        ],
    )
    
    they_found_nonce = True
    sys.stdout.write('NONCE FOUND BY OTHER INSTANCE\n')
    sys.exit(1)  


def findNonce():
    global i_found_nonce
    start_time = datetime.datetime.now()
    nonce = args.start
        
    # Brute force through all possible nonce values
    while (nonce <= max_nonce):        
        block = get_block(nonce)
        block_hash = get_block_hash(block)
        block_hash_binary = get_block_hash_binary(block_hash)
        leading_zeroes = len(block_hash_binary.split('1', 1)[0])

        if (leading_zeroes == difficulty):
            time_taken = (datetime.datetime.now() - start_time).total_seconds()
            
            out_queue_url = getQueueURL('outqueue.fifo')
            
            message = {
                'nonce' : nonce,
                'blockBinary': block_hash_binary,
                'timeTaken': time_taken,
                'instanceId': instance_id
            }
            
            timestamp = int(round(time.time() * 1000))
    
            response = logs.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=[
                    {
                        'timestamp': timestamp,
                        'message': json.dumps(message)
                    },
                ],
            )
            
            response = sqs.send_message(
                QueueUrl=out_queue_url,
                MessageBody=(
                    json.dumps(message)
                ),
                MessageGroupId='0',
            )           

            
            # nonce_found(nonce, block_hash_binary, time_taken)
            i_found_nonce = True
            sys.stdout.write('NONCE FOUND ' + str(nonce))
            break
        
        nonce += 1
    
    sys.exit(1)
           
# Nonce discovery
if __name__ == "__main__":
    t1 = Thread(target=findNonce, daemon=True)
    t2 = Thread(target=waitForExternalNonceDiscovery, daemon=True)

    t1.start()
    t2.start()
    
    while (i_found_nonce == False) and (they_found_nonce == False):
        pass
        
    sys.stdout.write('EXIT PROGRAM')
    sys.exit()
    os.exit()
    




        

        