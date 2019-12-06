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
import confidence
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
    if x < 0:
        raise argparse.ArgumentTypeError("Timeout value must be positive")
    return x

parser = argparse.ArgumentParser(description='''A client interfacing with AWS allowing a user to discover the golden nonce 
                                 for a block. This solution is parallelised across a given n EC2 instances for faster performance.''')

parser.add_argument("-i", "--instances", default=1, type=instance_type, help="The number of EC2 instances to divide the task across.")
parser.add_argument("-d", "--difficulty", default=10, type=int, help='''The difficulty of nonce discovery. This corresponds to the 
                    number of leading zero bits required in the hash.''')
parser.add_argument("-t", "--timeout", default=0, type=time_type, help="Limit of time in seconds before scram is initiated")
parser.add_argument("-l", "--logscram", default=False, action="store_true", help="Gives the option to collect logs from instances on scram")
parser.add_argument("-c", "--confidence", default=False, action="store_true", help="This will allow the program to automatically choose the number of instances to spawn according to runtime")

args = parser.parse_args()

no_of_instances = args.instances
difficulty = args.difficulty
timeout = args.timeout
log_on_scram = args.logscram
instances = []

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise interface to AWS
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

aws = awslib.initialiseInterface()

queue_names = ['in_queue', 'out_queue', 'scram_queue']
queues = awslib.initialiseQueues(aws['sqs'], queue_names)

log_group_name = 'PoW_logs'
awslib.createLogGroup(aws['logs'], log_group_name)

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Calculate instance count by confidence value
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

confidence_value = 0
runtime = 0
min_instances = False

if (args.confidence):
    # Take input and validate before continuing
    while True:
        confidence_value = float(input("Enter your confidence value: "))
        if not (confidence_value >= 0 and confidence_value <= 100):
            print("Confidence value must be a decimal between 0 and 100")
        else:
            break 
    while True:
        runtime = float(input("Enter your desired runtime: "))
        if not (runtime > 0):
            print("Runtime must be a number above 0")
        else:
            break
    while True:
        min_instances = input("Would you like to use the minimum number of instances possible? y/n : ")
        if min_instances == "y":
            min_instances = True
            break
        elif min_instances == "n":
            min_instances = False  
            break
    
    # Calculate number of instances by runtime and confidence value given
    no_of_instances = confidence.getNoOfInstancesByRuntime(runtime, difficulty, confidence_value, min_instances)
    
    if (no_of_instances == -1):
        print("No number of instances can discover the nonce with confidence in the given runtime.")
        print("Please try again with a higher run time")
        exit()
    
    print(f'Using performance statistics, it has been decided {no_of_instances} instances will be suffcient ' +
          f'to find the nonce within a runtime of {runtime}')

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
    
    awslib.scram(aws['ssm'], aws['ec2'], instances, queues, log_on_scram)

    print('SUCCESS!')
    print('Exiting...')
    exit()
    

signal.signal(signal.SIGINT, terminate)
signal.signal(signal.SIGALRM, terminate)


print('----------------------------------------------------------')
print('--------------------------START---------------------------')
print('----------------------------------------------------------')

print(f'Number of instances = {no_of_instances} ||  Difficulty = {difficulty} || Timeout = {timeout}s')

print('----------------------------------------------------------')
      
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

# Used for creating log stream name
date_time = start_time.strftime('%Y/%m/%d-[%H.%M.%S]')

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
        "dateTime"      : date_time,
        "logOnScram"    : log_on_scram
    }
    
    response = awslib.sendMessageToQueue(queues['in_queue'], message)

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print(f'SUCCESS!')
    else:
        print(f'ERROR: Failed to send message to input queue')

# Start timing to scram once instances have been notified
if timeout != 0:
    signal.alarm(timeout)
    
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
output_message['searchTime'] = f'{search_time_taken:.6f}'

# Shut down instance which sent message
response = aws['ec2'].terminate_instances(InstanceIds=[sender_instance_id])

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initiate scram
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Shutting down all AWS resources...', end="")

awslib.cancelAllCommands(aws['ssm'])
awslib.shutdownAllInstances(aws['ec2'], instances)
awslib.purgeQueues(queues)

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Push log to CloudWatch
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# Calculate total time taken and overhead from using cloud
overall_time_taken = (end_time - start_time).total_seconds()
cloud_overhead = overall_time_taken - search_time_taken

update_message = {
    'totalTime'     : float(f'{overall_time_taken:.6f}'),
    'cloudOverhead' : float(f'{cloud_overhead:.6f}'),
    'difficulty'    : difficulty,
    'noOfInstances' : no_of_instances,
    'logOnScram'    : log_on_scram
}

output_message['searchTime'] = float(output_message['searchTime'])

# Create final message to log
log_message = merge(output_message, update_message)
log_stream_name = f'{log_stream_prefix}-{sender_instance_id}'

# Create and upload log to stream for successful instance
awslib.createLogStream(aws['logs'], log_group_name, log_stream_name)
awslib.putLogEvent(aws['logs'], log_group_name, log_stream_name, log_message)



'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Save logs
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print('----------------------------------------------------')
print('----------------------COMPLETE----------------------')
print('----------------------------------------------------')
    
print(json.dumps(log_message, indent=4))