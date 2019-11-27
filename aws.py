
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
aws.py 

This holds all the custom functions created for the client
to communicate with AWS using boto3.
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''

import boto3
import time
import json

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

def getQueueURL(sqs, queue_name):
    response = sqs.get_queue_url(QueueName=queue_name)
    queue_url = response['QueueUrl']
    return queue_url
    
def createInstances(ec2, no_of_instances):
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
    
    return instances['Instances']

def waitUntilInstancesReady(ec2_resource, no_of_instances):
    ordered_instances = []
    all_instances_ready = False

    while (not all_instances_ready):
        instances_response = ec2_resource.instances.filter(
            Filters=[{
                'Name': 'instance-state-name', 
                'Values': ['running']
            }]
        )
        ordered_instances = [instance for instance in instances_response]
        
        if len(ordered_instances) == no_of_instances:
            all_instances_ready = True
        
        time.sleep(1)
    
    return ordered_instances

def sendMessageToQueue(queue, message):
    response = queue.send_message(
        MessageBody=(
            json.dumps(message)
        ),
        MessageGroupId='0',
    )
    
    return response

def receiveMessageFromQueue(queue):
    result = queue.receive_messages(
        MaxNumberOfMessages=1,
        VisibilityTimeout=10,
        WaitTimeSeconds=20,
    )
    return result
    
def deleteMessageFromQueue(queue, message):
    response = queue.delete_messages(
        Entries=[{
            'Id': message[0].message_id,
            'ReceiptHandle': message[0].receipt_handle
        }]
    )
    
def cancelAllCommands(ssm):
    # Get all running commands before cancelling
    running_commands = ssm.list_commands(
        Filters=[
            {
                'key': 'Status',
                'value': 'InProgress'
            },
        ]
    )

    for command in running_commands['Commands']:
        command_id = command['CommandId']
        ssm.cancel_command(CommandId=command_id)
        
def shutdownAllInstances(ec2, instances):
    instance_ids = []
    for instance in instances:
        instance_ids.append(instance['InstanceId'])

    response = ec2.terminate_instances(InstanceIds=instance_ids)
    
def purgeQueues(queues):
    for queue in queues:
        queue.purge()
        
def scram(ssm, ec2, instances, queues):
    cancelAllCommands(ssm)
    shutdownAllInstances(ec2, instances)
    purgeQueues(queues)
    