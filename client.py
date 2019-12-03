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
import awslib
from datetime import datetime
from jsonmerge import merge
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
    if x < 1:
        raise argparse.ArgumentTypeError("Timeout value must be positive")
    return x

parser = argparse.ArgumentParser(description='''A client interfacing with AWS allowing a user to discover the golden nonce 
                                 for a block. This solution is parallelised across a given n EC2 instances for faster performance.''')

parser.add_argument("-i", "--instances", default=1, type=instance_type, help="The number of EC2 instances to divide the task across.")
parser.add_argument("-d", "--difficulty", default=10, type=int, help='''The difficulty of nonce discovery. This corresponds to the 
                    number of leading zero bits required in the hash.''')
parser.add_argument("-t", "--timeout", default=0, type=time_type, help="Limit of time in seconds before scram is initiated")

args = parser.parse_args()

no_of_instances = args.instances
difficulty = args.difficulty
timeout = args.timeout
instances = []

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise interface to AWS
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

aws = awslib.initialiseInterface()

# SQS Queues
queue_names = ['inqueue.fifo', 'outqueue.fifo', 'scram_queue']
queues = awslib.initialiseQueues(aws['sqs'], queue_names)

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Callbacks
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

def terminate(signum, frame):      
    # User terminated program with Ctrl + C interrupt
    if (signum == 2):
        print('\nScram initiated by user')
        
    # Timeout terminated program
    elif (signum == 14):
        print(f'\nTimeout limit of {timeout}s reached. Scram initiated.')
    
    print('Shutting down everything and asking back for logs...', end="")
    
    awslib.scram(ssm, aws['ec2'], instances, queues)

    print('SUCCESS!')
    print('Exiting...')
    exit()
    

signal.signal(signal.SIGINT, terminate)
signal.signal(signal.SIGALRM, terminate)

if timeout != 0:
    signal.alarm(timeout)

print('----------------------------------------------------')
print('-----------------------START------------------------')
print('----------------------------------------------------')

print(f'Number of instances = {no_of_instances} ||  Difficulty = {difficulty} || Timeout = {timeout}')

print('----------------------------------------------------')
      
# Start timer to calculate overall time taken to find golden nonce
start_time = datetime.now()

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Upload python script cnd.py to S3 bucket
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print('Uploading pow.py to S3 bucket...', end="")

awslib.uploadFileToBucket(aws['s3'], 'faizaanbucket', 'pow.py', 'pow.py')

print("SUCCESS!")

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise instances
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Initialising {no_of_instances} EC2 instance(s)...', end="")

instances = awslib.createInstances(aws['ec2'], no_of_instances)

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Wait to complete checks
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Waiting for EC2 status checks to complete...', end="")

ordered_instances = awslib.waitUntilInstancesReady(aws['ec2_resource'], no_of_instances)
          
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

# Create log group name according to diffficulty
log_group_name = f'PoW_d_{difficulty}'
awslib.createLogGroup(aws['logs'], log_group_name)

# Used for creating log stream name
log_stream_prefix = start_time.strftime('%Y/%m/%d-[%H.%M.%S]')

# Send off messages to input queue
for i in range(0, len(ordered_instances)):
    print(f'Sending message to input queue to initiate discovery in {ordered_instances[i].id}...', end="")

    # Calculate search space for instance
    start_nonce = search_split * i
    end_nonce = search_split * (i + 1)
            
    message = {
        "instanceId"    : ordered_instances[i].id,
        "difficulty"    : difficulty,
        "startNonce"    : start_nonce,
        "endNonce"      : end_nonce,
        "dateTime"      : log_stream_prefix
    }
    
    response = awslib.sendMessageToFifoQueue(queues['in_queue'], message)

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print(f'SUCCESS!')
    else:
        print(f'ERROR: Failed to send message to input queue')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Read output queue to get back nonce
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Waiting for reply...', end="")

message_received = False

while not message_received: 
    message = awslib.receiveMessageFromQueue(queues['out_queue'])

    if message:
        message_received = True
        awslib.deleteMessageFromQueue(queues['out_queue'], message)
        
        
end_time = datetime.now()

print('SUCCESS!')

# Get required data from message
output_message = json.loads(message[0].body)
sender_instance_id = output_message['instanceId']
search_time_taken = output_message['searchTime']

# Shut down instance which sent message
response = aws['ec2'].terminate_instances(InstanceIds=[sender_instance_id])

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initiate scram
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Shutting down all AWS resources...', end="")

awslib.cancelAllCommands(aws['ssm'])
awslib.purgeQueues(queues)
awslib.shutdownAllInstances(aws['ec2'], instances)

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Push log to CloudWatch
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# Calculate total time taken and overhead from using cloud
overall_time_taken = (end_time - start_time).total_seconds()
cloud_overhead = overall_time_taken - search_time_taken

time_message = {
    'totalTime' : overall_time_taken,
    'cloudOverhead' : cloud_overhead
}

# Create final message to log
log_message = merge(output_message, time_message)
log_stream_name = f'{log_stream_prefix}-{sender_instance_id}'

# Create and upload log to stream for successful instance
awslib.createLogStream(aws['logs'], log_group_name, log_stream_name)
awslib.putLogEvent(aws['logs'], log_group_name, log_stream_name, log_message)

# Allow some time for log events to be pushed
time.sleep(2)

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Save logs
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print('----------------------------------------------------')
print('----------------------COMPLETE----------------------')
print('----------------------------------------------------')
    
print(json.dumps(log_message, indent=4))
