import sys
import os
import math
import signal
import json
import boto3
import argparse
import time
import datetime
import functools
import aws
from botocore.exceptions import ClientError

# Disable output buffering
print = functools.partial(print, flush=True)

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Argument Parsing
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

def instance_type(x):
    x = int(x)
    if x > 14:
        raise argparse.ArgumentTypeError("Maximum number of instances is 14")
    elif x < 1:
        raise argparse.ArgumentTypeError("Minimum number of instances is 1")
    return x

def time_type(x):
    x = int(x)
    if x < 0:
        raise argparse.ArgumentTypeError("Timeout value must be positive")
    return x

parser = argparse.ArgumentParser(description='''A client interfacing with AWS allowing a user to discover the golden nonce 
                                 for a block. This solution is parallelised across a given n EC2 instances for faster performance.''')

parser.add_argument("-i", "--instances", default=1, type=instance_type, help="The number of EC2 instances to divide the task across.")
parser.add_argument("-d", "--difficulty", default=10, type=int, help='''The difficulty of nonce discovery. This corresponds to the 
                    number of leading zero bits required in the hash.''')
parser.add_argument("-t", "--timeout", default=6000, type=time_type, help="Limit of time before scram is initiated")

args = parser.parse_args()

no_of_instances = args.instances
difficulty = args.difficulty
timeout = args.timeout
instances = []

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise interface to AWS
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
ec2 = boto3.client('ec2')
sqs = boto3.client('sqs')
ssm = boto3.client('ssm')
s3 = boto3.resource('s3')
ec2_resource = boto3.resource('ec2')
sqs_resource = boto3.resource('sqs')

# SQS Queues
# Use create_event_source_mapping to create queues?
in_queue_url = aws.getQueueURL(sqs, 'inqueue.fifo')
out_queue_url = aws.getQueueURL(sqs, 'outqueue.fifo')
in_queue = sqs_resource.Queue(in_queue_url)
out_queue = sqs_resource.Queue(out_queue_url)

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Callbacks
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

def terminate(signum, frame):
    signal.signal(signal.SIGINT, original_sigint)
    
    print('Scram initialised, shutting down everything...', end="")
    aws.scram(ssm, ec2, instances, [in_queue, out_queue])
    print('SUCCESS!')
    print('Exiting...')    
    exit()

original_sigint = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, terminate)


print('----------------------------------------------------')
print('-----------------------START------------------------')
print('----------------------------------------------------')
print(f'-------------- Number of instances = {no_of_instances} -------------')
print(f'------------------ Difficulty = {difficulty} -----------------')
print('----------------------------------------------------')


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Upload python script cnd.py to S3 bucket
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print('Uploading cnd.py to S3 bucket...', end="")

BUCKET = "faizaanbucket"
s3.Bucket(BUCKET).upload_file("cnd.py", "cnd.py")

print("SUCCESS!")

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise instances
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Initialising {no_of_instances} EC2 instance(s)...', end="")

instances = aws.createInstances(ec2, no_of_instances)

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Wait to complete checks
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Waiting for EC2 status checks to complete...', end="")

ordered_instances = aws.waitUntilInstancesReady(ec2_resource, no_of_instances)
          
# Give some additional time for instances to settle down
# Note: without the wait period below, the Lambda function would fail
# as it would not recognise the corresponding instance as active
time.sleep(10)

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Send message to SQS queue to trigger script
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# Calculate search space for each EC2 instance
max_nonce = 2 ** 32
search_split = math.ceil(max_nonce / len(ordered_instances))

for i in range(0, len(ordered_instances)):
    print(f'Sending message to input queue to initiate discovery in {ordered_instances[i].id}...', end="")

    start_nonce = search_split * i
    end_nonce = search_split * (i + 1)
        
    message = {
        "instanceId" : ordered_instances[i].id,
        "difficulty" : difficulty,
        "startNonce" : start_nonce,
        "endNonce" : end_nonce
    }
    
    response = aws.sendMessageToQueue(in_queue, message)

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print(f'SUCCESS!')
    else:
        print(f'ERROR: Failed to send message to input queue')


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Read output queue to get back nonce
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Waiting for reply...', end="")

message_received = False
start_time = datetime.datetime.now()

while not message_received: 
    message = aws.receiveMessageFromQueue(out_queue)

    if message:
        message_received = True
        aws.deleteMessageFromQueue(out_queue, message)
        
        
end_time = datetime.datetime.now()
message_time_taken = (end_time - start_time).total_seconds()

print('SUCCESS!')

print(f'Time taken to receive message: {message_time_taken}')

message_body = json.loads(message[0].body)
nonce = message_body['nonce']
block_binary = message_body['blockBinary']
sender_instance_id = message_body['instanceId']
time_taken = message_body['timeTaken']

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Gracefully shutdown all running commands and instances
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Shutting down all running commands and EC2 instances...', end="")

aws.cancelAllCommands(ssm)
aws.shutdownAllInstances(ec2, instances)

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Delete queues
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Purging SQS queues...', end="")

# Remove all outstanding messages in queues
# response = in_queue.purge()
# response = out_queue.purge()
aws.purgeQueues([in_queue, out_queue])

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Log Feedback
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print('----------------------------------------------------')
print('----------------------COMPLETE----------------------')
print('----------------------------------------------------')

sender_number = 0


for i in range(0, len(ordered_instances)):
    if ordered_instances[i].id == sender_instance_id:
        sender_number = i
    
message_delivery_overhead = message_time_taken - float(time_taken)

print(f'Golden nonce: {nonce}')
print(f'Delivered by instance no. {sender_number} with id {sender_instance_id}')
print(f'Data in binary: {block_binary}')
print(f'Discovered in : {"{:.4f}".format(time_taken)}s')
print(f'Message delivery overhead: {"{:.4f}".format(message_delivery_overhead)}s')
