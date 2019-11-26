import sys
import json
import boto3
import argparse
from botocore.exceptions import ClientError


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
AWS Functions
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

def createFifoQueue(queue_name):
    response = sqs.create_queue(
        QueueName=queue_name,
        Attributes={
            'DelaySeconds': '5',
            'MessageRetentionPeriod': '86400',
            'FifoQueue': 'true',
            'ContentBasedDeduplication': 'true',
        }
    )

def getQueueURL(queue_name):
    response = sqs.get_queue_url(QueueName=queue_name)
    queue_url = response['QueueUrl']
    return queue_url
    
def startInstance(instance_id):
    # Do a dryrun first to verify permissions
    try:
        ec2.start_instances(InstanceIds=[instance_id], DryRun=True)
    except ClientError as e:
        if 'DryRunOperation' not in str(e):
            raise

    # Dry run succeeded, run start_instances without dryrun
    try:
        response = ec2.start_instances(InstanceIds=[instance_id], DryRun=False)
        print(response)
    except ClientError as e:
        print(e)

def stopInstance(instance_id):
    # Do a dryrun first to verify permissions
    try:
        ec2.stop_instances(InstanceIds=[instance_id], DryRun=True)
    except ClientError as e:
        if 'DryRunOperation' not in str(e):
            raise

    # Dry run succeeded, call stop_instances without dryrun
    try:
        response = ec2.stop_instances(InstanceIds=[instance_id], DryRun=False)
        print(response)
    except ClientError as e:
        print(e)


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

parser = argparse.ArgumentParser(description='''A client interfacing with AWS allowing a user to discover the golden nonce 
                                 for a block. This solution is parallelised across a given n EC2 instances for faster performance.''')

parser.add_argument("-i", "--instances", default=1, type=instance_type, help="The number of EC2 instances to divide the task across.")
parser.add_argument("-d", "--difficulty", default=10, type=int, help='''The difficulty of nonce discovery. This corresponds to the 
                    number of leading zero bits required in the hash.''')

args = parser.parse_args()

no_of_instances = args.instances
difficulty = args.difficulty

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise interface to AWS
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
s3 = boto3.resource('s3')
ec2 = boto3.client('ec2')
sqs = boto3.client('sqs')
ssm = boto3.client('ssm')
ec2_resource = boto3.resource('ec2')
sqs_resource = boto3.resource('sqs')

# SQS Queues
in_queue_name = 'inqueue.fifo'
out_queue_name = 'outqueue.fifo'
in_queue_url = getQueueURL(in_queue_name)
out_queue_url = getQueueURL(out_queue_name)
in_queue = sqs_resource.Queue(in_queue_url)
out_queue = sqs_resource.Queue(out_queue_url)

# Use create_event_source_mapping to create queues?

# Upload python script to S3 bucket
print('Uploading cnd.py to S3 bucket...', end="")

BUCKET = "faizaanbucket"
s3.Bucket(BUCKET).upload_file("cnd.py", "cnd.py")

print("SUCCESS!")

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise instances
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Initialising {no_of_instances} EC2 instance(s)...', end="")

instances = ec2.run_instances(
    BlockDeviceMappings=[
        {   
            'DeviceName': '/dev/xvda',
            'Ebs': {
                'DeleteOnTermination': True,
                'VolumeSize': 8,
                'VolumeType': 'gp2',
                'Encrypted': False,
            },
        },
    ],
    ImageId = 'ami-091805f6b92bf74a1',
    InstanceType = 't2.micro',
    KeyName = 'awsec2',
    MinCount = 1,
    MaxCount = no_of_instances,
    SecurityGroups=['security-group-allow-all'],
    IamInstanceProfile={
        'Name': 'EC2AdminRole'
    },
)

instances = instances['Instances']

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Wait to complete checks
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Waiting for EC2 status checks to complete...', end="")

# Keep checking until all status checks complete
instance_ids = []
all_instances_ready = False

while (not all_instances_ready):
    instances_response = ec2_resource.instances.filter(
        Filters=[{
            'Name': 'instance-state-name', 
            'Values': ['running']
        }]
    )
    instance_ids = [instance for instance in instances_response]
    
    if len(instance_ids) == no_of_instances:
        all_instances_ready = True
               
print('SUCCESS!')


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Send message to SQS queue to trigger script
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# For loop to send n messages to queue each with instance_id

print(f'Sending message to input queue to initiate discovery in {instance_ids[0].id}...', end="")

message = {
    "instance_id" : instance_ids[0].id,
    "difficulty" : difficulty,
    "start_nonce" : "0",
    "end_nonce" : "20000"
}

response = sqs.send_message(
    QueueUrl=in_queue_url,
    MessageBody=(
        json.dumps(message)
    ),
    MessageGroupId='0',
)

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
    response = sqs.receive_message(
        QueueUrl=out_queue_url,
        AttributeNames=[
            'SentTimestamp'
        ],
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20
    )
    
    if ('messages' in response.keys()):
        message_received = True
    
    
# Delete message off queue
# response = out_queue(
    
# )

print(f'\n{result}\n')

message_body = result['Messages'][0]['Body']
message_body = json.loads(message_body)

nonce = message_body['nonce']

print('SUCCESS!')


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Gracefully shutdown all running instances
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Shutting down all running EC2 instances...', end="")

instance_ids = []
for instance in instances:
    instance_ids.append(instance['InstanceId'])

response = ec2.terminate_instances(InstanceIds=instance_ids)

print('SUCCESS!')


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Delete queues
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print(f'Purging SQS queues...', end="")

# Maybe just purge instead?
# Delete the SQS queues
response = in_queue.purge()
response = out_queue.purge()

print('SUCCESS!')

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Log Feedback
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

print('----------------------------------------------------')
print('------------------NONCE DISCOVERED------------------')
print('----------------------------------------------------')
print(f'Golden nonce: {nonce}')

