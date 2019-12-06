import json
import boto3
import time

ec2 = boto3.resource('ec2')
ssm = boto3.client('ssm')

def lambda_handler(event, context):
    
    message_body = json.loads(event['Records'][0]['body'])
    
    # Get instance_id to run script on
    instance_id = message_body['instance_id']

    # Get difficulty to use as parameter for script
    difficulty = message_body['difficulty']

    command_download_script = 'aws s3 cp s3://faizaanbucket/cnd.py home/ec2-user/cnd.py'
    command_run_script = f'sudo python3 home/ec2-user/cnd.py --d {difficulty}'
    
    commands = [command_download_script, command_run_script]

    # Check if instance exists
    instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    instance_ids = []
    for instance in instances:
        instance_ids.append(instance.id)

    if (instance_id not in instance_ids):
        return {
            'statusCode': 404
        }
    
    # Send command to download script and execute to instance
    ssmresponse = ssm.send_command(InstanceIds=[instance_id], DocumentName='AWS-RunShellScript', Parameters= { 'commands': commands } ) 
    
    return {
        'statusCode': 200
    }
