import sys
import os
import math
import signal
import json
import boto3
import argparse
import time
import datetime
from datetime import datetime
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
ec2 = boto3.client('ec2')
sqs = boto3.client('sqs')
ssm = boto3.client('ssm')
logs = boto3.client('logs')

s3 = boto3.resource('s3')
ec2_resource = boto3.resource('ec2')
sqs_resource = boto3.resource('sqs')

# SQS Queues
in_queue_url = aws.getQueueURL(sqs, 'inqueue.fifo')
out_queue_url = aws.getQueueURL(sqs, 'outqueue.fifo')
scram_queue_url = aws.getQueueURL(sqs, 'scram_queue')
in_queue = sqs_resource.Queue(in_queue_url)
out_queue = sqs_resource.Queue(out_queue_url)
scram_queue = sqs_resource.Queue(scram_queue_url)

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
    
    aws.scram(ssm, ec2, instances, [in_queue, out_queue, scram_queue])

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
print(f'-------------- Number of instances = {no_of_instances} -------------')
print(f'------------------ Difficulty = {difficulty} -----------------')
print('----------------------------------------------------')

print(f'Number of instances = {no_of_instances} ||  Difficulty = {difficulty}')
      
# Start timer to calculate overall time taken to find golden nonce
start_time = datetime.now()

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Upload python script cnd.py to S3 bucket
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print('Uploading pow.py to S3 bucket...', end="")

aws.uploadFileToBucket(s3, 'faizaanbucket', 'pow.py', 'pow.py')

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

# Create log group name according to diffficulty
log_group_name = f'PoW_d_{difficulty}'
aws.createLogGroup(logs, log_group_name)

# Send off messages to input queue
for i in range(0, len(ordered_instances)):
    print(f'Sending message to input queue to initiate discovery in {ordered_instances[i].id}...', end="")

    # Calculate search space for instance
    start_nonce = search_split * i
    end_nonce = search_split * (i + 1)
        
    message = {
        "instanceId"   : ordered_instances[i].id,
        "difficulty"   : difficulty,
        "startNonce"   : start_nonce,
        "endNonce"     : end_nonce,
        "logGroupName" : log_group_name
    }
    
    response = aws.sendMessageToFifoQueue(in_queue, message)

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
    message = aws.receiveMessageFromQueue(out_queue)

    if message:
        message_received = True
        aws.deleteMessageFromQueue(out_queue, message)
        
        
end_time = datetime.now()
overall_time_taken = (end_time - start_time).total_seconds()

print('SUCCESS!')

# Get required data from message
message_body = json.loads(message[0].body)
sender_instance_id = message_body['instanceId']
search_time_taken = message_body['searchTime']

# Shut down instance which sent message
response = ec2.terminate_instances(InstanceIds=[sender_instance_id])

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initiate scram
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Shutting down all AWS resources...', end="")

# time.sleep(10)

aws.cancelAllCommands(ssm)
aws.purgeQueues([in_queue, out_queue, scram_queue])
aws.shutdownAllInstances(ec2, instances)

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Push log for total time taken
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# Get current log stream for successful instance
response = logs.describe_log_streams(
    logGroupName=log_group_name,
    logStreamNamePrefix=sender_instance_id,
    limit=1
)

log_stream = response['logStreams'][0]
log_stream_name = log_stream['logStreamName']

# Get upload sequence token to upload total time to log
next_token = log_stream['uploadSequenceToken']

cloud_overhead = 0

if overall_time_taken > search_time_taken:
    cloud_overhead = overall_time_taken - search_time_taken
else:
    cloud_overhead = search_time_taken - overall_time_taken
    
message = {
    'totalTime' : overall_time_taken,
    'cloudOverhead' : cloud_overhead
}
    
response = logs.put_log_events(
    logGroupName=log_group_name,
    logStreamName=log_stream_name,
    logEvents=[
        {
            'timestamp': int(round(time.time() * 1000)),
            'message': json.dumps(message)
        },
    ],
    sequenceToken=next_token
)

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Retrieve logs
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

response = logs.get_log_events(
    logGroupName=log_group_name,
    logStreamName=log_stream_name,
    startFromHead=True
)

print(response)

log = response['events'][0]['message']
log = json.loads(log)


print('----------------------------------------------------')
print('----------------------COMPLETE----------------------')
print('----------------------------------------------------')

print(json.dumps(log, indent=2, sort_keys=True))
