import sys
import json
import boto3
import cnd
from botocore.exceptions import ClientError

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
AWS Functions
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

def createFifoQueue(queue_name):
    response = sqs.create_queue(
        QueueName=queue_name,
        Attributes={
            'DelaySeconds': '60',
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
Initialise interface to AWS
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
s3 = boto3.resource('s3')
ec2 = boto3.client('ec2')
sqs = boto3.client('sqs')
ssm = boto3.client('ssm')

# SQS Queues
in_queue_name = 'inqueue.fifo'
out_queue_name = 'outqueue.fifo'
in_queue_url = getQueueURL(in_queue_name)
out_queue_url = getQueueURL(out_queue_name)

# Use create_event_source_mapping to create queues?

# Upload python script to S3 bucket
BUCKET = "faizaanbucket"
s3.Bucket(BUCKET).upload_file("cnd.py", "cnd.py")

vms = 1
difficulty = 10

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise instances
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

response = ec2.run_instances(
    BlockDeviceMappings=[
        {   
            'DeviceName': '/dev/xvda',
            'Ebs': {
                'DeleteOnTermination': True,
                'SnapshotId': 'snap-03a3e785d4ebe70ba',
                'VolumeSize': 8,
                'VolumeType': 'gp2',
                'Encrypted': False,
            },
        },
    ],
    ImageId = 'ami-04cee60151dbb4d91',
    InstanceType = 't2.micro',
    KeyName = 'awsec2',
    MinCount = 1,
    MaxCount = vms,
    SecurityGroups=['security-group-allow-all'],
    IamInstanceProfile={
        'Name': 'EC2AdminRole'
    },
)


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Wait to complete checks
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# Get all instances
# Keep checking until all status checks complete

# response = ec2.describe_instances()
# instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Send message to SQS queue to trigger script
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# For loop to send n messages to queue each with instance_id

message = {
    "instance_id" : "i-0b9ec9605be549b72",
    "difficulty" : difficulty,
    "start_nonce" : "0",
    "end_nonce" : "20000"
}

# response = sqs.send_message(
#     QueueUrl=in_queue_url,
#     MessageBody=(
#         json.dumps(message)
#     ),
#     MessageGroupId='0',
# )

# print(response)

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Read output queue to get back nonce
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Gracefully shutdown all running VMs
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Delete queues
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''



# Maybe just purge instead?
# Delete the SQS queues
# sqs.delete_queue(QueueUrl=in_queue_url)
# sqs.delete_queue(QueueUrl=out_queue_url)